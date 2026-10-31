"""coach pvt (тест реакции) и coach log pvt: таблица pvt_log."""

import json
import sqlite3
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.cli import pvt as pvt_cli

runner = CliRunner()
TODAY = "2026-10-14"
TRIALS: list[int | None] = [250, 300, 400, None]


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("pvt не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


@pytest.fixture
def noon(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")


@pytest.fixture
def tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Терминал есть, клавиатура и тест - фейки (run_test отдаёт TRIALS)."""
    fake_sys = SimpleNamespace(stdin=SimpleNamespace(isatty=lambda: True, fileno=lambda: 0))
    monkeypatch.setattr(pvt_cli, "sys", fake_sys)
    monkeypatch.setattr(pvt_cli, "cbreak", lambda fd: nullcontext())
    monkeypatch.setattr(pvt_cli, "terminal_wait_key", lambda *a, **k: True)
    monkeypatch.setattr(pvt_cli, "run_test", lambda *a, **k: list(TRIALS))


def pvt_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM pvt_log ORDER BY id").fetchall()
    finally:
        conn.close()


def insert(db: Path, day: str, rts: str = "[250, 300, 400, null]", **over: Any) -> None:
    values: dict[str, Any] = {
        "date": day,
        "started_at": f"{day} 09:30:00",
        "duration_s": 180,
        "trials": 4,
        "false_starts": 1,
        "lapses": 1,
        "mean_rt_ms": 317,
        "median_rt_ms": 300,
        "slow10_ms": 400,
        "speed": 3.28,
        "rts": rts,
    }
    values.update(over)
    conn = sqlite3.connect(db)
    conn.execute(
        f"INSERT INTO pvt_log ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})",
        tuple(values.values()),
    )
    conn.commit()
    conn.close()


def test_not_a_terminal_fails_and_saves_nothing(isolated: Path) -> None:
    result = runner.invoke(main.app, ["pvt"])
    assert result.exit_code == 1
    assert "только в терминале" in result.output
    assert pvt_rows(isolated) == []


@pytest.mark.usefixtures("tty", "noon")
def test_pvt_writes_one_row(isolated: Path) -> None:
    result = runner.invoke(main.app, ["pvt"])
    assert result.exit_code == 0
    (row,) = pvt_rows(isolated)
    assert (row["date"], row["started_at"], row["duration_s"]) == (
        TODAY,
        f"{TODAY} 12:00:00",
        180,
    )
    assert (row["trials"], row["false_starts"], row["lapses"]) == (4, 1, 1)
    assert (row["mean_rt_ms"], row["median_rt_ms"], row["slow10_ms"], row["speed"]) == (
        317,
        300,
        400,
        3.28,
    )
    assert json.loads(row["rts"]) == TRIALS


@pytest.mark.usefixtures("tty", "noon")
def test_pvt_output_ends_with_summary_and_saved(isolated: Path) -> None:
    output = runner.invoke(main.app, ["pvt"]).output
    assert output.rstrip().endswith(
        "медиана 300 мс, среднее 317, медленные 10 % 400, скорость 3,28/с, "
        "провалы 1, фальстарты 1 (проб 4) - записано."
    )


@pytest.mark.usefixtures("tty")
def test_pvt_at_0359_goes_to_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-15 03:59:00")
    runner.invoke(main.app, ["pvt"])
    assert pvt_rows(isolated)[0]["date"] == TODAY


@pytest.mark.usefixtures("tty")
def test_pvt_at_0400_goes_to_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-15 04:00:00")
    runner.invoke(main.app, ["pvt"])
    assert pvt_rows(isolated)[0]["date"] == "2026-10-15"


@pytest.mark.usefixtures("tty", "noon")
def test_pvt_interrupt_in_test_saves_nothing(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(*args: Any, **kwargs: Any) -> list[int | None]:
        raise KeyboardInterrupt

    monkeypatch.setattr(pvt_cli, "run_test", interrupted)
    result = runner.invoke(main.app, ["pvt"])
    assert result.exit_code == 1
    assert "Прервано, не записано" in result.output
    assert pvt_rows(isolated) == []


@pytest.mark.usefixtures("tty", "noon")
def test_pvt_interrupt_at_start_key_saves_nothing(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(*args: Any, **kwargs: Any) -> bool:
        raise KeyboardInterrupt

    monkeypatch.setattr(pvt_cli, "terminal_wait_key", interrupted)
    result = runner.invoke(main.app, ["pvt"])
    assert result.exit_code == 1
    assert "Прервано, не записано" in result.output
    assert pvt_rows(isolated) == []


def test_log_pvt_without_entries(isolated: Path) -> None:
    result = runner.invoke(main.app, ["log", "pvt"])
    assert result.exit_code == 0
    assert "Записей нет." in result.output


@pytest.mark.usefixtures("noon")
def test_log_pvt_shows_row(isolated: Path) -> None:
    runner.invoke(main.app, ["log", "pvt"])  # создаёт базу
    insert(isolated, TODAY)
    lines = runner.invoke(main.app, ["log", "pvt"]).output.splitlines()
    assert lines == [
        f"1  {TODAY} 09:30:00  медиана 300 мс, среднее 317, медленные 10 % 400, "
        "скорость 3,28/с, провалы 1, фальстарты 1 (проб 4)"
    ]


@pytest.mark.usefixtures("noon")
def test_log_pvt_false_starts_only(isolated: Path) -> None:
    runner.invoke(main.app, ["log", "pvt"])
    insert(
        isolated,
        TODAY,
        "[null, null]",
        trials=2,
        false_starts=2,
        lapses=0,
        mean_rt_ms=None,
        median_rt_ms=None,
        slow10_ms=None,
        speed=None,
    )
    output = runner.invoke(main.app, ["log", "pvt"]).output
    assert "нет проб с ответом, фальстарты 2 (проб 2)" in output


@pytest.mark.usefixtures("noon")
def test_log_pvt_filters_by_date(isolated: Path) -> None:
    runner.invoke(main.app, ["log", "pvt"])
    insert(isolated, TODAY)
    insert(isolated, "2026-10-15", median_rt_ms=999)
    output = runner.invoke(main.app, ["log", "pvt", "--date", TODAY]).output
    assert "медиана 300" in output
    assert "999" not in output


def test_log_pvt_bad_date_fails(isolated: Path) -> None:
    assert runner.invoke(main.app, ["log", "pvt", "--date", "вчера"]).exit_code != 0
