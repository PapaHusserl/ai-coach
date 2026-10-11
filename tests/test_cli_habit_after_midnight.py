"""Дата отметки привычки - день самочувствия: до 04:00 это вчера, как у coach feel."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("habit не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def log_dates(db: Path) -> list[str]:
    conn = sqlite3.connect(db)
    try:
        return [r[0] for r in conn.execute("SELECT date FROM habit_log WHERE done = 1")]
    finally:
        conn.close()


@pytest.fixture
def habit_exists(isolated: Path) -> None:
    assert run("habit", "add", "зарядка").exit_code == 0


@pytest.mark.usefixtures("habit_exists")
@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        ("2026-10-11 03:59:00", "2026-10-10"),
        ("2026-10-11 04:00:00", "2026-10-11"),
        ("2026-10-11 00:00:00", "2026-10-10"),
        ("2026-10-11 01:51:00", "2026-10-10"),
        ("2026-10-11 23:59:00", "2026-10-11"),
        ("2026-11-01 02:00:00", "2026-10-31"),
        ("2026-01-01 00:30:00", "2025-12-31"),
    ],
)
def test_done_date_follows_cutoff(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, moment: str, expected: str
) -> None:
    freeze(monkeypatch, moment)
    assert run("habit", "done", "зарядка").exit_code == 0
    assert log_dates(isolated) == [expected]


@pytest.mark.usefixtures("habit_exists")
def test_undo_after_midnight_removes_yesterdays_mark(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("habit", "done", "зарядка", "--date", "2026-10-10").exit_code == 0
    freeze(monkeypatch, "2026-10-11 01:00:00")
    assert run("habit", "undo", "зарядка").exit_code == 0
    assert log_dates(isolated) == []


@pytest.mark.usefixtures("habit_exists")
def test_undo_after_midnight_keeps_calendar_todays_mark(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("habit", "done", "зарядка", "--date", "2026-10-11").exit_code == 0
    freeze(monkeypatch, "2026-10-11 01:00:00")
    assert run("habit", "undo", "зарядка").exit_code == 1
    assert log_dates(isolated) == ["2026-10-11"]
