"""get_overload(date), snapshot overload / evening_done_today / workload_ahead[].overloaded,
get_wellbeing и get_deviations с вечерними оценками. Синтетические данные."""

import sqlite3
from datetime import date, timedelta

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, rows, tool_names
from workload_fakes import stored_event

from ai_coach.mcp_server.tools import MAX_CHARS
from ai_coach.store.workload import replace_calendar_window, upsert_counter

DAY = "2026-10-07"


def shift(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


def feel(conn: sqlite3.Connection, day: str, at: str, **fields: object) -> None:
    values = {"date": day, "logged_at": f"{day} {at}", "score": 3, **fields}
    names = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO wellbeing_log ({names}) VALUES ({marks})", tuple(values.values()))


def heavy_day(conn: sqlite3.Connection, day: str) -> None:
    """Работа 08:00-22:00: много часов и вечер."""
    event = stored_event(
        uid=f"w-{day}", start_at=f"{day}T08:00:00", end_at=f"{day}T22:00:00", calendar="Work"
    )
    replace_calendar_window(conn, day, day, [event])


def heavy_days(conn: sqlite3.Connection, first: str, count: int) -> None:
    for number in range(count):
        heavy_day(conn, shift(first, number))


def manual(conn: sqlite3.Connection, day: str, kind: str, value: float) -> None:
    upsert_counter(
        conn,
        {
            "date": day,
            "kind": kind,
            "value": value,
            "source": "manual",
            "raw_json": {},
            "synced_at": "2026-10-08T10:00:00",
        },
    )


def kinds(conn: sqlite3.Connection, day: str = DAY) -> list[str]:
    return [r["kind"] for r in call(conn, "get_overload", date=day)["signals"]]


# --- get_overload ---


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_overload" in tool_names(conn)


def test_overload_has_date_total_days_and_signals(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_overload", date=DAY)
    assert {"date", "total", "days", "signals"} <= set(answer)
    assert answer["date"] == DAY
    assert answer["signals"] == []


def test_overload_total_of_a_heavy_day_is_above_a_light_one(conn: sqlite3.Connection) -> None:
    heavy_day(conn, DAY)
    assert (
        call(conn, "get_overload", date=DAY)["total"]
        > call(conn, "get_overload", date=shift(DAY, -1))["total"]
    )


def test_overload_days_end_with_the_checked_day(conn: sqlite3.Connection) -> None:
    days = call(conn, "get_overload", date=DAY)["days"]
    assert days[-1]["date"] == DAY
    assert [d["date"] for d in days] == sorted(d["date"] for d in days)


def test_overload_days_show_manual_hours(conn: sqlite3.Connection) -> None:
    manual(conn, DAY, "work_hours", 3.0)
    days = call(conn, "get_overload", date=DAY)["days"]
    assert days[-1]["manual_work_hours"] == 3.0
    assert days[-2]["manual_work_hours"] is None


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


def test_overload_days_show_screen_hours(conn: sqlite3.Connection) -> None:
    screen(conn, DAY, "screen_work_hours", 3.25)
    screen(conn, DAY, "screen_hobby_hours", 0)
    days = call(conn, "get_overload", date=DAY)["days"]
    assert days[-1]["screen_work_hours"] == 3.25
    assert days[-1]["screen_hobby_hours"] == 0
    assert days[-2]["screen_work_hours"] is None
    assert days[-2]["screen_hobby_hours"] is None


def test_overload_days_do_not_show_browser_and_evening_screen(conn: sqlite3.Connection) -> None:
    screen(conn, DAY, "screen_browser_hours", 2.0)
    screen(conn, DAY, "screen_evening_hours", 2.0)
    day = call(conn, "get_overload", date=DAY)["days"][-1]
    assert "screen_browser_hours" not in day
    assert "screen_evening_hours" not in day


def test_screen_hours_count_in_overload_total(conn: sqlite3.Connection) -> None:
    before = call(conn, "get_overload", date=DAY)["total"]
    screen(conn, DAY, "screen_work_hours", 8.0)
    assert call(conn, "get_overload", date=DAY)["total"] > before


def test_screen_overrides_calendar_in_overload_total(conn: sqlite3.Connection) -> None:
    heavy_day(conn, DAY)
    heavy = call(conn, "get_overload", date=DAY)["total"]
    screen(conn, DAY, "screen_work_hours", 0)
    assert call(conn, "get_overload", date=DAY)["total"] < heavy


def test_manual_overrides_screen_in_overload_total(conn: sqlite3.Connection) -> None:
    screen(conn, DAY, "screen_work_hours", 8.0)
    manual(conn, DAY, "work_hours", 0.0)
    assert call(conn, "get_overload", date=DAY)["total"] == 0


def test_screen_hours_make_a_run_of_heavy_days(conn: sqlite3.Connection) -> None:
    for number in range(14):
        screen(conn, shift(DAY, -number), "screen_work_hours", 12.0)
    assert "total_streak" in kinds(conn)


def test_screen_zero_stops_calendar_run_of_heavy_days(conn: sqlite3.Connection) -> None:
    heavy_days(conn, shift(DAY, -13), 14)
    for number in range(14):
        screen(conn, shift(DAY, -number), "screen_work_hours", 0)
    assert "total_streak" not in kinds(conn)


def test_screen_work_on_weekend_is_weekend_work_signal(conn: sqlite3.Connection) -> None:
    saturday = "2026-10-10"
    screen(conn, saturday, "screen_work_hours", 4.0)
    assert "weekend_work" in kinds(conn, saturday)


def test_overload_without_data_is_empty(conn: sqlite3.Connection) -> None:
    assert kinds(conn) == []


def test_overload_without_load_says_so(conn: sqlite3.Connection) -> None:
    assert "coach sync" in call(conn, "get_overload", date=DAY)["load_error"]


def test_overload_bad_date_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_overload", date="07.10.2026")


def test_overload_catches_a_run_of_heavy_days(conn: sqlite3.Connection) -> None:
    heavy_days(conn, shift(DAY, -13), 14)
    found = kinds(conn)
    assert "total_streak" in found
    assert "evening_streak" in found


def test_overload_run_must_reach_the_checked_day(conn: sqlite3.Connection) -> None:
    heavy_days(conn, shift(DAY, -13), 10)
    assert "total_streak" not in kinds(conn)


def test_overload_of_a_light_period_has_no_streaks(conn: sqlite3.Connection) -> None:
    for number in range(14):
        day = shift(DAY, -number)
        replace_calendar_window(
            conn,
            day,
            day,
            [stored_event(uid=f"l-{day}", start_at=f"{day}T10:00:00", end_at=f"{day}T11:00:00")],
        )
    found = kinds(conn)
    assert "total_streak" not in found
    assert "evening_streak" not in found


def test_manual_hours_override_calendar_in_overload(conn: sqlite3.Connection) -> None:
    heavy_days(conn, shift(DAY, -13), 14)
    for number in range(14):
        manual(conn, shift(DAY, -number), "work_hours", 1.0)
    assert "total_streak" not in kinds(conn)


def test_overload_text_has_no_event_titles(conn: sqlite3.Connection) -> None:
    heavy_days(conn, shift(DAY, -13), 14)
    assert "Синтетическая встреча" not in call_text(conn, "get_overload", date=DAY)


# --- snapshot ---


def test_snapshot_has_overload_section(conn: sqlite3.Connection) -> None:
    section = call(conn, "get_morning_snapshot", date=DAY)["overload"]
    assert section["signals"] == []
    assert section["date"] == DAY


def test_snapshot_overload_lists_signals(conn: sqlite3.Connection) -> None:
    heavy_days(conn, shift(DAY, -13), 14)
    section = call(conn, "get_morning_snapshot", date=DAY)["overload"]
    assert "total_streak" in [r["kind"] for r in section["signals"]]


def test_snapshot_ahead_rows_have_overloaded_flag(conn: sqlite3.Connection) -> None:
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    assert ahead
    assert all(r["overloaded"] is False for r in ahead)


def test_snapshot_ahead_marks_heavy_day(conn: sqlite3.Connection) -> None:
    heavy_day(conn, shift(DAY, 2))
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    flags = {r["date"]: r["overloaded"] for r in ahead}
    assert flags[shift(DAY, 2)] is True
    assert flags[shift(DAY, 3)] is False


def test_snapshot_ahead_still_has_no_counters(conn: sqlite3.Connection) -> None:
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    assert all("todo_open" not in r for r in ahead)


def test_snapshot_ahead_marks_day_heavy_by_screen_hours(conn: sqlite3.Connection) -> None:
    screen(conn, shift(DAY, 2), "screen_work_hours", 14.0)
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    flags = {r["date"]: r["overloaded"] for r in ahead}
    assert flags[shift(DAY, 2)] is True
    assert flags[shift(DAY, 3)] is False


def test_snapshot_ahead_zero_screen_beats_heavy_calendar(conn: sqlite3.Connection) -> None:
    heavy_day(conn, shift(DAY, 2))
    screen(conn, shift(DAY, 2), "screen_work_hours", 0)
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    assert {r["date"]: r["overloaded"] for r in ahead}[shift(DAY, 2)] is False


def test_snapshot_ahead_has_no_screen_fields(conn: sqlite3.Connection) -> None:
    screen(conn, shift(DAY, 2), "screen_work_hours", 14.0)
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    assert all(not [k for k in r if k.startswith("screen_")] for r in ahead)


def test_snapshot_with_seven_screen_days_fits_the_limit(conn: sqlite3.Connection) -> None:
    for number in range(30):
        for kind in (
            "screen_work_hours",
            "screen_hobby_hours",
            "screen_browser_hours",
            "screen_evening_hours",
        ):
            screen(conn, shift(DAY, -number), kind, 7.77)
        feel(conn, shift(DAY, -number), "20:00:00", mood=2, stress=5, text="т" * 200)
    heavy_days(conn, shift(DAY, -13), 21)
    answer = call_text(conn, "get_morning_snapshot", date=DAY)
    assert len(answer) <= MAX_CHARS
    assert "screen_work_hours" in answer


def test_snapshot_with_overload_fits_the_limit(conn: sqlite3.Connection) -> None:
    heavy_days(conn, shift(DAY, -13), 21)
    for number in range(30):
        feel(conn, shift(DAY, -number), "20:00:00", mood=2, stress=5, text="т" * 200)
    assert len(call_text(conn, "get_morning_snapshot", date=DAY)) <= MAX_CHARS


# --- evening_done_today ---


def test_evening_not_done_without_entries(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_morning_snapshot", date=DAY)["evening_done_today"] is False


def test_morning_entry_without_mood_stress_is_not_evening(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "08:00:00", score=4)
    assert call(conn, "get_morning_snapshot", date=DAY)["evening_done_today"] is False


def test_entry_with_mood_is_evening_done(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", mood=4)
    assert call(conn, "get_morning_snapshot", date=DAY)["evening_done_today"] is True


def test_entry_with_stress_is_evening_done(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", stress=2)
    assert call(conn, "get_morning_snapshot", date=DAY)["evening_done_today"] is True


def test_yesterdays_evening_does_not_count(conn: sqlite3.Connection) -> None:
    feel(conn, shift(DAY, -1), "21:00:00", mood=4, stress=2)
    assert call(conn, "get_morning_snapshot", date=DAY)["evening_done_today"] is False


def test_evening_done_survives_snapshot_trimming(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", mood=4)
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert isinstance(snapshot["evening_done_today"], bool)


# --- wellbeing и deviations ---


def test_wellbeing_rows_have_mood_and_stress(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", mood=2, stress=4)
    feel(conn, DAY, "08:00:00", score=5)
    found = rows(conn, "get_wellbeing", start=DAY, end=DAY)
    assert [(r["mood"], r["stress"]) for r in found] == [(None, None), (2, 4)]


def test_snapshot_wellbeing_has_mood_and_stress(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", mood=2, stress=4)
    found = call(conn, "get_morning_snapshot", date=DAY)["wellbeing"]["rows"]
    assert (found[0]["mood"], found[0]["stress"]) == (2, 4)


def deviation_kinds(conn: sqlite3.Connection) -> list[str]:
    return [r["kind"] for r in rows(conn, "get_deviations", date=DAY)]


def test_low_mood_is_a_deviation(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", score=4, mood=2)
    assert deviation_kinds(conn) == ["mood"]


def test_high_stress_is_a_deviation(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", score=4, stress=4)
    assert deviation_kinds(conn) == ["stress"]


def test_mood_3_stress_3_are_fine(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", score=4, mood=3, stress=3)
    assert deviation_kinds(conn) == []


def test_main_entry_is_the_last_one_for_mood(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", score=4, mood=1)
    feel(conn, DAY, "22:00:00", score=4, mood=4)
    assert deviation_kinds(conn) == []


def test_later_entry_without_mood_keeps_the_evening_mood(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", score=4, mood=1)
    feel(conn, DAY, "22:00:00", score=4)
    assert deviation_kinds(conn) == ["mood"]


def test_later_entry_without_stress_keeps_the_evening_stress(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "21:00:00", score=4, stress=5)
    feel(conn, DAY, "22:00:00", score=4, mood=4)
    assert deviation_kinds(conn) == ["stress"]


def test_later_mood_replaces_earlier_one(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, "20:00:00", score=4, mood=4)
    feel(conn, DAY, "22:00:00", score=4, mood=1)
    assert deviation_kinds(conn) == ["mood"]


def test_mood_of_another_day_does_not_leak(conn: sqlite3.Connection) -> None:
    feel(conn, shift(DAY, -1), "21:00:00", score=4, mood=1, stress=5)
    feel(conn, DAY, "08:00:00", score=4)
    assert deviation_kinds(conn) == []


def test_overload_catches_a_falling_mood(conn: sqlite3.Connection) -> None:
    for number in range(7):
        day = shift(DAY, -number)
        mood = 1 if number < 3 else 5
        feel(conn, day, "21:00:00", score=4, mood=mood)
    assert "recovery_drop" in kinds(conn)


def test_overload_catches_a_rising_stress(conn: sqlite3.Connection) -> None:
    for number in range(7):
        day = shift(DAY, -number)
        feel(conn, day, "21:00:00", score=4, stress=5 if number < 3 else 1)
    assert "recovery_drop" in kinds(conn)


def test_overload_without_evening_marks_has_no_recovery_drop(conn: sqlite3.Connection) -> None:
    assert "recovery_drop" not in kinds(conn)


def test_overload_days_take_the_last_nonempty_mood_of_the_day(conn: sqlite3.Connection) -> None:
    for number in range(7):
        day = shift(DAY, -number)
        recent = number < 3
        feel(conn, day, "21:00:00", score=4, mood=1 if recent else 5)
        feel(conn, day, "22:00:00", score=4)
    assert "recovery_drop" in kinds(conn)


def test_overload_mood_drop_with_baseline_in_days_7_to_9(conn: sqlite3.Connection) -> None:
    for number in (0, 1, 2):
        feel(conn, shift(DAY, -number), "21:00:00", score=4, mood=1)
    for number in (7, 8, 9):
        feel(conn, shift(DAY, -number), "21:00:00", score=4, mood=5)
    assert "recovery_drop" in kinds(conn)


def test_overload_stress_without_later_entry_value_is_kept(conn: sqlite3.Connection) -> None:
    for number in range(7):
        day = shift(DAY, -number)
        feel(conn, day, "21:00:00", score=4, stress=5 if number < 3 else 1)
        feel(conn, day, "22:30:00", score=4, mood=3)
    assert "recovery_drop" in kinds(conn)
