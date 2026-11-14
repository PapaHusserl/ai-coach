"""get_done_log: отметки «сделал / пропустил» пунктов календаря (только чтение)."""

import sqlite3
from datetime import date, timedelta

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, rows, tool_names
from workload_fakes import coach_event

from ai_coach.store.agenda import add_event, mark_done, unmark_done, update_event


def event(conn: sqlite3.Connection, **fields: object) -> int:
    return add_event(conn, coach_event(**fields))


def log(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    return rows(conn, "get_done_log", date_from=start, date_to=end)


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_done_log" in tool_names(conn)


def test_get_done_log_on_empty_database(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_done_log", date_from="2026-10-01", date_to="2026-10-31")
    assert result == {"rows": [], "truncated": False}


def test_get_done_log_row_fields_for_done_and_skipped(conn: sqlite3.Connection) -> None:
    practice = event(conn, kind="practice", title="Растяжка")
    rest = event(conn, kind="rest", title="Выходной")
    mark_done(conn, practice, "2026-10-10", 1, "2026-10-10T21:00:00")
    mark_done(conn, rest, "2026-10-10", 0, "2026-10-10T21:05:00")
    found = {r["title"]: r for r in log(conn, "2026-10-10", "2026-10-10")}
    assert len(found) == 2
    assert (found["Растяжка"]["kind"], found["Растяжка"]["done"]) == ("practice", 1)
    assert (found["Выходной"]["kind"], found["Выходной"]["done"]) == ("rest", 0)
    assert found["Растяжка"]["event_id"] == practice
    assert found["Растяжка"]["date"] == "2026-10-10"
    assert found["Растяжка"]["logged_at"] == "2026-10-10T21:00:00"


def test_get_done_log_repeating_checkin_gives_row_per_day(conn: sqlite3.Connection) -> None:
    checkin = event(conn, kind="checkin", title="Чек-ин", survey="none", repeat="daily")
    mark_done(conn, checkin, "2026-10-10", 1, "2026-10-10T21:00:00")
    mark_done(conn, checkin, "2026-10-11", 1, "2026-10-11T21:00:00")
    found = log(conn, "2026-10-10", "2026-10-11")
    assert [r["event_id"] for r in found] == [checkin, checkin]
    assert sorted(r["date"] for r in found) == ["2026-10-10", "2026-10-11"]


def test_get_done_log_period_is_inclusive_and_cuts_outside(conn: sqlite3.Connection) -> None:
    practice = event(conn, kind="practice")
    for day in ("2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"):
        mark_done(conn, practice, day, 1, f"{day}T21:00:00")
    found = [r["date"] for r in log(conn, "2026-10-09", "2026-10-10")]
    assert sorted(found) == ["2026-10-09", "2026-10-10"]


def test_get_done_log_unmarked_is_gone(conn: sqlite3.Connection) -> None:
    practice = event(conn, kind="practice")
    mark_done(conn, practice, "2026-10-10", 1, "2026-10-10T21:00:00")
    unmark_done(conn, practice, "2026-10-10")
    assert log(conn, "2026-10-10", "2026-10-10") == []


def test_get_done_log_keeps_mark_of_removed_event(conn: sqlite3.Connection) -> None:
    practice = event(conn, kind="practice", title="Растяжка")
    mark_done(conn, practice, "2026-10-10", 1, "2026-10-10T21:00:00")
    update_event(conn, practice, {"status": "removed"})
    assert [r["title"] for r in log(conn, "2026-10-10", "2026-10-10")] == ["Растяжка"]


def test_get_done_log_end_before_start_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="Конец периода раньше начала."):
        call(conn, "get_done_log", date_from="2026-10-10", date_to="2026-10-09")


def test_get_done_log_bad_date_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        call(conn, "get_done_log", date_from="вчера", date_to="2026-10-09")


def test_get_done_log_period_over_92_days_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="Период не больше 92 дней."):
        call(conn, "get_done_log", date_from="2026-01-01", date_to="2026-06-01")


def test_get_done_log_is_capped_and_keeps_newest(conn: sqlite3.Connection) -> None:
    practice = event(conn, kind="practice")
    first = date(2026, 8, 1)
    days = [(first + timedelta(days=n)).isoformat() for n in range(70)]
    for day in days:
        mark_done(conn, practice, day, 1, f"{day}T21:00:00")
    result = call(conn, "get_done_log", date_from=days[0], date_to=days[-1])
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60
    found = {r["date"] for r in result["rows"]}
    assert days[-1] in found
    assert days[0] not in found
