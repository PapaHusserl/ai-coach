import sqlite3
from datetime import date, datetime
from typing import Any

from workload_fakes import coach_event

from ai_coach.profile.service import set_value
from ai_coach.store.agenda import add_event
from ai_coach.store.journal import add_food, add_slip, add_weight, add_wellbeing
from ai_coach.store.workload import replace_calendar_window
from ai_coach.web.day import day_view
from ai_coach.web.marks import save_mark
from ai_coach.web.repeat import moved, on_day

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


def mark(event_id: int, kind: str, **fields: Any) -> dict[str, Any]:
    return {"event_id": event_id, "date": D, "mark": kind, **fields}


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
        "marks",
        "due",
    }
    assert row["note"] == "заметка"


def by_id(result: dict[str, Any], event_id: int) -> dict[str, Any]:
    return next(r for r in result["items"] if r["id"] == event_id)


def test_due_for_past_unmarked_task_only(conn: sqlite3.Connection) -> None:
    unmarked = item(conn, "09:00", "10:00")
    rated = item(conn, "10:00", "11:00")
    future = item(conn, "16:00", "17:00")
    save_mark(conn, mark(rated, "rating", focus=4, fatigue=2, effort=3), at("10:30"))
    conn.commit()
    result = view(conn, "15:00")
    assert by_id(result, unmarked)["due"] is True
    assert by_id(result, rated)["due"] is False
    assert by_id(result, future)["due"] is False


def test_practice_done_zero_is_not_due(conn: sqlite3.Connection) -> None:
    practice = item(conn, "12:00", "12:15", kind="practice")
    save_mark(conn, mark(practice, "done", done=0), at("12:05"))
    conn.commit()
    row = by_id(view(conn, "15:00"), practice)
    assert row["due"] is False
    assert row["marks"]["done"]["done"] == 0


def test_checkin_due_follows_evening_done_even_without_event_id(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "20:00", "20:15", kind="checkin")
    assert by_id(view(conn, "21:00"), checkin)["due"] is True
    add_wellbeing(conn, {"date": D, "logged_at": f"{D} 20:30:00", "score": 3, "mood": 3})
    conn.commit()
    assert by_id(view(conn, "21:00"), checkin)["due"] is False


def test_marks_hold_only_own_item_and_day(conn: sqlite3.Connection) -> None:
    mine = item(conn, "09:00", "10:00")
    other = item(conn, "10:00", "11:00")
    save_mark(conn, mark(mine, "slip", text="бесит"), at("09:30"))
    save_mark(conn, mark(other, "feel", score=4), at("10:30"))
    add_slip(
        conn,
        {
            "date": "2026-11-06",
            "logged_at": "2026-11-06 09:30:00",
            "text": "вчера",
            "event_id": mine,
        },
    )
    conn.commit()
    result = view(conn, "12:00")
    assert [s["text"] for s in by_id(result, mine)["marks"]["slips"]] == ["бесит"]
    assert by_id(result, mine)["marks"]["feel"] == []
    assert by_id(result, other)["marks"]["feel"][0]["score"] == 4


def test_past_unmarked_rest_and_practice_are_due(conn: sqlite3.Connection) -> None:
    rest = item(conn, "09:00", "09:30", kind="rest")
    practice = item(conn, "10:00", "10:30", kind="practice")
    result = view(conn, "15:00")
    assert by_id(result, rest)["due"] is True
    assert by_id(result, practice)["due"] is True
    assert by_id(result, rest)["marks"]["done"] is None


def test_done_one_on_rest_is_not_due(conn: sqlite3.Connection) -> None:
    rest = item(conn, "09:00", "09:30", kind="rest")
    save_mark(conn, mark(rest, "done", done=1), at("09:10"))
    conn.commit()
    assert by_id(view(conn, "15:00"), rest)["due"] is False


def test_past_unrated_focus_is_due(conn: sqlite3.Connection) -> None:
    focus = item(conn, "09:00", "10:00", kind="focus")
    assert by_id(view(conn, "15:00"), focus)["due"] is True


def test_feel_and_slip_do_not_fill_a_task(conn: sqlite3.Connection) -> None:
    task = item(conn, "09:00", "10:00")
    save_mark(conn, mark(task, "feel", score=4), at("09:30"))
    save_mark(conn, mark(task, "slip", text="сорвался"), at("09:40"))
    conn.commit()
    assert by_id(view(conn, "15:00"), task)["due"] is True


def test_past_unfilled_checkin_is_due_only_when_past(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "20:00", "20:15", kind="checkin")
    assert by_id(view(conn, "20:05"), checkin)["due"] is False


def test_kinds_without_window_are_never_due_and_have_empty_marks(
    conn: sqlite3.Connection,
) -> None:
    ids = [item(conn, "06:00", "07:00", kind=k) for k in ("sleep", "training")]
    result = view(conn, "15:00")
    for event_id in ids:
        row = by_id(result, event_id)
        assert row["due"] is False
        assert row["marks"] == {"ratings": [], "feel": [], "slips": [], "done": None, "food": []}
        assert "meal" not in row


def meal(conn: sqlite3.Connection, start: str = "08:00", end: str = "09:00", **fields: Any) -> int:
    return item(conn, start, end, kind="meal", title=fields.pop("title", "Завтрак"), **fields)


def profile(conn: sqlite3.Connection) -> None:
    for key, value in [
        ("sex", "m"),
        ("birth_date", "1990-01-15"),
        ("height_cm", "180"),
        ("kcal_target", "2400"),
    ]:
        set_value(conn, key, value, "manual", "2026-10-01T10:00:00")
    add_weight(conn, {"measured_at": "2026-11-06 07:00:00", "weight_kg": 80.0})
    conn.commit()


def eaten(conn: sqlite3.Connection, text: str, kcal: float | None, **fields: Any) -> None:
    values = {"logged_at": f"{D} 08:00:00", "text": text, "kcal": kcal}
    if kcal is not None:
        values |= {"protein_g": 30, "fat_g": 10, "carbs_g": 50}
    add_food(conn, values | fields)
    conn.commit()


def test_past_meal_without_food_is_due(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    assert by_id(view(conn, "15:00"), breakfast)["due"] is True


def test_future_or_running_meal_is_not_due(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn, "16:00", "17:00")
    assert by_id(view(conn, "15:00"), breakfast)["due"] is False
    assert by_id(view(conn, "16:30"), breakfast)["due"] is False


def test_food_text_without_nutrition_clears_due(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    save_mark(conn, mark(breakfast, "food", text="омлет"), at("08:30"))
    conn.commit()
    assert by_id(view(conn, "15:00"), breakfast)["due"] is False


def test_food_of_another_item_does_not_clear_due(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    supper = meal(conn, "13:00", "14:00", title="Ужин")
    save_mark(conn, mark(supper, "food", text="суп"), at("13:30"))
    conn.commit()
    result = view(conn, "15:00")
    assert by_id(result, breakfast)["due"] is True
    assert by_id(result, supper)["due"] is False


def test_food_from_cli_without_event_does_not_clear_due(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    eaten(conn, "из CLI", None)
    assert by_id(view(conn, "15:00"), breakfast)["due"] is True


def test_feel_does_not_clear_meal_due(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    save_mark(conn, mark(breakfast, "feel", score=4), at("08:30"))
    conn.commit()
    assert by_id(view(conn, "15:00"), breakfast)["due"] is True


def test_cooking_is_never_due(conn: sqlite3.Connection) -> None:
    cooking = meal(conn, title="Готовка")
    row = by_id(view(conn, "15:00"), cooking)
    assert row["due"] is False


def test_cooking_has_no_meal_key_and_breakfast_has(conn: sqlite3.Connection) -> None:
    cooking = meal(conn, title="Готовка")
    breakfast = meal(conn, "10:00", "11:00")
    result = view(conn, "15:00")
    assert "meal" not in by_id(result, cooking)
    assert "meal" in by_id(result, breakfast)


def test_meal_item_has_food_of_own_item_only(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    supper = meal(conn, "13:00", "14:00", title="Ужин")
    save_mark(conn, mark(breakfast, "food", text="омлет"), at("08:30"))
    save_mark(conn, mark(supper, "food", text="суп"), at("13:30"))
    eaten(conn, "из CLI", None)
    conn.commit()
    result = view(conn, "15:00")
    assert [f["text"] for f in by_id(result, breakfast)["meal"]["food"]] == ["омлет"]
    assert [f["text"] for f in by_id(result, supper)["meal"]["food"]] == ["суп"]


def test_meal_food_row_fields(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    eaten(conn, "каша", 400, event_id=breakfast)
    [food] = by_id(view(conn, "15:00"), breakfast)["meal"]["food"]
    assert set(food) == {"id", "text", "kcal", "logged_at"}
    assert (food["text"], food["kcal"], food["logged_at"]) == ("каша", 400, f"{D} 08:00:00")


def test_meal_food_of_other_day_is_not_shown(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    eaten(conn, "вчера", None, event_id=breakfast, logged_at="2026-11-06 08:00:00")
    assert by_id(view(conn, "15:00"), breakfast)["meal"]["food"] == []


def test_meal_remaining_is_none_without_profile(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    row = by_id(view(conn, "15:00"), breakfast)
    assert row["meal"]["remaining"] is None


def test_meal_remaining_is_target_minus_all_day_food(conn: sqlite3.Connection) -> None:
    profile(conn)
    breakfast = meal(conn)
    supper = meal(conn, "13:00", "14:00", title="Ужин")
    eaten(conn, "каша", 500, event_id=breakfast)
    eaten(conn, "из CLI", 300)
    eaten(conn, "без КБЖУ", None, event_id=supper)
    result = view(conn, "15:00")
    for event_id in (breakfast, supper):
        remaining = by_id(result, event_id)["meal"]["remaining"]
        assert remaining["kcal"] == 2400 - 800
        assert remaining["pending_count"] == 1
        assert set(remaining) == {"kcal", "protein_g", "fat_g", "carbs_g", "pending_count"}


def test_meal_remaining_ignores_other_day_food(conn: sqlite3.Connection) -> None:
    profile(conn)
    breakfast = meal(conn)
    eaten(conn, "вчера", 900, logged_at="2026-11-06 20:00:00")
    assert by_id(view(conn, "15:00"), breakfast)["meal"]["remaining"]["kcal"] == 2400


def test_marks_carry_fields_and_order_by_time(conn: sqlite3.Connection) -> None:
    task = item(conn, "09:00", "11:00")
    save_mark(conn, mark(task, "rating", focus=4, fatigue=2, effort=3, text="ок"), at("09:30"))
    save_mark(conn, mark(task, "rating", focus=1, fatigue=5, effort=5), at("10:30"))
    save_mark(conn, mark(task, "feel", score=2, text="устал"), at("10:00"))
    conn.commit()
    marks = by_id(view(conn, "12:00"), task)["marks"]
    first, second = marks["ratings"]
    assert (first["focus"], first["fatigue"], first["effort"], first["text"]) == (4, 2, 3, "ок")
    assert first["logged_at"] == f"{D} 09:30:00"
    assert second["focus"] == 1
    assert (marks["feel"][0]["score"], marks["feel"][0]["text"]) == (2, "устал")
    assert marks["feel"][0]["logged_at"] == f"{D} 10:00:00"


def test_meetings_have_no_marks(conn: sqlite3.Connection) -> None:
    meeting(conn, "09:00", "10:00")
    row = view(conn, "12:00")["meetings"][0]
    assert "marks" not in row
    assert "due" not in row


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


def repeat_row(repeat: str | None, since: str = "2026-10-31") -> dict[str, Any]:
    return {
        "repeat": repeat,
        "date": since,
        "start_at": f"{since}T20:00:00",
        "end_at": f"{since}T20:15:00",
    }


def test_on_day_without_repeat_or_on_start_day_defers_to_query() -> None:
    assert on_day(repeat_row(None), date(2026, 11, 7))
    assert on_day(repeat_row("weekly"), date(2026, 10, 31))
    assert on_day(repeat_row("weekly"), date(2026, 10, 30))


def test_on_day_by_repeat_kind() -> None:
    assert on_day(repeat_row("weekly"), date(2026, 11, 7))
    assert not on_day(repeat_row("weekly"), date(2026, 11, 8))
    assert on_day(repeat_row("biweekly"), date(2026, 11, 14))
    assert not on_day(repeat_row("biweekly"), date(2026, 11, 7))


def test_moved_shifts_dates_keeping_time_of_day() -> None:
    row = moved(repeat_row("weekly"), date(2026, 11, 7))
    assert (row["start_at"], row["end_at"]) == ("2026-11-07T20:00:00", "2026-11-07T20:15:00")


def test_moved_on_start_day_returns_row_untouched() -> None:
    row = {**repeat_row("weekly"), "start_at": "2026-10-31 20:00", "end_at": "2026-10-31 20:15"}
    assert moved(row, date(2026, 10, 31)) == row


def test_item_ending_exactly_now_is_past_and_due(conn: sqlite3.Connection) -> None:
    task = item(conn, "09:00", "10:00")
    assert by_id(view(conn, "10:00"), task)["due"] is True


def test_moved_leaves_non_repeating_row() -> None:
    row = repeat_row(None)
    assert moved(row, date(2026, 11, 7)) == row


def test_repeat_on_other_day_does_not_extend_frame(conn: sqlite3.Connection) -> None:
    checkin(conn, "weekly", "2026-10-31")
    item(conn, "09:00", "10:00", day="2026-11-05")
    result = day_view(conn, date(2026, 11, 5), datetime(2026, 11, 5, 9, 30))
    assert [i["kind"] for i in result["items"]] != ["checkin"]
    assert (result["elapsed_min"], result["left_min"]) == (30, 30)
