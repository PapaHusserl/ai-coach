import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
from garmin_fakes import FakeGarmin, sync_log
from typer.testing import CliRunner
from workload_fakes import (
    FakeCalendar,
    raw_event,
    todo_item,
    tree_state,
    write_config,
    write_hb,
    write_todo,
)

from ai_coach.cli import main
from ai_coach.garmin.client import GarminAuthError
from ai_coach.sync import workload_sync
from ai_coach.workload.calendar_eventkit import CalendarError

runner = CliRunner()
TODAY = date.today()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.setattr(time, "sleep", lambda _: None)
    todo = write_todo(tmp_path / "todo.json", [todo_item(1, "todo", TODAY.isoformat())])
    hb = write_hb(tmp_path / "hb", {"a.md": f"{TODAY.isoformat()} 09:00"}, {})
    config = write_config(
        tmp_path / "w.toml",
        f'[calendar]\nwork = ["Work"]\n[paths]\ntodo = "{todo}"\nhb_watch = "{hb}"\n',
    )
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))
    return db


def use_calendar(monkeypatch: pytest.MonkeyPatch, calendar: FakeCalendar) -> None:
    monkeypatch.setattr(workload_sync, "CalendarReader", lambda *a, **k: calendar)


def rows(db: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def event_today() -> dict:
    start = f"{TODAY.isoformat()}T10:00:00"
    return raw_event(uid="w", start_at=start, end_at=f"{TODAY.isoformat()}T11:00:00")


def test_sync_also_imports_workload(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar([event_today()]))
    result = runner.invoke(main.app, ["sync", "--days", "3"])
    assert result.exit_code == 0
    assert rows(isolated, "SELECT uid FROM calendar_events") == [("w",)]
    kinds = {r[0] for r in rows(isolated, "SELECT kind FROM day_counters")}
    assert kinds == {"todo_open", "todo_closed", "grooming_done", "grooming_pending"}


def test_sync_logs_both_sync_and_workload(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    runner.invoke(main.app, ["sync", "--days", "1"])
    assert sorted((r["kind"], r["status"]) for r in sync_log(isolated)) == [
        ("sync", "ok"),
        ("workload", "ok"),
    ]


def test_garmin_auth_error_still_runs_workload_and_exits_1(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_tokens(*a: object, **k: object) -> None:
        raise GarminAuthError("Токенов Garmin нет. Выполни: coach login")

    monkeypatch.setattr(main, "load_client", no_tokens)
    use_calendar(monkeypatch, FakeCalendar([event_today()]))
    result = runner.invoke(main.app, ["sync"])
    assert result.exit_code == 1
    assert "coach login" in result.output
    assert rows(isolated, "SELECT uid FROM calendar_events") == [("w",)]
    assert rows(isolated, "SELECT COUNT(*) FROM day_counters")[0][0] > 0


def test_calendar_error_does_not_break_garmin_sync(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar(error=CalendarError("нет доступа")))
    result = runner.invoke(main.app, ["sync", "--days", "2"])
    assert rows(isolated, "SELECT COUNT(*) FROM daily_metrics")[0][0] == 2
    assert rows(isolated, "SELECT COUNT(*) FROM day_counters")[0][0] > 0
    assert "Traceback" not in result.output
    assert ("workload", "error") in [(r["kind"], r["status"]) for r in sync_log(isolated)]


def test_sync_does_not_modify_todo_and_hb_watch(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = tree_state(tmp_path / "todo.json", tmp_path / "hb")
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar([event_today()]))
    runner.invoke(main.app, ["sync", "--days", "2"])
    runner.invoke(main.app, ["sync", "--days", "2"])
    assert tree_state(tmp_path / "todo.json", tmp_path / "hb") == before


def test_second_sync_keeps_first_run_today_logic(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Один sync дня = одна строка kind='sync', workload её не удваивает."""
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    runner.invoke(main.app, ["sync", "--days", "1"])
    assert [r["kind"] for r in sync_log(isolated)].count("sync") == 1


def test_sync_window_edge_uses_days_option(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    calendar = FakeCalendar()
    use_calendar(monkeypatch, calendar)
    runner.invoke(main.app, ["sync", "--days", "3"])
    assert calendar.calls == [(TODAY - timedelta(days=3), TODAY + timedelta(days=14))]
