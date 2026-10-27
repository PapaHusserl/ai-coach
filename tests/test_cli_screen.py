"""coach screen [--days N]: экранное время из ActivityWatch в day_counters (шаг v2.8).

Только экран: Garmin и sync_log не трогаются. Читатель подменён FakeAw, сеть не нужна.
"""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from garmin_fakes import sync_log
from typer.testing import CliRunner
from workload_fakes import FakeAw, write_config

from ai_coach.cli import main
from ai_coach.store.db import open_db
from ai_coach.store.journal import add_sync_log, last_sync_log, sync_runs_on
from ai_coach.workload.screen import ScreenError

runner = CliRunner()
HOUR = 3600
SCREEN = '[screen]\nwork = ["Alpha Editor"]\nhobby = ["BetaGame"]\nbrowser = ["Gamma Browser"]\n'


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_garmin(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("screen не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_garmin)
    paths = f'[paths]\ntodo = "{tmp_path / "no-todo.json"}"\nhb_watch = "{tmp_path / "no-hb"}"\n'
    config = write_config(tmp_path / "w.toml", paths + SCREEN)
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))
    return db


def use_aw(monkeypatch: pytest.MonkeyPatch, aw: FakeAw) -> FakeAw:
    monkeypatch.setattr(main, "AwReader", lambda config: aw)
    return aw


def day_of(work: float = 3.0, hobby: float = 1.0, evening: float = 1.0) -> Any:
    whole = {
        ("alpha editor", ""): work * HOUR,
        ("betagame", ""): hobby * HOUR,
        ("gamma browser", ""): 0.25 * HOUR,
    }
    return whole, {("alpha editor", ""): evening * HOUR}


def counters(db: Path) -> dict[tuple[str, str], tuple[float, str]]:
    conn = sqlite3.connect(db)
    try:
        sql = "SELECT date, kind, value, source FROM day_counters"
        return {(d, k): (v, s) for d, k, v, s in conn.execute(sql)}
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


def test_screen_writes_counters_for_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    use_aw(monkeypatch, FakeAw({"2026-10-11": day_of()}))
    result = runner.invoke(main.app, ["screen"])
    assert result.exit_code == 0
    assert counters(isolated) == {
        ("2026-10-11", "screen_work_hours"): (3.0, "screen"),
        ("2026-10-11", "screen_hobby_hours"): (1.0, "screen"),
        ("2026-10-11", "screen_browser_hours"): (0.25, "screen"),
        ("2026-10-11", "screen_evening_hours"): (1.0, "screen"),
    }


def test_screen_prints_hours_by_category(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    use_aw(monkeypatch, FakeAw({"2026-10-11": day_of()}))
    result = runner.invoke(main.app, ["screen"])
    assert "2026-10-11" in result.output
    assert "работа 3.0" in result.output
    assert "хобби 1.0" in result.output
    assert "браузер 0.25" in result.output


def test_screen_after_midnight_goes_to_yesterday(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 01:00:00")
    aw = use_aw(monkeypatch, FakeAw({"2026-10-10": day_of()}))
    result = runner.invoke(main.app, ["screen"])
    assert result.exit_code == 0
    assert {d for d, _ in counters(isolated)} == {"2026-10-10"}
    assert aw.calls[0][0][0].date().isoformat() == "2026-10-10"
    assert "2026-10-10" in result.output


def test_screen_at_0400_goes_to_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 04:00:00")
    use_aw(monkeypatch, FakeAw({"2026-10-11": day_of()}))
    runner.invoke(main.app, ["screen"])
    assert {d for d, _ in counters(isolated)} == {"2026-10-11"}


def test_screen_default_is_one_day(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    aw = use_aw(monkeypatch, FakeAw())
    runner.invoke(main.app, ["screen"])
    assert len(aw.calls) == 1
    assert len(aw.calls[0]) == 2


def test_screen_repeated_run_replaces_values(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    use_aw(monkeypatch, FakeAw({"2026-10-11": day_of(work=2.0)}))
    runner.invoke(main.app, ["screen"])
    use_aw(monkeypatch, FakeAw({"2026-10-11": day_of(work=4.5)}))
    runner.invoke(main.app, ["screen"])
    found = counters(isolated)
    assert found[("2026-10-11", "screen_work_hours")] == (4.5, "screen")
    assert len(found) == 4


def test_screen_days_writes_all_days_prints_only_today(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    aw = use_aw(
        monkeypatch,
        FakeAw(
            {
                "2026-10-09": day_of(work=1.0),
                "2026-10-10": day_of(work=2.0),
                "2026-10-11": day_of(work=3.0),
            }
        ),
    )
    result = runner.invoke(main.app, ["screen", "--days", "3"])
    assert result.exit_code == 0
    assert len(aw.calls[0]) == 6
    assert {d for d, _ in counters(isolated)} == {"2026-10-09", "2026-10-10", "2026-10-11"}
    assert "работа 3.0" in result.output
    assert "2026-10-10" not in result.output
    assert "2026-10-09" not in result.output


@pytest.mark.parametrize("days", ["0", "-1"])
def test_screen_days_below_one_is_usage_error(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, days: str
) -> None:
    aw = use_aw(monkeypatch, FakeAw())
    result = runner.invoke(main.app, ["screen", "--days", days])
    assert result.exit_code == 2
    assert aw.calls == []
    assert counters(isolated) == {}


def test_screen_day_without_window_events_writes_nothing_and_exits_0(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    use_aw(monkeypatch, FakeAw())
    result = runner.invoke(main.app, ["screen"])
    assert result.exit_code == 0
    assert counters(isolated) == {}
    assert "Traceback" not in result.output


def test_screen_aw_down_is_one_line_and_exit_1(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    use_aw(monkeypatch, FakeAw(error=ScreenError("aw-server не отвечает - запущен ли AW?")))
    result = runner.invoke(main.app, ["screen"])
    assert result.exit_code == 1
    assert "aw-server не отвечает" in result.output
    assert len(result.output.strip().splitlines()) == 1
    assert "Traceback" not in result.output
    assert counters(isolated) == {}


def test_screen_without_screen_section_is_exit_1(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = write_config(tmp_path / "no-screen.toml", '[calendar]\nwork = ["Work"]\n')
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))
    aw = use_aw(monkeypatch, FakeAw({"2026-10-11": day_of()}))
    result = runner.invoke(main.app, ["screen"])
    assert result.exit_code == 1
    assert len(result.output.strip().splitlines()) == 1
    assert "[screen]" in result.output
    assert aw.calls == []
    assert counters(isolated) == {}


def test_screen_with_broken_config_is_exit_1_without_traceback(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = write_config(tmp_path / "broken.toml", "[screen\nwork = ")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))
    result = runner.invoke(main.app, ["screen"])
    assert result.exit_code == 1
    assert "Traceback" not in result.output


def seed_sync_log(db: Path) -> None:
    conn = open_db(db)
    try:
        with conn:
            add_sync_log(
                conn, {"started_at": "2026-10-11 08:00:00", "kind": "sync", "status": "ok"}
            )
    finally:
        conn.close()


def test_screen_does_not_touch_sync_log(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    seed_sync_log(isolated)
    before = sync_log(isolated)
    use_aw(monkeypatch, FakeAw({"2026-10-11": day_of()}))
    runner.invoke(main.app, ["screen"])
    runner.invoke(main.app, ["screen"])
    assert sync_log(isolated) == before
    conn = open_db(isolated)
    try:
        assert sync_runs_on(conn, "2026-10-11") == 1
        last = last_sync_log(conn)
        assert last is not None
        assert last["kind"] == "sync"
    finally:
        conn.close()


def test_failed_screen_does_not_touch_sync_log(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    seed_sync_log(isolated)
    before = sync_log(isolated)
    use_aw(monkeypatch, FakeAw(error=ScreenError("нет")))
    runner.invoke(main.app, ["screen"])
    assert sync_log(isolated) == before
