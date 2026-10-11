"""get_habits и get_habit_log: привычки и журнал отметок (только чтение)."""

import sqlite3
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, db_file, rows, tool_names
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()


@pytest.fixture(autouse=True)
def cli_env(conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_COACH_DB", db_file(conn))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))


def coach(*args: str) -> None:
    assert runner.invoke(main.app, list(args)).exit_code == 0


def log(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    return rows(conn, "get_habit_log", date_from=start, date_to=end)


def test_tools_exist(conn: sqlite3.Connection) -> None:
    assert {"get_habits", "get_habit_log"} <= tool_names(conn)


# --- get_habits ---


def test_get_habits_on_empty_database(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_habits") == {"rows": [], "truncated": False}


def test_get_habits_row_has_id_name_unit(conn: sqlite3.Connection) -> None:
    coach("habit", "add", "вода", "--unit", "стаканов")
    coach("habit", "add", "зарядка")
    found = {r["name"]: r for r in rows(conn, "get_habits")}
    assert found["вода"]["unit"] == "стаканов"
    assert found["зарядка"]["unit"] is None
    assert isinstance(found["вода"]["id"], int)


def test_get_habits_hides_deleted(conn: sqlite3.Connection) -> None:
    coach("habit", "add", "вода")
    coach("habit", "add", "зарядка")
    coach("habit", "delete", "вода")
    assert [r["name"] for r in rows(conn, "get_habits")] == ["зарядка"]


def test_get_habits_has_no_service_fields(conn: sqlite3.Connection) -> None:
    coach("habit", "add", "вода")
    text = call_text(conn, "get_habits")
    assert "deleted_at" not in text
    assert "created_at" not in text


def test_get_habits_is_capped(conn: sqlite3.Connection) -> None:
    for number in range(100):
        coach("habit", "add", f"привычка {number}")
    result = call(conn, "get_habits")
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60


# --- get_habit_log ---


def test_get_habit_log_on_empty_database(conn: sqlite3.Connection) -> None:
    assert log(conn, "2026-10-01", "2026-10-31") == []


def test_get_habit_log_row_fields(conn: sqlite3.Connection) -> None:
    coach("habit", "add", "вода", "--unit", "стаканов")
    coach("habit", "done", "вода", "6", "--date", "2026-10-10")
    row = log(conn, "2026-10-10", "2026-10-10")[0]
    assert (row["date"], row["name"], row["unit"]) == ("2026-10-10", "вода", "стаканов")
    assert (row["done"], row["amount"]) == (1, 6)
    assert isinstance(row["habit_id"], int)


def test_get_habit_log_shows_no_as_zero(conn: sqlite3.Connection) -> None:
    coach("habit", "add", "зарядка")
    coach("habit", "done", "зарядка", "--no", "--date", "2026-10-10")
    row = log(conn, "2026-10-10", "2026-10-10")[0]
    assert (row["done"], row["amount"]) == (0, None)


def test_get_habit_log_period_is_inclusive_and_cuts_outside(conn: sqlite3.Connection) -> None:
    coach("habit", "add", "зарядка")
    for day in ("2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"):
        coach("habit", "done", "зарядка", "--date", day)
    found = [r["date"] for r in log(conn, "2026-10-09", "2026-10-10")]
    assert sorted(found) == ["2026-10-09", "2026-10-10"]


def test_get_habit_log_has_no_unmarked_days(conn: sqlite3.Connection) -> None:
    coach("habit", "add", "зарядка")
    coach("habit", "done", "зарядка", "--date", "2026-10-10")
    assert len(log(conn, "2026-10-01", "2026-10-31")) == 1


def test_get_habit_log_covers_several_habits(conn: sqlite3.Connection) -> None:
    coach("habit", "add", "вода")
    coach("habit", "add", "зарядка")
    coach("habit", "done", "вода", "--date", "2026-10-10")
    coach("habit", "done", "зарядка", "--date", "2026-10-10")
    assert {r["name"] for r in log(conn, "2026-10-10", "2026-10-10")} == {"вода", "зарядка"}


def test_get_habit_log_end_before_start_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="Конец периода раньше начала."):
        call(conn, "get_habit_log", date_from="2026-10-10", date_to="2026-10-09")


def test_get_habit_log_bad_date_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        call(conn, "get_habit_log", date_from="вчера", date_to="2026-10-09")


def test_get_habit_log_period_over_92_days_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="Период не больше 92 дней."):
        call(conn, "get_habit_log", date_from="2026-01-01", date_to="2026-06-01")


def test_get_habit_log_is_capped(conn: sqlite3.Connection) -> None:
    for number in range(70):
        coach("habit", "add", f"привычка {number}")
        coach("habit", "done", f"привычка {number}", "--date", "2026-10-10")
    result = call(conn, "get_habit_log", date_from="2026-10-10", date_to="2026-10-10")
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60
