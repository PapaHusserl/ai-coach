"""MCP шага v2.6: create_draft_event, cancel_draft_event, get_agenda, snapshot agenda."""

import sqlite3
from datetime import date, timedelta
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text
from workload_fakes import coach_event

from ai_coach.mcp_server.tools import MAX_CHARS
from ai_coach.store.agenda import add_event, get_event

TODAY = date.today()
TOMORROW = (TODAY + timedelta(days=1)).isoformat()


def task(**fields: Any) -> dict[str, Any]:
    base = {
        "kind": "task",
        "title": "Буду работать",
        "start_at": f"{TOMORROW}T10:00:00",
        "end_at": f"{TOMORROW}T12:00:00",
        "category": "work",
    }
    return base | fields


def create(conn: sqlite3.Connection, **fields: Any) -> Any:
    return call(conn, "create_draft_event", **task(**fields))


def test_create_draft_event_returns_id_and_stores_draft(conn: sqlite3.Connection) -> None:
    result = create(conn)
    row = get_event(conn, result["draft_id"])
    assert row is not None
    assert (row["status"], row["kind"], row["title"]) == ("draft", "task", "Буду работать")
    assert (row["date"], row["category"]) == (TOMORROW, "work")
    assert row["calendar_uid"] is None


def count(conn: sqlite3.Connection, status: str) -> int:
    sql = "SELECT COUNT(*) FROM coach_events WHERE status = ?"
    return conn.execute(sql, (status,)).fetchone()[0]


def test_create_never_writes_to_calendar(conn: sqlite3.Connection) -> None:
    create(conn)
    assert count(conn, "written") == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "meeting"},
        {"title": ""},
        {"start_at": f"{TOMORROW}T12:00:00", "end_at": f"{TOMORROW}T10:00:00"},
        {"start_at": "не дата"},
        {"category": "coach"},
        {"repeat": "daily"},
        {"workout_id": 999},
    ],
)
def test_invalid_draft_is_rejected(conn: sqlite3.Connection, bad: dict[str, Any]) -> None:
    with pytest.raises(ToolError):
        create(conn, **bad)
    assert count(conn, "draft") == 0


def test_draft_too_far_ahead_is_rejected(conn: sqlite3.Connection) -> None:
    day = (TODAY + timedelta(days=15)).isoformat()
    with pytest.raises(ToolError):
        create(conn, start_at=f"{day}T10:00:00", end_at=f"{day}T11:00:00")


def test_draft_30_days_back_is_ok(conn: sqlite3.Connection) -> None:
    day = (TODAY - timedelta(days=30)).isoformat()
    create(conn, start_at=f"{day}T10:00:00", end_at=f"{day}T11:00:00")


def test_draft_31_days_back_is_rejected(conn: sqlite3.Connection) -> None:
    day = (TODAY - timedelta(days=31)).isoformat()
    with pytest.raises(ToolError):
        create(conn, start_at=f"{day}T10:00:00", end_at=f"{day}T11:00:00")


def test_checkin_daily_draft(conn: sqlite3.Connection) -> None:
    result = create(
        conn, kind="checkin", title="Чек-ин", category=None, repeat="daily",
        start_at=f"{TOMORROW}T21:00:00", end_at=f"{TOMORROW}T21:15:00", alarm_min=0,
    )  # fmt: skip
    row = get_event(conn, result["draft_id"])
    assert row is not None
    assert row["repeat"] == "daily"


def checkin(conn: sqlite3.Connection, clock: str) -> Any:
    return create(
        conn, kind="checkin", title="Чек-ин", category=None, repeat="daily",
        start_at=f"{TOMORROW}T{clock}:00", end_at=f"{TOMORROW}T{clock}:15",
    )  # fmt: skip


def test_second_checkin_daily_at_other_time_gets_draft_id(conn: sqlite3.Connection) -> None:
    first = checkin(conn, "11:00")
    second = checkin(conn, "15:00")
    assert second["draft_id"] != first["draft_id"]
    assert count(conn, "draft") == 2


def test_second_checkin_daily_at_same_time_is_rejected(conn: sqlite3.Connection) -> None:
    checkin(conn, "11:00")
    with pytest.raises(ToolError):
        checkin(conn, "11:00")
    assert count(conn, "draft") == 1


def test_get_agenda_returns_all_earlier_repeating_checkins(conn: sqlite3.Connection) -> None:
    for clock in ("15:00", "11:00"):
        add_event(conn, coach_event(
            kind="checkin", category=None, repeat="daily", title=f"Чек-ин {clock}",
            date="2026-10-01", start_at=f"2026-10-01T{clock}:00", end_at=f"2026-10-01T{clock}:15",
        ))  # fmt: skip
    data = call(conn, "get_agenda", date_from="2026-10-10", date_to="2026-10-10")
    assert [r["title"] for r in data["rows"]] == ["Чек-ин 11:00", "Чек-ин 15:00"]


def test_cancel_draft_event(conn: sqlite3.Connection) -> None:
    draft_id = create(conn)["draft_id"]
    result = call(conn, "cancel_draft_event", event_id=draft_id)
    assert result == {"cancelled_id": draft_id}
    row = get_event(conn, draft_id)
    assert row is not None
    assert row["status"] == "cancelled"


def test_cancel_written_event_is_rejected(conn: sqlite3.Connection) -> None:
    event_id = add_event(conn, coach_event(status="written", calendar_uid="u1"))
    with pytest.raises(ToolError):
        call(conn, "cancel_draft_event", event_id=event_id)
    row = get_event(conn, event_id)
    assert row is not None
    assert row["status"] == "written"


def test_cancel_missing_event_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "cancel_draft_event", event_id=999)


def test_get_agenda_returns_rows_with_statuses(conn: sqlite3.Connection) -> None:
    add_event(conn, coach_event(status="draft", title="Черновик"))
    add_event(conn, coach_event(status="written", calendar_uid="u1", title="Записано"))
    data = call(conn, "get_agenda", date_from="2026-10-10", date_to="2026-10-10")
    assert set(data) == {"rows", "truncated"}
    assert {r["title"]: r["status"] for r in data["rows"]} == {
        "Черновик": "draft",
        "Записано": "written",
    }


def test_get_agenda_filters_by_dates(conn: sqlite3.Connection) -> None:
    add_event(conn, coach_event(date="2026-10-09", start_at="2026-10-09T10:00:00"))
    inside = add_event(conn, coach_event(date="2026-10-10"))
    add_event(conn, coach_event(date="2026-10-12", start_at="2026-10-12T10:00:00"))
    data = call(conn, "get_agenda", date_from="2026-10-10", date_to="2026-10-11")
    assert [r["id"] for r in data["rows"]] == [inside]


def test_get_agenda_empty(conn: sqlite3.Connection) -> None:
    data = call(conn, "get_agenda", date_from="2026-10-10", date_to="2026-10-11")
    assert data == {"rows": [], "truncated": False}


def test_get_agenda_92_days_is_ok(conn: sqlite3.Connection) -> None:
    call(conn, "get_agenda", date_from="2026-10-01", date_to="2026-12-31")


def test_get_agenda_over_92_days_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_agenda", date_from="2026-10-01", date_to="2027-01-02")


def test_get_agenda_reversed_dates_are_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_agenda", date_from="2026-10-11", date_to="2026-10-10")


def test_get_agenda_bad_date_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_agenda", date_from="вчера", date_to="2026-10-10")


DAY = "2026-10-10"


def put(conn: sqlite3.Connection, day: str, **fields: Any) -> int:
    values = coach_event(date=day, start_at=f"{day}T10:00:00", end_at=f"{day}T11:00:00", **fields)
    return add_event(conn, values)


def test_snapshot_agenda_covers_minus_1_to_plus_7(conn: sqlite3.Connection) -> None:
    for day in ("2026-10-08", "2026-10-09", "2026-10-10", "2026-10-17", "2026-10-18"):
        put(conn, day)
    agenda = call(conn, "get_morning_snapshot", date=DAY)["agenda"]
    assert set(agenda) == {"rows", "truncated"}
    assert sorted(r["start_at"][:10] for r in agenda["rows"]) == [
        "2026-10-09",
        "2026-10-10",
        "2026-10-17",
    ]


def test_snapshot_agenda_has_only_draft_and_written(conn: sqlite3.Connection) -> None:
    for status in ("draft", "written", "cancelled", "removed"):
        put(conn, DAY, status=status)
    rows = call(conn, "get_morning_snapshot", date=DAY)["agenda"]["rows"]
    assert sorted(r["status"] for r in rows) == ["draft", "written"]


def test_snapshot_agenda_empty(conn: sqlite3.Connection) -> None:
    agenda = call(conn, "get_morning_snapshot", date=DAY)["agenda"]
    assert agenda == {"rows": [], "truncated": False}


def test_snapshot_with_20_long_events_fits_max_chars(conn: sqlite3.Connection) -> None:
    for i in range(20):
        day = f"2026-10-{10 + i % 8:02d}"
        put(conn, day, title="Длинное название " * 5, note="Очень длинная заметка " * 10)
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert len(text) <= MAX_CHARS
