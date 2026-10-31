"""MCP create_day_plan (шаг Н13): ответ, параметры, отказы."""

import ast
import sqlite3
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, tool_names

import ai_coach.agenda.day_plan as day_plan_module
import ai_coach.agenda.slots as slots_module

DAY = "2026-11-02"  # понедельник; «сегодня» в тестах - воскресенье 2026-11-01


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai_coach.mcp_server.tools.now", lambda: datetime(2026, 11, 1, 9, 0))


def plan(conn: sqlite3.Connection, **fields: Any) -> Any:
    return call(conn, "create_day_plan", **({"date": DAY} | fields))


def test_tool_is_registered(conn: sqlite3.Connection) -> None:
    assert "create_day_plan" in tool_names(conn)


def test_response_shape(conn: sqlite3.Connection) -> None:
    result = plan(conn, tasks=[{"title": "Отчёт", "minutes": 60, "category": "work"}])
    assert set(result) == {"date", "drafts", "skipped", "busy"}
    assert result["date"] == DAY
    assert result["drafts"]
    for draft in result["drafts"]:
        assert set(draft) == {"draft_id", "kind", "title", "start_at", "end_at", "category"}


def test_drafts_are_stored_as_drafts(conn: sqlite3.Connection) -> None:
    result = plan(conn)
    ids = {d["draft_id"] for d in result["drafts"]}
    rows = conn.execute("SELECT id, status FROM coach_events").fetchall()
    assert {r["id"] for r in rows} == ids
    assert {r["status"] for r in rows} == {"draft"}


def test_second_call_is_already_planned(conn: sqlite3.Connection) -> None:
    first = plan(conn)
    again = plan(conn)
    assert "drafts" not in again
    assert set(again["already_planned"]) <= {d["draft_id"] for d in first["drafts"]}
    assert again["already_planned"]
    assert conn.execute("SELECT COUNT(*) FROM coach_events").fetchone()[0] == len(first["drafts"])


def test_day_start_moves_first_block(conn: sqlite3.Connection) -> None:
    result = plan(
        conn, day_start="12:00", tasks=[{"title": "Т", "minutes": 30, "category": "work"}]
    )
    assert min(d["start_at"] for d in result["drafts"]) >= f"{DAY}T12:00"


def test_day_end_midnight_equals_default(conn: sqlite3.Connection) -> None:
    default = plan(conn)["drafts"]
    conn.execute("DELETE FROM coach_events")
    explicit = plan(conn, day_end="00:00")["drafts"]
    key = [(d["kind"], d["start_at"], d["end_at"]) for d in default]
    assert [(d["kind"], d["start_at"], d["end_at"]) for d in explicit] == key


def test_day_end_limits_blocks(conn: sqlite3.Connection) -> None:
    result = plan(conn, day_end="22:00", tasks=[{"title": "Т", "minutes": 30, "category": "work"}])
    assert result["drafts"]
    assert all(d["end_at"] <= f"{DAY}T22:00" for d in result["drafts"])


def test_meal_times_are_taken_from_arguments(conn: sqlite3.Connection) -> None:
    result = plan(conn, dinner_at="20:00", snack_at="16:00")
    by_title = {d["title"]: d for d in result["drafts"]}
    assert (by_title["Ужин"]["start_at"], by_title["Ужин"]["end_at"]) == (
        f"{DAY}T20:00",
        f"{DAY}T21:00",
    )
    assert (by_title["Перекус"]["start_at"], by_title["Перекус"]["end_at"]) == (
        f"{DAY}T16:00",
        f"{DAY}T16:15",
    )


def test_breakfast_at_is_taken_from_arguments(conn: sqlite3.Connection) -> None:
    result = plan(conn, breakfast_at="12:00")
    assert {d["title"]: d for d in result["drafts"]}["Завтрак"]["start_at"] == f"{DAY}T12:00"


def test_breakfast_defaults_to_frame_of_day(conn: sqlite3.Connection) -> None:
    result = plan(conn)
    assert {d["title"]: d for d in result["drafts"]}["Завтрак"]["start_at"] == f"{DAY}T11:00"


@pytest.mark.parametrize(
    "fields",
    [
        {"date": "2026-10-31"},
        {"date": "2026-11-16"},
        {"date": "завтра"},
        {"day_end": "9:00"},
        {"dinner_at": "20"},
        {"day_start": "12:00", "day_end": "11:00"},
        {"tasks": [{"title": "Т", "minutes": 0}]},
    ],
)
def test_bad_input_is_tool_error_and_writes_nothing(
    conn: sqlite3.Connection, fields: dict[str, Any]
) -> None:
    with pytest.raises(ToolError):
        plan(conn, **fields)
    assert conn.execute("SELECT COUNT(*) FROM coach_events").fetchone()[0] == 0


def test_14_days_ahead_is_allowed(conn: sqlite3.Connection) -> None:
    assert plan(conn, date="2026-11-15")["drafts"]


@pytest.mark.parametrize("module", [day_plan_module, slots_module], ids=lambda m: m.__name__)
def test_day_plan_modules_do_not_import_calendar_writer(module: ModuleType) -> None:
    names: list[str] = []
    for node in ast.walk(ast.parse(Path(module.__file__ or "").read_text())):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    for name in names:
        assert name != "ai_coach.agenda.calendar_write"
        assert "eventkit" not in name.lower()
