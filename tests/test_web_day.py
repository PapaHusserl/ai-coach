import sqlite3
from datetime import date, datetime
from typing import Any

import pytest
from test_web_food import ITEMS
from test_web_food import put_offer as put_offer_on
from test_web_training import RUN_SPEC, activity, actual, workout
from workload_fakes import coach_event

from ai_coach.profile.service import set_value
from ai_coach.store.agenda import add_event
from ai_coach.store.journal import add_food, add_slip, add_weight, add_wellbeing, add_who5
from ai_coach.store.workload import replace_calendar_window
from ai_coach.web.day import day_view
from ai_coach.web.errors import MarkError
from ai_coach.web.marks import save_mark
from ai_coach.web.repeat import moved, on_day
from ai_coach.workouts.phone import player_payload

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


def test_day_view_has_header_with_weight_of_the_day(conn: sqlite3.Connection) -> None:
    assert view(conn, "12:00")["header"]["weight"] is None
    add_weight(conn, {"measured_at": "2026-11-07 07:00:00", "weight_kg": 81.7})
    header = view(conn, "12:00")["header"]
    assert header["weight"] == {"kg": 81.7, "measured_at": "2026-11-07 07:00:00"}
    assert set(header) == {"weight", "sync", "metrics"}


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
        "workout_id",
        "survey",
    }
    assert row["note"] == "заметка"
    assert row["workout_id"] is None


def test_item_survey_is_null_for_non_checkin(conn: sqlite3.Connection) -> None:
    task = item(conn, "09:00", "10:00")
    assert by_id(view(conn, "09:30"), task)["survey"] is None


def test_item_survey_of_checkin_is_given(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "20:00", "20:15", kind="checkin", category=None, survey="focus")
    assert by_id(view(conn, "20:05"), checkin)["survey"] == "focus"


def test_past_feel_checkin_is_due_until_own_feel_mark(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="feel")
    assert by_id(view(conn, "16:00"), checkin)["due"] is True
    save_mark(conn, mark(checkin, "feel", score=4), at("15:10"))
    conn.commit()
    assert by_id(view(conn, "16:00"), checkin)["due"] is False


def test_evening_done_does_not_clear_feel_checkin(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="feel")
    add_wellbeing(conn, {"date": D, "logged_at": f"{D} 20:30:00", "score": 3, "mood": 3})
    conn.commit()
    assert by_id(view(conn, "21:00"), checkin)["due"] is True


def test_past_focus_checkin_is_due_until_rating(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="focus")
    assert by_id(view(conn, "16:00"), checkin)["due"] is True
    save_mark(conn, mark(checkin, "rating", focus=4, fatigue=2, effort=3), at("15:10"))
    conn.commit()
    assert by_id(view(conn, "16:00"), checkin)["due"] is False


@pytest.mark.parametrize("done", [1, 0])
def test_none_checkin_is_due_without_mark_and_not_with_it(
    conn: sqlite3.Connection, done: int
) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="none")
    assert by_id(view(conn, "16:00"), checkin)["due"] is True
    save_mark(conn, mark(checkin, "done", done=done), at("15:10"))
    conn.commit()
    assert by_id(view(conn, "16:00"), checkin)["due"] is False


def test_none_checkin_unmarked_returns_to_due(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="none")
    save_mark(conn, mark(checkin, "done", done=1), at("15:10"))
    save_mark(conn, mark(checkin, "done", done=None), at("15:12"))
    conn.commit()
    assert by_id(view(conn, "16:00"), checkin)["due"] is True


def test_future_checkin_of_any_survey_is_not_due(conn: sqlite3.Connection) -> None:
    ids = [
        item(conn, "18:00", "18:15", kind="checkin", category=None, survey=s)
        for s in ("evening", "feel", "focus", "none")
    ]
    result = view(conn, "17:00")
    assert [by_id(result, i)["due"] for i in ids] == [False] * 4


WHO5_ANSWERS = {"q1": 5, "q2": 4, "q3": 3, "q4": 4, "q5": 5}


def test_past_who5_checkin_is_due_until_measure_of_the_day(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="who5")
    assert by_id(view(conn, "16:00"), checkin)["due"] is True
    save_mark(conn, mark(checkin, "who5", **WHO5_ANSWERS), at("15:10"))
    conn.commit()
    assert by_id(view(conn, "16:00"), checkin)["due"] is False


def test_who5_measure_from_coach_clears_due_and_is_shown(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="who5")
    add_who5(
        conn,
        {**WHO5_ANSWERS, "score": 84, "date": D, "logged_at": f"{D} 09:00:00", "text": None},
    )
    conn.commit()
    row = by_id(view(conn, "16:00"), checkin)
    assert row["due"] is False
    assert (row["who5"]["score"], row["who5"]["logged_at"]) == (84, f"{D} 09:00:00")


def test_who5_key_shows_pult_measure(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="who5")
    save_mark(conn, mark(checkin, "who5", **WHO5_ANSWERS), at("15:10"))
    conn.commit()
    assert by_id(view(conn, "16:00"), checkin)["who5"]["score"] == 84


def test_future_who5_checkin_is_not_due(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "18:00", "18:15", kind="checkin", category=None, survey="who5")
    assert by_id(view(conn, "17:00"), checkin)["due"] is False


def test_who5_measure_of_other_day_does_not_clear_due(conn: sqlite3.Connection) -> None:
    checkin = item(conn, "15:00", "15:15", kind="checkin", category=None, survey="who5")
    add_who5(
        conn,
        {**WHO5_ANSWERS, "score": 84, "date": "2026-11-06", "logged_at": "2026-11-06 09:00:00",
         "text": None},
    )  # fmt: skip
    conn.commit()
    assert by_id(view(conn, "16:00"), checkin)["due"] is True


def test_none_checkin_mark_of_other_day_does_not_clear_due(conn: sqlite3.Connection) -> None:
    checkin = item(
        conn, "15:00", "15:15", day="2026-11-05", kind="checkin", category=None,
        survey="none", repeat="daily",
    )  # fmt: skip
    payload = {"event_id": checkin, "date": "2026-11-06", "mark": "done", "done": 1}
    save_mark(conn, payload, at("16:00"))
    conn.commit()
    assert by_id(view(conn, "16:00"), checkin)["due"] is True


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
    ids = [item(conn, "06:00", "07:00", kind=k) for k in ("sleep",)]
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


def offers_of(conn: sqlite3.Connection, event_id: int, now: str = "15:00") -> list[dict[str, Any]]:
    return by_id(view(conn, now), event_id)["meal"]["offers"]


def put_offer(conn: sqlite3.Connection, day: str = D, **fields: Any) -> int:
    """Вариант на день этого файла (D), не на день test_web_food."""
    return put_offer_on(conn, day=day, **fields)


def test_meal_offers_of_other_day_are_not_shown(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    put_offer(conn, event_id=breakfast, name="Вчерашний", day="2026-11-06")
    put_offer(conn, event_id=breakfast, name="Сегодняшний")
    assert [o["name"] for o in offers_of(conn, breakfast)] == ["Сегодняшний"]


def test_meal_without_offers_has_empty_offers_list(conn: sqlite3.Connection) -> None:
    assert offers_of(conn, meal(conn)) == []


def test_meal_offers_have_id_name_items_and_totals(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    offer_id = put_offer(conn, event_id=breakfast, name="Омлет")
    [offer] = offers_of(conn, breakfast)
    assert offer["id"] == offer_id
    assert offer["name"] == "Омлет"
    assert offer["items"] == ITEMS
    totals = (offer["kcal"], offer["protein_g"], offer["fat_g"], offer["carbs_g"])
    assert totals == (270, 16, 11, 25)


def test_meal_offers_follow_position_order(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    put_offer(conn, event_id=breakfast, name="Второй", position=2)
    put_offer(conn, event_id=breakfast, name="Первый", position=1)
    assert [o["name"] for o in offers_of(conn, breakfast)] == ["Первый", "Второй"]


def test_meal_offers_are_only_of_own_item(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    supper = meal(conn, "13:00", "14:00", title="Ужин")
    put_offer(conn, event_id=supper, name="Суп")
    assert offers_of(conn, breakfast) == []
    assert [o["name"] for o in offers_of(conn, supper)] == ["Суп"]


def test_cooking_has_no_offers_key_even_with_offer_row(conn: sqlite3.Connection) -> None:
    cooking = meal(conn, title="Готовка")
    put_offer(conn, event_id=cooking)
    assert "meal" not in by_id(view(conn, "15:00"), cooking)


def test_taking_offer_lowers_remaining_by_its_kcal_without_pending(
    conn: sqlite3.Connection,
) -> None:
    profile(conn)
    breakfast = meal(conn)
    before = by_id(view(conn, "15:00"), breakfast)["meal"]["remaining"]
    offer_id = put_offer(conn, event_id=breakfast)
    save_mark(conn, mark(breakfast, "food", offer_id=offer_id), at("08:30"))
    conn.commit()
    after = by_id(view(conn, "15:00"), breakfast)["meal"]["remaining"]
    assert before["kcal"] - after["kcal"] == 270
    assert after["pending_count"] == 0


def test_taking_offer_clears_meal_due(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    offer_id = put_offer(conn, event_id=breakfast)
    save_mark(conn, mark(breakfast, "food", offer_id=offer_id), at("08:30"))
    conn.commit()
    assert by_id(view(conn, "15:00"), breakfast)["due"] is False


def test_offer_of_another_meal_item_is_rejected_by_save_mark(conn: sqlite3.Connection) -> None:
    breakfast = meal(conn)
    supper = meal(conn, "13:00", "14:00", title="Ужин")
    offer_id = put_offer(conn, event_id=supper)
    with pytest.raises(MarkError):
        save_mark(conn, mark(breakfast, "food", offer_id=offer_id), at("08:30"))


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
    assert set(row) == {
        "id",
        "start_at",
        "end_at",
        "all_day",
        "title",
        "calendar",
        "recurring",
        "editable",
    }
    assert row["title"] == "Синтетическая встреча"
    assert "сырой ответ" not in str(view(conn, "10:30"))
    assert "uid-10:00" not in str(view(conn, "10:30"))


def test_meeting_with_uid_of_written_coach_item_is_hidden(conn: sqlite3.Connection) -> None:
    item(conn, "10:00", "11:00", status="written", calendar_uid="uid-10:00-11:00-2026-11-07")
    meeting(conn, "10:00", "11:00")
    meeting(conn, "12:00", "13:00")
    found = view(conn, "10:30")["meetings"]
    assert [m["start_at"] for m in found] == [f"{D}T12:00:00"]


def test_meeting_editable_only_without_attendee_status(conn: sqlite3.Connection) -> None:
    meeting(conn, "09:00", "10:00", my_status="accepted")
    meeting(conn, "10:00", "11:00", my_status=None)
    found = view(conn, "12:00")["meetings"]
    assert [(m["start_at"][11:16], m["editable"]) for m in found] == [
        ("09:00", False),
        ("10:00", True),
    ]


def test_meeting_recurring_comes_from_raw_json(conn: sqlite3.Connection) -> None:
    meeting(conn, "09:00", "10:00", raw_json={"recurring": True})
    meeting(conn, "10:00", "11:00", raw_json={})
    found = view(conn, "12:00")["meetings"]
    assert [m["recurring"] for m in found] == [True, False]


@pytest.mark.parametrize("raw_json", [None, ""])
def test_recurring_without_raw_json_is_false(raw_json: str | None) -> None:
    from ai_coach.web.day import recurring

    assert recurring({"raw_json": raw_json}) is False


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


def run_item(conn: sqlite3.Connection, start: str = "09:00", end: str = "09:40") -> tuple[int, int]:
    wid = workout(conn)
    return item(conn, start, end, kind="training", workout_id=wid), wid


def test_training_item_has_workout_id(conn: sqlite3.Connection) -> None:
    eid, wid = run_item(conn)
    assert by_id(view(conn, "15:00"), eid)["workout_id"] == wid


def test_training_plan_has_name_sport_duration_and_player_steps(conn: sqlite3.Connection) -> None:
    eid, _ = run_item(conn)
    plan = by_id(view(conn, "15:00"), eid)["training"]["plan"]
    assert (plan["name"], plan["sport"], plan["duration_min"]) == ("Лёгкий бег", "run", 40)
    assert plan["steps"] == player_payload("run", RUN_SPEC, D)["b"]


def test_training_fact_is_none_before_sync(conn: sqlite3.Connection) -> None:
    eid, _ = run_item(conn)
    assert by_id(view(conn, "15:00"), eid)["training"]["fact"] is None


def test_training_fact_after_sync(conn: sqlite3.Connection) -> None:
    eid, wid = run_item(conn)
    actual(conn, wid, activity_id=activity(conn))
    fact = by_id(view(conn, "15:00"), eid)["training"]["fact"]
    assert (fact["kind"], fact["duration_s"]) == ("done", 2400)


def test_other_kinds_have_no_training_key(conn: sqlite3.Connection) -> None:
    task = item(conn, "09:00", "10:00")
    assert "training" not in by_id(view(conn, "15:00"), task)


def test_past_training_without_mark_and_fact_is_due(conn: sqlite3.Connection) -> None:
    eid, _ = run_item(conn)
    assert by_id(view(conn, "15:00"), eid)["due"] is True


def test_future_training_is_not_due(conn: sqlite3.Connection) -> None:
    eid, _ = run_item(conn, "16:00", "16:40")
    assert by_id(view(conn, "15:00"), eid)["due"] is False


@pytest.mark.parametrize("kind", ["done", "different"])
def test_training_with_garmin_fact_is_not_due(conn: sqlite3.Connection, kind: str) -> None:
    eid, wid = run_item(conn)
    actual(conn, wid, kind, activity_id=activity(conn))
    assert by_id(view(conn, "15:00"), eid)["due"] is False


def test_skipped_fact_without_mark_stays_due(conn: sqlite3.Connection) -> None:
    eid, wid = run_item(conn)
    actual(conn, wid, "skipped")
    row = by_id(view(conn, "15:00"), eid)
    assert row["training"]["fact"]["kind"] == "skipped"
    assert row["due"] is True


@pytest.mark.parametrize("done", [1, 0])
def test_manual_mark_clears_training_due(conn: sqlite3.Connection, done: int) -> None:
    eid, wid = run_item(conn)
    actual(conn, wid, "skipped")
    save_mark(conn, mark(eid, "done", done=done), at("09:50"))
    conn.commit()
    assert by_id(view(conn, "15:00"), eid)["due"] is False


def test_feel_does_not_clear_training_due(conn: sqlite3.Connection) -> None:
    eid, _ = run_item(conn)
    save_mark(conn, mark(eid, "feel", score=4), at("09:50"))
    conn.commit()
    assert by_id(view(conn, "15:00"), eid)["due"] is True


def test_fact_of_another_workout_does_not_clear_due(conn: sqlite3.Connection) -> None:
    eid, _ = run_item(conn)
    other = workout(conn)
    actual(conn, other, activity_id=activity(conn))
    assert by_id(view(conn, "15:00"), eid)["due"] is True


UNLINKED = [None, 9999]


@pytest.mark.parametrize("workout_id", UNLINKED)
def test_unlinked_training_has_no_training_key(
    conn: sqlite3.Connection, workout_id: int | None
) -> None:
    eid = item(conn, "09:00", "09:40", kind="training", workout_id=workout_id)
    assert "training" not in by_id(view(conn, "15:00"), eid)


@pytest.mark.parametrize("workout_id", UNLINKED)
def test_unlinked_past_training_is_due_until_marked(
    conn: sqlite3.Connection, workout_id: int | None
) -> None:
    eid = item(conn, "09:00", "09:40", kind="training", workout_id=workout_id)
    assert by_id(view(conn, "15:00"), eid)["due"] is True
    save_mark(conn, mark(eid, "done", done=0), at("09:50"))
    conn.commit()
    assert by_id(view(conn, "15:00"), eid)["due"] is False


@pytest.mark.parametrize("workout_id", UNLINKED)
def test_unlinked_training_takes_done_feel_and_slip(
    conn: sqlite3.Connection, workout_id: int | None
) -> None:
    eid = item(conn, "09:00", "09:40", kind="training", workout_id=workout_id)
    save_mark(conn, mark(eid, "done", done=1), at("09:50"))
    save_mark(conn, mark(eid, "feel", score=4), at("09:51"))
    save_mark(conn, mark(eid, "slip", text="устал"), at("09:52"))
    conn.commit()
    marks = by_id(view(conn, "15:00"), eid)["marks"]
    assert marks["done"]["done"] == 1
    assert [f["score"] for f in marks["feel"]] == [4]
    assert [s["text"] for s in marks["slips"]] == ["устал"]


def test_meal_remaining_counts_calories_burned_that_day(conn: sqlite3.Connection) -> None:
    for key, value in [
        ("sex", "m"),
        ("birth_date", "1990-01-15"),
        ("height_cm", "180"),
        ("activity_level", "light"),
    ]:
        set_value(conn, key, value, "manual", "2026-10-01T10:00:00")
    add_weight(conn, {"measured_at": "2026-11-06 07:00:00", "weight_kg": 80.0})
    breakfast = meal(conn)
    conn.commit()
    before = by_id(view(conn, "15:00"), breakfast)["meal"]["remaining"]
    activity(conn, 1, calories=600.0)
    after = by_id(view(conn, "15:00"), breakfast)["meal"]["remaining"]
    assert after["kcal"] > before["kcal"]
