"""MCP create_day_plan (шаг Н13): ответ, параметры, отказы."""

import ast
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, tool_names

import ai_coach.agenda.day_layout as day_layout_module
import ai_coach.agenda.day_plan as day_plan_module
import ai_coach.agenda.slots as slots_module
from ai_coach.agenda.day_layout import FOCUS_MAX
from ai_coach.mcp_server.server import TOOLS
from ai_coach.store.garmin_data import upsert_daily_metrics
from ai_coach.store.journal import add_who5

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


def test_weekday_plan_has_ten_drafts_with_two_cooking_meals_and_two_inboxes(
    conn: sqlite3.Connection,
) -> None:
    result = plan(conn)
    assert len(result["drafts"]) == 10
    inbox = [d for d in result["drafts"] if d["title"] == "Инбокс"]
    assert [(d["kind"], d["category"]) for d in inbox] == [("task", "work")] * 2
    cooks = [d for d in result["drafts"] if d["title"] == "Готовка"]
    assert [(c["kind"], c["start_at"], c["end_at"]) for c in cooks] == [
        ("meal", f"{DAY}T10:30", f"{DAY}T11:00"),
        ("meal", f"{DAY}T19:00", f"{DAY}T19:30"),
    ]


def test_tool_description_mentions_cooking() -> None:
    assert "готовк" in TOOLS["create_day_plan"][1]


def test_tool_description_mentions_inbox() -> None:
    assert "Инбокс" in TOOLS["create_day_plan"][1]


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


def illness_base(conn: sqlite3.Connection, out_days: int) -> None:
    """28 дней до «сегодня» (2026-11-01) пульс 50, HRV 60; последние out_days - вне коридора."""
    today = date(2026, 11, 1)
    for number in range(28, -1, -1):
        outlier = number == 20
        out = number < out_days
        rhr, hrv = (90, 10) if out else (60, 70) if outlier else (50, 60)
        upsert_daily_metrics(
            conn,
            {
                "date": (today - timedelta(days=number)).isoformat(),
                "sleep_seconds": 7 * 3600,
                "hrv_last_night": hrv,
                "raw_json": {"sleep": {"restingHeartRate": rhr}},
            },
        )


def test_illness_risk_gives_one_focus_block_and_reason(conn: sqlite3.Connection) -> None:
    illness_base(conn, out_days=2)
    result = plan(conn)
    assert len([d for d in result["drafts"] if d["kind"] == "focus"]) == FOCUS_MAX - 1
    assert [s for s in result["skipped"] if "возможно, заболеваешь" in s]


def test_no_illness_signal_keeps_two_focus_blocks(conn: sqlite3.Connection) -> None:
    illness_base(conn, out_days=1)
    result = plan(conn)
    assert len([d for d in result["drafts"] if d["kind"] == "focus"]) == FOCUS_MAX
    assert not [s for s in result["skipped"] if "заболеваешь" in s]


def who5_low_yesterday(conn: sqlite3.Connection, day: str = "2026-10-31") -> None:
    add_who5(
        conn,
        {
            "date": day,
            "logged_at": f"{day} 09:00:00",
            "q1": 5,
            "q2": 2,
            "q3": 0,
            "q4": 0,
            "q5": 0,
            "score": 28,
        },
    )


def test_who5_low_gives_one_focus_block_and_reason(conn: sqlite3.Connection) -> None:
    who5_low_yesterday(conn)
    result = plan(conn)
    assert len([d for d in result["drafts"] if d["kind"] == "focus"]) == FOCUS_MAX - 1
    assert [s for s in result["skipped"] if "режим щажения (WHO-5 28 из 100" in s]


def test_who5_low_15_days_ago_keeps_two_focus_blocks(conn: sqlite3.Connection) -> None:
    who5_low_yesterday(conn, "2026-10-17")
    result = plan(conn)
    assert len([d for d in result["drafts"] if d["kind"] == "focus"]) == FOCUS_MAX
    assert not [s for s in result["skipped"] if "щажения" in s]


@pytest.mark.parametrize(
    "module", [day_plan_module, day_layout_module, slots_module], ids=lambda m: m.__name__
)
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
