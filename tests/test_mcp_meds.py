import sqlite3

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, rows, tool_names

from ai_coach.store.meds import add_med, delete_med

DAY = "2026-10-08"
NOW = "2026-10-08 10:00:00"
SNAPSHOT_MEDS_ROWS = 10


def new_med(conn: sqlite3.Connection, name: str = "витамин D", **fields: object) -> int:
    base = {
        "name": name,
        "kind": "vitamin",
        "dose": 25.0,
        "unit": "mcg",
        "schedule": "daily",
        "time_note": "с едой",
        "start_date": "2026-10-01",
        "end_date": None,
        "note": "SECRET_NOTE",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return add_med(conn, {**base, **fields})


# --- get_meds ---


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_meds" in tool_names(conn)


def test_get_on_empty_database(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_meds") == {"rows": [], "truncated": False}


def test_get_without_date_returns_all_alive_courses(conn: sqlite3.Connection) -> None:
    new_med(conn, "текущий")
    new_med(conn, "закончен", start_date="2026-08-01", end_date="2026-08-31")
    gone = new_med(conn, "удалённый")
    delete_med(conn, gone, "2026-10-08 12:00:00")
    assert sorted(r["name"] for r in rows(conn, "get_meds")) == ["закончен", "текущий"]


def test_get_row_has_fields(conn: sqlite3.Connection) -> None:
    mid = new_med(conn, end_date="2026-10-31")
    row = rows(conn, "get_meds")[0]
    assert (row["id"], row["name"], row["kind"], row["dose"], row["unit"]) == (
        mid,
        "витамин D",
        "vitamin",
        25.0,
        "mcg",
    )
    assert (row["schedule"], row["start_date"], row["end_date"]) == (
        "daily",
        "2026-10-01",
        "2026-10-31",
    )
    assert row["time_note"] == "с едой"


def test_get_has_no_service_fields(conn: sqlite3.Connection) -> None:
    new_med(conn)
    text = call_text(conn, "get_meds")
    assert "deleted_at" not in text
    assert "created_at" not in text


def test_get_with_date_filters_by_borders(conn: sqlite3.Connection) -> None:
    new_med(conn, "курс", start_date="2026-10-05", end_date="2026-10-10")
    assert [r["name"] for r in rows(conn, "get_meds", date="2026-10-05")] == ["курс"]
    assert [r["name"] for r in rows(conn, "get_meds", date="2026-10-10")] == ["курс"]
    assert rows(conn, "get_meds", date="2026-10-04") == []
    assert rows(conn, "get_meds", date="2026-10-11") == []


def test_get_with_date_includes_open_ended_course(conn: sqlite3.Connection) -> None:
    new_med(conn, "бессрочный")
    assert [r["name"] for r in rows(conn, "get_meds", date="2099-01-01")] == ["бессрочный"]


def test_get_bad_date_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        call(conn, "get_meds", date="08.10.2026")


@pytest.mark.parametrize("date", [None, DAY])
def test_get_is_capped(conn: sqlite3.Connection, date: str | None) -> None:
    for number in range(100):
        new_med(conn, f"курс {number}")
    result = call(conn, "get_meds") if date is None else call(conn, "get_meds", date=date)
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60


# --- snapshot ---


def snapshot(conn: sqlite3.Connection) -> dict:
    return call(conn, "get_morning_snapshot", date=DAY)


def test_snapshot_without_courses_has_no_meds_today(conn: sqlite3.Connection) -> None:
    assert "meds_today" not in snapshot(conn)


def test_snapshot_without_active_courses_has_no_meds_today(conn: sqlite3.Connection) -> None:
    new_med(conn, "закончен", start_date="2026-08-01", end_date="2026-10-07")
    new_med(conn, "будущий", start_date="2026-10-09")
    gone = new_med(conn, "удалённый")
    delete_med(conn, gone, "2026-10-08 12:00:00")
    assert "meds_today" not in snapshot(conn)


def test_snapshot_has_course_on_border_days(conn: sqlite3.Connection) -> None:
    new_med(conn, "с сегодня", start_date=DAY)
    new_med(conn, "по сегодня", start_date="2026-10-01", end_date=DAY)
    names = [r["name"] for r in snapshot(conn)["meds_today"]["rows"]]
    assert sorted(names) == ["по сегодня", "с сегодня"]


def test_snapshot_meds_are_compact_without_notes(conn: sqlite3.Connection) -> None:
    new_med(conn)
    part = snapshot(conn)["meds_today"]
    row = part["rows"][0]
    assert (row["name"], row["dose"], row["unit"], row["schedule"]) == (
        "витамин D",
        25.0,
        "mcg",
        "daily",
    )
    assert part["truncated"] is False
    text = str(part)
    assert "SECRET_NOTE" not in text
    assert "note" not in row
    assert "deleted_at" not in text
    assert "created_at" not in text


def test_snapshot_has_at_most_10_rows(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_MEDS_ROWS + 10):
        new_med(conn, f"курс {number}")
    part = snapshot(conn)["meds_today"]
    assert len(part["rows"]) <= SNAPSHOT_MEDS_ROWS
    assert part["truncated"] is True
