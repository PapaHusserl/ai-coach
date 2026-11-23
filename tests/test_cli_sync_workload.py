import json
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
        f'[calendar]\nwork = ["Work"]\n[paths]\ntodo = "{todo}"\nhb_watch = "{hb}"\n'
        f'claude_projects = "{tmp_path / "no-claude"}"\n',
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


def no_garmin(*a: object, **k: object) -> None:
    raise AssertionError("Garmin-клиент не должен вызываться")


def test_sync_calendar_does_not_load_garmin_client(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", no_garmin)
    use_calendar(monkeypatch, FakeCalendar([event_today()]))
    result = runner.invoke(main.app, ["sync", "--calendar"])
    assert result.exit_code == 0
    assert rows(isolated, "SELECT COUNT(*) FROM daily_metrics")[0][0] == 0


def test_sync_calendar_imports_workload(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", no_garmin)
    use_calendar(monkeypatch, FakeCalendar([event_today()]))
    runner.invoke(main.app, ["sync", "--calendar"])
    assert rows(isolated, "SELECT uid FROM calendar_events") == [("w",)]
    assert rows(isolated, "SELECT COUNT(*) FROM day_counters")[0][0] > 0


def test_sync_calendar_logs_workload_and_weather(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", no_garmin)
    use_calendar(monkeypatch, FakeCalendar())
    runner.invoke(main.app, ["sync", "--calendar"])
    assert [(r["kind"], r["status"]) for r in sync_log(isolated)] == [
        ("workload", "ok"),
        ("weather", "error"),
        ("kp", "error"),
    ]


def test_sync_calendar_without_tokens_exits_0(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", no_garmin)
    use_calendar(monkeypatch, FakeCalendar())
    result = runner.invoke(main.app, ["sync", "--calendar"])
    assert result.exit_code == 0
    assert "coach login" not in result.output


def test_sync_without_flag_still_calls_garmin(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    runner.invoke(main.app, ["sync", "--days", "2"])
    assert rows(isolated, "SELECT COUNT(*) FROM daily_metrics")[0][0] == 2


def test_sync_logs_both_sync_and_workload(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    runner.invoke(main.app, ["sync", "--days", "1"])
    assert sorted((r["kind"], r["status"]) for r in sync_log(isolated)) == [
        ("kp", "error"),
        ("sync", "ok"),
        ("weather", "error"),
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


def test_sync_does_not_modify_claude_transcripts(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "projects"
    folder = root / "-synthetic-alpha"
    folder.mkdir(parents=True)
    line = {
        "type": "user",
        "timestamp": f"{TODAY.isoformat()}T10:00:00Z",
        "message": {"role": "user", "content": "синтетическая реплика"},
        "cwd": "/synthetic/alpha",
    }
    (folder / "s1.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
    config = write_config(tmp_path / "c.toml", f'[paths]\nclaude_projects = "{root}"\n')
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    before = tree_state(root)
    runner.invoke(main.app, ["sync", "--days", "2"])
    assert rows(isolated, "SELECT COUNT(*) FROM day_counters WHERE source = 'claude'")[0][0] > 0
    assert tree_state(root) == before


def test_second_sync_keeps_first_run_today_logic(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Один sync дня = одна строка kind='sync', workload её не удваивает."""
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    runner.invoke(main.app, ["sync", "--days", "1"])
    assert [r["kind"] for r in sync_log(isolated)].count("sync") == 1


def with_weather(monkeypatch: pytest.MonkeyPatch) -> None:
    """Место и сервис погоды подменены: настоящие геолокация и сеть не вызываются."""
    from ai_coach import location, weather

    raw = json.loads(
        (Path(__file__).parent / "fixtures" / "weather" / "open_meteo.json").read_text()
    )
    monkeypatch.setattr(location, "read_place", lambda *a, **k: location.Place(52.52, 13.41))
    monkeypatch.setattr(weather, "fetch_forecast", lambda place: raw)


def test_sync_prints_weather_line_after_workload(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    with_weather(monkeypatch)
    result = runner.invoke(main.app, ["sync", "--days", "1"])
    lines = result.output.splitlines()
    assert lines[-1] == "погода: записана, +4°"
    assert len(lines) >= 3
    assert rows(isolated, "SELECT COUNT(*) FROM weather_now")[0][0] == 1


def test_sync_calendar_also_prints_weather_line(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", no_garmin)
    use_calendar(monkeypatch, FakeCalendar())
    with_weather(monkeypatch)
    result = runner.invoke(main.app, ["sync", "--calendar"])
    assert result.output.splitlines()[-1] == "погода: записана, +4°"
    assert [r[0] for r in rows(isolated, "SELECT kind FROM sync_log ORDER BY id")] == [
        "workload",
        "weather",
        "kp",
    ]


def test_weather_failure_prints_reason_and_keeps_exit_code_0(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    result = runner.invoke(main.app, ["sync", "--days", "1"])
    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == "погода: место не определено"
    assert "Traceback" not in result.output


def test_weather_failure_with_calendar_keeps_exit_code_0(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", no_garmin)
    use_calendar(monkeypatch, FakeCalendar())
    result = runner.invoke(main.app, ["sync", "--calendar"])
    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == "погода: место не определено"


def test_weather_runs_after_garmin_error_and_exit_stays_1(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_tokens(*a: object, **k: object) -> None:
        raise GarminAuthError("Токенов Garmin нет. Выполни: coach login")

    monkeypatch.setattr(main, "load_client", no_tokens)
    use_calendar(monkeypatch, FakeCalendar())
    with_weather(monkeypatch)
    result = runner.invoke(main.app, ["sync"])
    assert result.exit_code == 1
    assert rows(isolated, "SELECT COUNT(*) FROM weather_now")[0][0] == 1


def test_weather_does_not_add_sync_run(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    with_weather(monkeypatch)
    runner.invoke(main.app, ["sync", "--days", "1"])
    assert [r["kind"] for r in sync_log(isolated)].count("sync") == 1


def with_kp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сервис NOAA подменён настоящим ответом из фикстуры."""
    from ai_coach import kp

    raw = json.loads((Path(__file__).parent / "fixtures" / "weather" / "kp.json").read_text())
    monkeypatch.setattr(kp, "fetch_kp", lambda: raw)


def test_sync_writes_kp_after_weather(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    with_weather(monkeypatch)
    with_kp(monkeypatch)
    runner.invoke(main.app, ["sync", "--days", "1"])
    assert rows(isolated, "SELECT COUNT(*) FROM kp_index")[0][0] == 81
    kinds = [r["kind"] for r in sync_log(isolated)]
    assert kinds.index("kp") > kinds.index("weather")


def test_sync_calendar_also_writes_kp(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", no_garmin)
    use_calendar(monkeypatch, FakeCalendar())
    with_kp(monkeypatch)
    runner.invoke(main.app, ["sync", "--calendar"])
    assert rows(isolated, "SELECT COUNT(*) FROM kp_index")[0][0] == 81
    assert rows(isolated, "SELECT status FROM sync_log WHERE kind = 'kp'") == [("ok",)]


def test_kp_success_adds_no_line_to_output(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    with_weather(monkeypatch)
    result = runner.invoke(main.app, ["sync", "--days", "1"])
    with_kp(monkeypatch)
    with_kp_result = runner.invoke(main.app, ["sync", "--days", "1"])
    assert len(with_kp_result.output.splitlines()) == len(result.output.splitlines())
    assert with_kp_result.output.splitlines()[-1] == "погода: записана, +4°"
    lowered = with_kp_result.output.lower()
    assert "kp" not in lowered
    assert "бур" not in lowered


def test_kp_failure_adds_no_line_and_keeps_exit_code_0(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    with_weather(monkeypatch)
    result = runner.invoke(main.app, ["sync", "--days", "1"])
    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == "погода: записана, +4°"
    assert "kp" not in result.output.lower()
    assert "Traceback" not in result.output
    assert rows(isolated, "SELECT status FROM sync_log WHERE kind = 'kp'") == [("error",)]


def test_kp_runs_after_garmin_error_and_exit_stays_1(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_tokens(*a: object, **k: object) -> None:
        raise GarminAuthError("Токенов Garmin нет. Выполни: coach login")

    monkeypatch.setattr(main, "load_client", no_tokens)
    use_calendar(monkeypatch, FakeCalendar())
    with_kp(monkeypatch)
    result = runner.invoke(main.app, ["sync"])
    assert result.exit_code == 1
    assert rows(isolated, "SELECT COUNT(*) FROM kp_index")[0][0] == 81


def test_kp_does_not_add_sync_run(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    use_calendar(monkeypatch, FakeCalendar())
    with_kp(monkeypatch)
    runner.invoke(main.app, ["sync", "--days", "1"])
    assert [r["kind"] for r in sync_log(isolated)].count("sync") == 1


def test_sync_window_edge_uses_days_option(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: FakeGarmin())
    calendar = FakeCalendar()
    use_calendar(monkeypatch, calendar)
    runner.invoke(main.app, ["sync", "--days", "3"])
    assert calendar.calls == [(TODAY - timedelta(days=3), TODAY + timedelta(days=14))]
