import sqlite3
from typing import Any

import pytest
from workload_fakes import stored_event

from ai_coach.store.workload import replace_calendar_window, upsert_counter
from ai_coach.workload.service import workload_day, workload_series

WED = "2026-10-07"
THU = "2026-10-08"
SAT = "2026-10-10"
SUN = "2026-10-11"


def put(conn: sqlite3.Connection, *events: dict[str, Any]) -> None:
    replace_calendar_window(conn, "2026-10-01", "2026-10-31", list(events))


def slot(start: str, end: str, category: str = "work", uid: str | None = None, **fields: Any):
    """start/end вида '2026-10-07 10:00'."""
    return stored_event(
        category,
        uid=uid or f"u-{start}-{end}",
        start_at=start.replace(" ", "T") + ":00",
        end_at=end.replace(" ", "T") + ":00",
        **fields,
    )


def test_work_hours_sum_of_events(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 11:30"), slot(f"{WED} 14:00", f"{WED} 15:00"))
    assert workload_day(conn, WED)["work_hours"] == pytest.approx(2.5)


def test_day_without_events_is_zero(conn: sqlite3.Connection) -> None:
    day = workload_day(conn, WED)
    assert day["date"] == WED
    assert day["work_hours"] == 0
    assert day["work_evening_hours"] == 0


def test_overlapping_events_are_united(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 12:00"), slot(f"{WED} 11:00", f"{WED} 13:00"))
    assert workload_day(conn, WED)["work_hours"] == pytest.approx(3.0)


def test_nested_event_does_not_add_hours(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 13:00"), slot(f"{WED} 11:00", f"{WED} 12:00"))
    assert workload_day(conn, WED)["work_hours"] == pytest.approx(3.0)


def test_recurring_instances_count_each_on_own_day(conn: sqlite3.Connection) -> None:
    put(
        conn,
        slot(f"{WED} 10:00", f"{WED} 11:00", uid="series"),
        slot(f"{THU} 10:00", f"{THU} 11:00", uid="series"),
    )
    assert workload_day(conn, WED)["work_hours"] == pytest.approx(1.0)
    assert workload_day(conn, THU)["work_hours"] == pytest.approx(1.0)


def test_all_day_work_event_gives_flag_not_hours(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 00:00", f"{THU} 00:00", all_day=True))
    day = workload_day(conn, WED)
    assert day["all_day_work"] is True
    assert day["work_hours"] == 0


def test_no_all_day_flag_without_all_day_event(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 11:00"))
    assert workload_day(conn, WED)["all_day_work"] is False


def test_all_day_personal_event_does_not_set_work_flag(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 00:00", f"{THU} 00:00", "personal", all_day=True))
    assert workload_day(conn, WED)["all_day_work"] is False


def test_cancelled_event_is_not_counted(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 11:00", status="cancelled"))
    assert workload_day(conn, WED)["work_hours"] == 0


def test_declined_event_is_not_counted(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 11:00", my_status="declined"))
    assert workload_day(conn, WED)["work_hours"] == 0


def test_tentative_event_is_counted(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 11:00", status="tentative", my_status="tentative"))
    assert workload_day(conn, WED)["work_hours"] == pytest.approx(1.0)


def test_event_from_18_30_to_19_30_gives_half_hour_evening(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 18:30", f"{WED} 19:30"))
    day = workload_day(conn, WED)
    assert day["work_hours"] == pytest.approx(1.0)
    assert day["work_evening_hours"] == pytest.approx(0.5)


def test_event_ending_at_19_00_gives_no_evening(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 17:00", f"{WED} 19:00"))
    assert workload_day(conn, WED)["work_evening_hours"] == 0


def test_event_fully_after_19_is_all_evening(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 20:00", f"{WED} 21:30"))
    assert workload_day(conn, WED)["work_evening_hours"] == pytest.approx(1.5)


def test_evening_overlap_is_not_double_counted(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 19:00", f"{WED} 21:00"), slot(f"{WED} 20:00", f"{WED} 22:00"))
    assert workload_day(conn, WED)["work_evening_hours"] == pytest.approx(3.0)


def test_event_across_midnight_is_cut_by_days(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 22:00", f"{THU} 01:00"))
    wed, thu = workload_day(conn, WED), workload_day(conn, THU)
    assert wed["work_hours"] == pytest.approx(2.0)
    assert wed["work_evening_hours"] == pytest.approx(2.0)
    assert thu["work_hours"] == pytest.approx(1.0)
    assert thu["work_evening_hours"] == 0


def test_saturday_is_weekend(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{SAT} 10:00", f"{SAT} 12:00"))
    day = workload_day(conn, SAT)
    assert day["weekend"] is True
    assert day["work_hours"] == pytest.approx(2.0)


def test_sunday_is_weekend(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{SUN} 10:00", f"{SUN} 11:00"))
    assert workload_day(conn, SUN)["weekend"] is True


def test_weekday_is_not_weekend(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 12:00"))
    assert workload_day(conn, WED)["weekend"] is False


def test_personal_and_hobby_have_own_hours(conn: sqlite3.Connection) -> None:
    put(
        conn,
        slot(f"{WED} 10:00", f"{WED} 11:00", "personal"),
        slot(f"{WED} 12:00", f"{WED} 14:00", "hobby"),
    )
    day = workload_day(conn, WED)
    assert day["personal_hours"] == pytest.approx(1.0)
    assert day["hobby_hours"] == pytest.approx(2.0)
    assert day["work_hours"] == 0


def test_personal_events_follow_same_rules(conn: sqlite3.Connection) -> None:
    put(
        conn,
        slot(f"{WED} 10:00", f"{WED} 12:00", "personal"),
        slot(f"{WED} 11:00", f"{WED} 13:00", "personal"),
        slot(f"{WED} 15:00", f"{WED} 16:00", "personal", status="cancelled"),
    )
    assert workload_day(conn, WED)["personal_hours"] == pytest.approx(3.0)


def test_unknown_calendar_events_are_not_in_load(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 12:00", "unknown"))
    day = workload_day(conn, WED)
    assert (day["work_hours"], day["personal_hours"], day["hobby_hours"]) == (0, 0, 0)


def test_work_events_do_not_mix_with_other_categories(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 10:00", f"{WED} 11:00"), slot(f"{WED} 10:00", f"{WED} 12:00", "hobby"))
    assert workload_day(conn, WED)["work_hours"] == pytest.approx(1.0)


def test_day_has_counters_of_that_day(conn: sqlite3.Connection) -> None:
    for kind, value in (("todo_closed", 3), ("grooming_done", 5)):
        upsert_counter(
            conn,
            {
                "date": WED,
                "kind": kind,
                "value": value,
                "source": "x",
                "raw_json": {},
                "synced_at": "2026-10-08T10:00:00",
            },
        )
    day = workload_day(conn, WED)
    assert day["todo_closed"] == 3
    assert day["grooming_done"] == 5


def test_missing_counter_is_none(conn: sqlite3.Connection) -> None:
    assert workload_day(conn, WED)["todo_open"] is None


def counter(conn: sqlite3.Connection, kind: str, value: float, source: str = "screen") -> None:
    upsert_counter(
        conn,
        {
            "date": WED,
            "kind": kind,
            "value": value,
            "source": source,
            "raw_json": None,
            "synced_at": "2026-10-08T10:00:00",
        },
    )


def test_screen_hours_keep_fraction(conn: sqlite3.Connection) -> None:
    counter(conn, "screen_work_hours", 2.25)
    day = workload_series(conn, WED, WED)[0]
    assert day["screen_work_hours"] == 2.25
    assert isinstance(day["screen_work_hours"], float)


def test_all_four_screen_counters_are_in_the_row(conn: sqlite3.Connection) -> None:
    for kind, value in (
        ("screen_work_hours", 3.5),
        ("screen_hobby_hours", 1.25),
        ("screen_browser_hours", 0.75),
        ("screen_evening_hours", 2.5),
    ):
        counter(conn, kind, value)
    day = workload_series(conn, WED, WED)[0]
    assert [day[k] for k in sorted(day) if k.startswith("screen_")] == [0.75, 2.5, 1.25, 3.5]


def test_screen_zero_stays_zero_not_none(conn: sqlite3.Connection) -> None:
    counter(conn, "screen_work_hours", 0)
    assert workload_series(conn, WED, WED)[0]["screen_work_hours"] == 0


def test_todo_counter_stays_int_next_to_screen_hours(conn: sqlite3.Connection) -> None:
    counter(conn, "todo_open", 4, "todo")
    counter(conn, "screen_work_hours", 2.25)
    day = workload_series(conn, WED, WED)[0]
    assert day["todo_open"] == 4
    assert isinstance(day["todo_open"], int)


def test_series_without_screen_counters_has_none_fields(conn: sqlite3.Connection) -> None:
    day = workload_series(conn, WED, WED)[0]
    for kind in (
        "screen_work_hours",
        "screen_hobby_hours",
        "screen_browser_hours",
        "screen_evening_hours",
    ):
        assert day[kind] is None


def test_screen_counter_of_another_day_is_not_taken(conn: sqlite3.Connection) -> None:
    counter(conn, "screen_work_hours", 2.0)
    assert workload_series(conn, THU, THU)[0]["screen_work_hours"] is None


def test_series_has_row_per_day_in_order(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{THU} 10:00", f"{THU} 11:00"))
    series = workload_series(conn, WED, SAT)
    assert [d["date"] for d in series] == [WED, THU, "2026-10-09", SAT]
    assert [d["work_hours"] for d in series] == [0, pytest.approx(1.0), 0, 0]


def test_series_includes_midnight_tail_of_previous_day_event(conn: sqlite3.Connection) -> None:
    put(conn, slot(f"{WED} 23:00", f"{THU} 02:00"))
    assert workload_series(conn, THU, THU)[0]["work_hours"] == pytest.approx(2.0)
