import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
DAY = "2026-10-08"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def add_med(name: str, schedule: str) -> None:
    result = run(
        *("med", "add", name, "--kind", "vitamin", "--dose", "1", "--unit", "g"),
        *("--schedule", schedule, "--start", "2026-10-01"),
    )
    assert result.exit_code == 0


def add_workout(db: Path, status: str) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO planned_workouts (date, sport, name, workout_json, status) "
        "VALUES (?, 'run', 'т', ?, ?)",
        (DAY, json.dumps({}), status),
    )
    conn.commit()
    conn.close()


def test_list_date_hides_training_course_without_training(isolated: Path) -> None:
    add_med("дейли", "daily")
    add_med("после", "after")
    out = run("med", "list", "--date", DAY).output
    assert "дейли" in out
    assert "после" not in out


def test_list_date_shows_training_course_with_training(isolated: Path) -> None:
    add_med("дейли", "daily")
    add_med("после", "after")
    add_workout(isolated, "approved")
    out = run("med", "list", "--date", DAY).output
    assert "дейли" in out
    assert "после" in out


def test_list_date_hides_training_course_with_only_cancelled(isolated: Path) -> None:
    add_med("после", "training_day")
    add_workout(isolated, "cancelled")
    assert "после" not in run("med", "list", "--date", DAY).output


def test_list_all_shows_training_course_without_training(isolated: Path) -> None:
    add_med("после", "before")
    assert "после" in run("med", "list", "--all").output


def test_list_default_hides_training_course_without_training(isolated: Path) -> None:
    add_med("дейли", "daily")
    add_med("после", "after")
    out = run("med", "list").output
    assert "дейли" in out
    assert "после" not in out
