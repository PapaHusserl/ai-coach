import sqlite3

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, rows, tool_names
from workload_fakes import stored_event

from ai_coach.store.workload import replace_calendar_window, upsert_counter

DAY = "2026-10-07"
TITLE = "Секретное название встречи"
RAW = "SECRET_RAW_PAYLOAD"


def put(conn: sqlite3.Connection, day: str, start: str, end: str, **fields: object) -> None:
    event = stored_event(
        uid=f"u-{day}-{start}",
        start_at=f"{day}T{start}:00",
        end_at=f"{day}T{end}:00",
        title=TITLE,
        raw_json={"secret": RAW},
        **fields,
    )
    replace_calendar_window(conn, day, day, [event])


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_workload" in tool_names(conn)


def test_workload_has_rows_and_truncated(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_workload", date_from=DAY, date_to=DAY)
    assert set(answer) == {"rows", "truncated"}
    assert answer["truncated"] is False


def test_workload_returns_row_per_day_inclusive(conn: sqlite3.Connection) -> None:
    found = rows(conn, "get_workload", date_from="2026-10-06", date_to=DAY)
    assert [r["date"] for r in found] == ["2026-10-06", DAY]


def test_workload_row_has_hours_and_counters(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    upsert_counter(
        conn,
        {
            "date": DAY,
            "kind": "todo_closed",
            "value": 2,
            "source": "x",
            "raw_json": {},
            "synced_at": "2026-10-08T10:00:00",
        },
    )
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert row["work_hours"] == pytest.approx(2.0)
    assert row["todo_closed"] == 2


SCREEN_KINDS = (
    "screen_work_hours",
    "screen_hobby_hours",
    "screen_browser_hours",
    "screen_evening_hours",
)


def screen(conn: sqlite3.Connection, day: str, kind: str, value: float) -> None:
    upsert_counter(
        conn,
        {
            "date": day,
            "kind": kind,
            "value": value,
            "source": "screen",
            "raw_json": None,
            "synced_at": "2026-10-08T10:00:00",
        },
    )


def test_workload_row_has_screen_hours(conn: sqlite3.Connection) -> None:
    for number, kind in enumerate(SCREEN_KINDS):
        screen(conn, DAY, kind, 1.25 + number)
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert [row[k] for k in SCREEN_KINDS] == [1.25, 2.25, 3.25, 4.25]


def test_workload_screen_fields_are_none_without_data(conn: sqlite3.Connection) -> None:
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert all(row[k] is None for k in SCREEN_KINDS)


def test_workload_screen_zero_stays_zero(conn: sqlite3.Connection) -> None:
    screen(conn, DAY, "screen_work_hours", 0)
    assert rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]["screen_work_hours"] == 0


def test_workload_with_events_true_still_has_screen_hours_and_no_app_names(
    conn: sqlite3.Connection,
) -> None:
    screen(conn, DAY, "screen_work_hours", 2.5)
    text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=True)
    assert "2.5" in text
    assert "raw_json" not in text


def test_workload_range_of_92_days_is_allowed(conn: sqlite3.Connection) -> None:
    call(conn, "get_workload", date_from="2026-07-08", date_to="2026-10-07")


def test_workload_range_over_92_days_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_workload", date_from="2026-07-07", date_to="2026-10-07")


def test_workload_bad_date_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_workload", date_from="07.10.2026", date_to=DAY)


def test_workload_end_before_start_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_workload", date_from=DAY, date_to="2026-10-01")


def test_workload_without_events_has_no_titles(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    assert TITLE not in call_text(conn, "get_workload", date_from=DAY, date_to=DAY)


def test_workload_events_false_has_no_titles(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=False)
    assert TITLE not in text


def test_workload_events_on_one_day_has_titles(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=True)
    assert TITLE in text


def test_workload_events_on_range_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_workload", date_from="2026-10-06", date_to=DAY, events=True)


def test_workload_never_returns_raw_json(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    for events in (False, True):
        text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=events)
        assert RAW not in text
        assert "raw_json" not in text
