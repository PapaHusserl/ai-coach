import sqlite3
from datetime import date, datetime
from typing import Any

from workload_fakes import coach_event

from ai_coach.store.agenda import add_event
from ai_coach.store.workload import replace_calendar_window
from ai_coach.web.day import day_view

DAY = date(2026, 11, 7)
D = "2026-11-07"


def at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{D}T{hhmm}:00")


def item(conn: sqlite3.Connection, start: str, end: str, day: str = D, **fields: Any) -> int:
    values = coach_event(date=day, start_at=f"{day}T{start}:00", end_at=f"{day}T{end}:00", **fields)
    event_id = add_event(conn, values)
    conn.commit()
    return event_id


def meeting(
    conn: sqlite3.Connection,
    start: str,
    end: str,
    day: str = D,
    end_day: str | None = None,
    **fields: Any,
) -> int:
    values: dict[str, Any] = {
        "uid": f"uid-{start}-{end}-{day}",
        "date": day,
        "start_at": f"{day}T{start}:00",
        "end_at": f"{end_day or day}T{end}:00",
        "all_day": 0,
        "calendar": "Работа",
        "category": "work",
        "title": "Синтетическая встреча",
        "status": "confirmed",
        "my_status": "accepted",
        "raw_json": {"secret": "сырой ответ"},
        "synced_at": "2026-11-07T08:00:00",
    } | fields
    replace_calendar_window(conn, day, day, _existing(conn, day) + [values])
    conn.commit()
    row = conn.execute("SELECT id FROM calendar_events WHERE uid = ?", (values["uid"],)).fetchone()
    return row["id"]


def _existing(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Прежние встречи дня, чтобы замена окна их не стёрла."""
    rows = conn.execute("SELECT * FROM calendar_events WHERE date = ?", (day,)).fetchall()
    return [{k: r[k] for k in r.keys() if k != "id"} for r in rows]  # noqa: SIM118


def view(conn: sqlite3.Connection, now: str) -> dict[str, Any]:
    return day_view(conn, DAY, at(now))


def test_empty_day(conn: sqlite3.Connection) -> None:
    result = view(conn, "12:00")
    assert result["items"] == []
    assert result["meetings"] == []
    assert result["current"] == []
    assert (result["elapsed_min"], result["left_min"]) == (0, 0)


def three(conn: sqlite3.Connection) -> list[int]:
    return [
        item(conn, "09:00", "10:00"),
        item(conn, "10:00", "11:00"),
        item(conn, "12:00", "13:00"),
    ]


def test_current_and_bar_between_items(conn: sqlite3.Connection) -> None:
    ids = three(conn)
    result = view(conn, "10:30")
    assert result["current"] == [{"source": "item", "id": ids[1]}]
    assert (result["elapsed_min"], result["left_min"]) == (90, 150)


def test_pause_has_no_current(conn: sqlite3.Connection) -> None:
    three(conn)
    result = view(conn, "11:30")
    assert result["current"] == []
    assert (result["elapsed_min"], result["left_min"]) == (150, 90)


def test_boundary_start_inclusive_end_exclusive(conn: sqlite3.Connection) -> None:
    ids = three(conn)
    assert view(conn, "10:00")["current"] == [{"source": "item", "id": ids[1]}]


def test_bar_clamped_before_and_after_frame(conn: sqlite3.Connection) -> None:
    three(conn)
    before = view(conn, "07:00")
    after = view(conn, "15:00")
    assert (before["elapsed_min"], before["left_min"]) == (0, 240)
    assert (after["elapsed_min"], after["left_min"]) == (240, 0)


def test_cancelled_and_removed_items_hidden(conn: sqlite3.Connection) -> None:
    item(conn, "09:00", "10:00", status="cancelled")
    item(conn, "10:00", "11:00", status="removed")
    assert view(conn, "09:30")["items"] == []


def test_draft_and_written_visible_with_status(conn: sqlite3.Connection) -> None:
    item(conn, "09:00", "10:00", status="draft")
    item(conn, "10:00", "11:00", status="written")
    result = view(conn, "09:30")
    assert [i["status"] for i in result["items"]] == ["draft", "written"]


def test_item_fields_whitelist(conn: sqlite3.Connection) -> None:
    item(conn, "09:00", "10:00", note="заметка")
    row = view(conn, "09:30")["items"][0]
    assert set(row) == {
        "id",
        "kind",
        "title",
        "start_at",
        "end_at",
        "all_day",
        "status",
        "note",
        "repeat",
    }
    assert row["note"] == "заметка"


def test_cancelled_and_declined_meetings_hidden(conn: sqlite3.Connection) -> None:
    meeting(conn, "09:00", "10:00", status="cancelled")
    meeting(conn, "10:00", "11:00", my_status="declined")
    assert view(conn, "09:30")["meetings"] == []


def test_meeting_from_previous_evening_clipped_to_midnight(conn: sqlite3.Connection) -> None:
    meeting(conn, "23:00", "01:00", day="2026-11-06", end_day=D)
    found = view(conn, "00:30")["meetings"]
    assert [(m["start_at"], m["end_at"]) for m in found] == [(f"{D}T00:00:00", f"{D}T01:00:00")]


def test_meeting_ending_tomorrow_clipped_to_next_midnight(conn: sqlite3.Connection) -> None:
    meeting(conn, "23:00", "02:00", end_day="2026-11-08")
    found = view(conn, "23:30")["meetings"]
    assert [(m["start_at"], m["end_at"]) for m in found] == [
        (f"{D}T23:00:00", "2026-11-08T00:00:00")
    ]


def test_meeting_started_two_days_ago_not_listed(conn: sqlite3.Connection) -> None:
    meeting(conn, "22:00", "01:00", day="2026-11-05", end_day=D)
    assert view(conn, "00:30")["meetings"] == []


def test_result_has_date_and_now(conn: sqlite3.Connection) -> None:
    result = view(conn, "12:00")
    assert result["date"] == D
    assert result["now"] == f"{D}T12:00:00"


def test_meeting_fully_yesterday_hidden(conn: sqlite3.Connection) -> None:
    meeting(conn, "10:00", "11:00", day="2026-11-06")
    assert view(conn, "10:30")["meetings"] == []


def test_meeting_fields_whitelist_and_title(conn: sqlite3.Connection) -> None:
    meeting(conn, "10:00", "11:00")
    row = view(conn, "10:30")["meetings"][0]
    assert set(row) == {"id", "start_at", "end_at", "all_day", "title", "calendar"}
    assert row["title"] == "Синтетическая встреча"
    assert "сырой ответ" not in str(view(conn, "10:30"))


def test_meeting_current_and_frame(conn: sqlite3.Connection) -> None:
    item(conn, "09:00", "10:00")
    mid = meeting(conn, "14:00", "15:00")
    result = view(conn, "14:30")
    assert result["current"] == [{"source": "meeting", "id": mid}]
    assert (result["elapsed_min"], result["left_min"]) == (330, 30)


def test_early_meeting_moves_frame_start(conn: sqlite3.Connection) -> None:
    item(conn, "09:00", "10:00")
    meeting(conn, "08:00", "08:30")
    result = view(conn, "09:00")
    assert (result["elapsed_min"], result["left_min"]) == (60, 60)


def test_all_day_meeting_listed_not_current_not_in_frame(conn: sqlite3.Connection) -> None:
    item(conn, "09:00", "10:00")
    meeting(conn, "00:00", "23:59", all_day=1)
    result = view(conn, "09:30")
    assert [m["all_day"] for m in result["meetings"]] == [1]
    assert result["current"] == [{"source": "item", "id": result["items"][0]["id"]}]
    assert (result["elapsed_min"], result["left_min"]) == (30, 30)


def test_all_day_item_listed_not_current_not_in_frame(conn: sqlite3.Connection) -> None:
    item(conn, "00:00", "23:59", all_day=1)
    result = view(conn, "12:00")
    assert len(result["items"]) == 1
    assert result["current"] == []
    assert (result["elapsed_min"], result["left_min"]) == (0, 0)


def test_overlap_meeting_and_training_both_current(conn: sqlite3.Connection) -> None:
    mid = meeting(conn, "10:00", "11:00")
    tid = item(conn, "10:30", "11:30", kind="training")
    assert view(conn, "10:45")["current"] == [
        {"source": "meeting", "id": mid},
        {"source": "item", "id": tid},
    ]
    assert view(conn, "11:00")["current"] == [{"source": "item", "id": tid}]


def test_two_items_overlap_both_current(conn: sqlite3.Connection) -> None:
    a = item(conn, "10:00", "11:00")
    b = item(conn, "10:30", "11:30")
    assert view(conn, "10:45")["current"] == [
        {"source": "item", "id": a},
        {"source": "item", "id": b},
    ]


def checkin(conn: sqlite3.Connection, repeat: str, since: str, start: str = "20:00") -> int:
    return item(conn, start, "20:15", day=since, kind="checkin", repeat=repeat)


def test_weekly_checkin_only_on_its_weekday(conn: sqlite3.Connection) -> None:
    checkin(conn, "weekly", "2026-10-31")
    assert len(view(conn, "12:00")["items"]) == 1
    assert day_view(conn, date(2026, 11, 8), at("12:00"))["items"] == []
    assert day_view(conn, date(2026, 11, 5), at("12:00"))["items"] == []


def test_daily_checkin_every_day(conn: sqlite3.Connection) -> None:
    checkin(conn, "daily", "2026-10-31")
    for day in (date(2026, 11, 7), date(2026, 11, 8), date(2026, 11, 12)):
        assert len(day_view(conn, day, at("12:00"))["items"]) == 1


def test_biweekly_checkin_every_two_weeks(conn: sqlite3.Connection) -> None:
    checkin(conn, "biweekly", "2026-10-24")
    assert len(view(conn, "12:00")["items"]) == 1
    assert day_view(conn, date(2026, 11, 14), at("12:00"))["items"] == []


def test_repeat_on_its_day_moved_current_and_extends_frame(conn: sqlite3.Connection) -> None:
    cid = checkin(conn, "weekly", "2026-10-31")
    item(conn, "09:00", "10:00")
    result = view(conn, "20:05")
    assert result["items"][1]["start_at"] == f"{D}T20:00:00"
    assert {"source": "item", "id": cid} in result["current"]
    assert (result["elapsed_min"], result["left_min"]) == (665, 10)


def test_repeat_on_other_day_does_not_extend_frame(conn: sqlite3.Connection) -> None:
    checkin(conn, "weekly", "2026-10-31")
    item(conn, "09:00", "10:00", day="2026-11-05")
    result = day_view(conn, date(2026, 11, 5), datetime(2026, 11, 5, 9, 30))
    assert [i["kind"] for i in result["items"]] != ["checkin"]
    assert (result["elapsed_min"], result["left_min"]) == (30, 30)
