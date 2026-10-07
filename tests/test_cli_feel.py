import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """База — во временной папке; Garmin и сеть недоступны."""
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("feel не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM wellbeing_log ORDER BY id").fetchall()
    finally:
        conn.close()


def test_score_is_saved(isolated: Path) -> None:
    result = runner.invoke(main.app, ["feel", "4"])
    assert result.exit_code == 0
    assert [r["score"] for r in rows(isolated)] == [4]


def test_text_is_optional(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "4"])
    assert rows(isolated)[0]["text"] in (None, "")


def test_text_is_saved(isolated: Path) -> None:
    result = runner.invoke(main.app, ["feel", "2", "плохо спал, болит спина"])
    assert result.exit_code == 0
    row = rows(isolated)[0]
    assert (row["score"], row["text"]) == (2, "плохо спал, болит спина")


def test_saved_with_todays_date_and_time(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3"])
    row = rows(isolated)[0]
    assert row["date"] == date.today().isoformat()
    assert row["logged_at"].startswith(date.today().isoformat())


def test_two_scores_in_a_day_are_two_rows(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "4"])
    runner.invoke(main.app, ["feel", "2", "после тренировки"])
    assert [r["score"] for r in rows(isolated)] == [4, 2]


@pytest.mark.parametrize("value", ["1", "5"])
def test_limits_are_inclusive(isolated: Path, value: str) -> None:
    assert runner.invoke(main.app, ["feel", value]).exit_code == 0


@pytest.mark.parametrize("value", ["0", "6", "-1", "3.5", "abc", "", "nan", "100"])
def test_bad_score_is_rejected_and_not_saved(isolated: Path, value: str) -> None:
    result = runner.invoke(main.app, ["feel", value])
    assert result.exit_code != 0
    assert rows(isolated) == []


def test_feel_without_score_is_rejected(isolated: Path) -> None:
    result = runner.invoke(main.app, ["feel"])
    assert result.exit_code != 0
    assert rows(isolated) == []
