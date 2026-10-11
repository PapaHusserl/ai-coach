"""Snapshot: habits_today - активные привычки с отметкой за день самочувствия (до 04:00 - вчера)."""

import json
import sqlite3
from pathlib import Path

import pytest
from fake_clock import freeze
from mcp_fakes import call, call_text, db_file
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.mcp_server.tools import MAX_CHARS

runner = CliRunner()
TODAY = "2026-10-11"
YESTERDAY = "2026-10-10"


@pytest.fixture(autouse=True)
def cli_env(conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_COACH_DB", db_file(conn))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))


def coach(*args: str) -> None:
    assert runner.invoke(main.app, list(args)).exit_code == 0


def habits_today(conn: sqlite3.Connection, day: str = TODAY) -> dict:
    return call(conn, "get_morning_snapshot", date=day)["habits_today"]


def by_name(conn: sqlite3.Connection, day: str = TODAY) -> dict[str, dict]:
    return {r["name"]: r for r in habits_today(conn, day)["rows"]}


def test_empty_without_habits(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    assert habits_today(conn)["rows"] == []


def test_unmarked_habit_is_listed_as_not_done(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    coach("habit", "add", "зарядка")
    row = by_name(conn)["зарядка"]
    assert row["done"] is None
    assert row.get("amount") is None


def test_done_habit_has_done_and_amount(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    coach("habit", "add", "вода", "--unit", "стаканов")
    coach("habit", "add", "зарядка")
    coach("habit", "done", "вода", "6")
    found = by_name(conn)
    assert found["вода"]["done"] is True
    assert found["вода"]["amount"] == 6
    assert found["вода"]["unit"] == "стаканов"
    assert found["зарядка"]["done"] is None


def test_no_mark_is_false_not_null(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    coach("habit", "add", "зарядка")
    coach("habit", "add", "вода")
    coach("habit", "done", "зарядка", "--no")
    found = by_name(conn)
    assert found["зарядка"]["done"] is False
    assert found["вода"]["done"] is None


def test_done_no_and_unmarked_are_three_different_states(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    for name in ("а-привычка", "б-привычка", "в-привычка"):
        coach("habit", "add", name)
    coach("habit", "done", "а-привычка")
    coach("habit", "done", "б-привычка", "--no")
    found = by_name(conn)
    assert [found[n]["done"] for n in ("а-привычка", "б-привычка", "в-привычка")] == [
        True,
        False,
        None,
    ]


def test_undone_habit_is_not_done(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    coach("habit", "add", "зарядка")
    coach("habit", "done", "зарядка")
    coach("habit", "undo", "зарядка")
    assert by_name(conn)["зарядка"]["done"] is None


def test_deleted_habit_is_not_listed(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    coach("habit", "add", "вода")
    coach("habit", "add", "зарядка")
    coach("habit", "done", "вода")
    coach("habit", "delete", "вода")
    assert list(by_name(conn)) == ["зарядка"]


def test_yesterdays_mark_is_not_todays(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    coach("habit", "add", "зарядка")
    coach("habit", "done", "зарядка", "--date", YESTERDAY)
    assert by_name(conn)["зарядка"]["done"] is None


def test_past_date_shows_marks_of_that_date(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    coach("habit", "add", "зарядка")
    coach("habit", "done", "зарядка", "--date", YESTERDAY)
    assert by_name(conn, YESTERDAY)["зарядка"]["done"] is True


def test_at_0100_snapshot_shows_yesterdays_evening(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 01:00:00")
    coach("habit", "add", "зарядка")
    coach("habit", "done", "зарядка", "--date", YESTERDAY)
    assert by_name(conn)["зарядка"]["done"] is True


def test_at_0400_snapshot_shows_the_new_day(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 04:00:00")
    coach("habit", "add", "зарядка")
    coach("habit", "done", "зарядка", "--date", YESTERDAY)
    assert by_name(conn)["зарядка"]["done"] is None


def test_snapshot_habits_have_no_service_fields(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    coach("habit", "add", "зарядка")
    text = json.dumps(habits_today(conn), ensure_ascii=False)
    assert "deleted_at" not in text
    assert "created_at" not in text


def test_snapshot_stays_in_limit_with_many_habits(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    big = "я" * 200
    for number in range(80):
        coach("habit", "add", f"привычка {number} {big}")
    text = call_text(conn, "get_morning_snapshot", date=TODAY)
    assert len(text) <= MAX_CHARS
    assert "habits_today" in json.loads(text)
