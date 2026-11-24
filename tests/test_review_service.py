"""ai_coach.review.service.weekly_review(conn, today: date, weeks=4) - недельный обзор (шаг v2.5).

Недели ISO Пн-Вс, от старой к новой; последняя - неделя today (partial). Поля: week_start,
week_end (воскресенье), partial, tss, work_hours, evening_hours, weekend_work_hours,
todo_closed, todo_open, mood, stress, sleep (среднее sleep_score), readiness, days_with_data,
delta (dict с теми же ключами метрик: разница с предыдущей неделей; у первой недели None).
Синтетические данные, суммы - ручной расчёт (см. комментарии к фикстуре).
"""

import sqlite3
from datetime import date

import pytest
from workload_fakes import stored_event

from ai_coach.review.service import weekly_review
from ai_coach.store.garmin_data import upsert_activity, upsert_daily_metrics
from ai_coach.store.workload import replace_calendar_window, upsert_counter

WED = date(2026, 10, 14)


def work(conn: sqlite3.Connection, day: str, start: str, end: str) -> None:
    event = stored_event(
        uid=f"w-{day}", start_at=f"{day}T{start}:00", end_at=f"{day}T{end}:00", calendar="Work"
    )
    replace_calendar_window(conn, day, day, [event])


def counter(conn: sqlite3.Connection, day: str, kind: str, value: float) -> None:
    values = {"date": day, "kind": kind, "value": value, "source": "manual"}
    upsert_counter(conn, {**values, "raw_json": {}, "synced_at": "2026-10-08T10:00:00"})


def strength(conn: sqlite3.Connection, activity_id: int, day: str, seconds: int) -> None:
    upsert_activity(
        conn,
        {
            "activity_id": activity_id,
            "start_time_local": f"{day} 18:00:00",
            "type_key": "strength_training",
            "duration_s": seconds,
            "raw_json": {},
        },
    )


def metric(conn: sqlite3.Connection, day: str, sleep: int, readiness: int) -> None:
    upsert_daily_metrics(
        conn,
        {
            "date": day,
            "sleep_score": sleep,
            "readiness_score": readiness,
            "raw_json": {"sleep": {"restingHeartRate": 50}},
        },
    )


def feel(conn: sqlite3.Connection, day: str, mood: int, stress: int) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, logged_at, score, mood, stress) VALUES (?, ?, 3, ?, ?)",
        (day, f"{day} 21:00:00", mood, stress),
    )


@pytest.fixture
def filled(conn: sqlite3.Connection) -> sqlite3.Connection:
    # Неделя A, 2026-09-28..10-04.
    strength(conn, 1, "2026-10-01", 3600)  # 35 TSS в час
    strength(conn, 2, "2026-10-02", 1800)  # 17.5; всего TSS 52.5
    work(conn, "2026-09-29", "09:00", "17:00")  # 8 ч
    work(conn, "2026-10-01", "10:00", "21:00")  # 11 ч, вечер (после 19:00) 2 ч
    work(conn, "2026-10-03", "10:00", "12:00")  # суббота, 2 ч; итого 21 / 2 / 2
    counter(conn, "2026-09-29", "todo_closed", 2)
    counter(conn, "2026-10-02", "todo_closed", 3)  # закрыто 5
    counter(conn, "2026-10-04", "todo_open", 7)
    feel(conn, "2026-10-01", 5, 1)
    feel(conn, "2026-10-02", 2, 2)  # mood 3.5, stress 1.5
    metric(conn, "2026-10-01", 80, 60)
    metric(conn, "2026-10-02", 70, 80)  # sleep 75, readiness 70
    # Неделя B, 2026-10-05..10-11.
    strength(conn, 3, "2026-10-06", 7200)  # TSS 70
    work(conn, "2026-10-06", "08:00", "18:00")  # 10 ч
    work(conn, "2026-10-07", "14:00", "22:00")  # 8 ч, вечер 3 ч
    work(conn, "2026-10-11", "11:00", "15:00")  # воскресенье 4 ч; итого 22 / 3 / 4
    counter(conn, "2026-10-08", "todo_closed", 1)
    counter(conn, "2026-10-09", "todo_open", 4)
    feel(conn, "2026-10-08", 3, 4)
    metric(conn, "2026-10-08", 60, 50)
    return conn


def by_start(rows: list[dict]) -> dict[str, dict]:
    return {r["week_start"]: r for r in rows}


def test_detachment_fields_do_not_change_weekly_review(filled: sqlite3.Connection) -> None:
    before = weekly_review(filled, WED)
    filled.execute(
        "UPDATE wellbeing_log SET work_thoughts = 5, hindrance = 5, valuable = 1, flow = 0"
    )
    assert weekly_review(filled, WED) == before


# --- границы недель ---


def test_default_is_four_weeks_oldest_first(conn: sqlite3.Connection) -> None:
    starts = [r["week_start"] for r in weekly_review(conn, WED)]
    assert starts == ["2026-09-21", "2026-09-28", "2026-10-05", "2026-10-12"]


def test_weeks_argument_sets_row_count(conn: sqlite3.Connection) -> None:
    assert len(weekly_review(conn, WED, weeks=2)) == 2
    assert len(weekly_review(conn, WED, weeks=12)) == 12


def test_weeks_start_on_monday_end_on_sunday(conn: sqlite3.Connection) -> None:
    for row in weekly_review(conn, WED):
        assert date.fromisoformat(row["week_start"]).weekday() == 0
        assert date.fromisoformat(row["week_end"]).weekday() == 6
        assert (
            date.fromisoformat(row["week_end"]) - date.fromisoformat(row["week_start"])
        ).days == 6


def test_sunday_belongs_to_the_week_that_it_closes(conn: sqlite3.Connection) -> None:
    rows = weekly_review(conn, date(2026, 10, 11), weeks=2)
    assert [r["week_start"] for r in rows] == ["2026-09-28", "2026-10-05"]


def test_monday_starts_a_new_week(conn: sqlite3.Connection) -> None:
    rows = weekly_review(conn, date(2026, 10, 12), weeks=2)
    assert [r["week_start"] for r in rows] == ["2026-10-05", "2026-10-12"]


def test_year_border_week_53(conn: sqlite3.Connection) -> None:
    rows = weekly_review(conn, date(2027, 1, 1), weeks=2)
    assert [r["week_start"] for r in rows] == ["2026-12-21", "2026-12-28"]
    assert rows[-1]["week_end"] == "2027-01-03"


def test_new_year_monday_starts_new_week(conn: sqlite3.Connection) -> None:
    rows = weekly_review(conn, date(2027, 1, 4), weeks=2)
    assert [r["week_start"] for r in rows] == ["2026-12-28", "2027-01-04"]


# --- partial ---


def test_only_current_week_is_partial(conn: sqlite3.Connection) -> None:
    assert [r["partial"] for r in weekly_review(conn, WED)] == [False, False, False, True]


def test_week_before_monday_is_complete(conn: sqlite3.Connection) -> None:
    rows = weekly_review(conn, date(2026, 10, 12), weeks=2)
    assert [r["partial"] for r in rows] == [False, True]


# --- суммы ---


def test_tss_sum_of_week(filled: sqlite3.Connection) -> None:
    rows = by_start(weekly_review(filled, WED))
    assert rows["2026-09-28"]["tss"] == pytest.approx(52.5)
    assert rows["2026-10-05"]["tss"] == pytest.approx(70.0)


def test_work_hours_sum_of_week(filled: sqlite3.Connection) -> None:
    rows = by_start(weekly_review(filled, WED))
    assert rows["2026-09-28"]["work_hours"] == pytest.approx(21.0)
    assert rows["2026-10-05"]["work_hours"] == pytest.approx(22.0)


def test_evening_hours_sum_of_week(filled: sqlite3.Connection) -> None:
    rows = by_start(weekly_review(filled, WED))
    assert rows["2026-09-28"]["evening_hours"] == pytest.approx(2.0)
    assert rows["2026-10-05"]["evening_hours"] == pytest.approx(3.0)


def test_weekend_work_hours_sum_of_week(filled: sqlite3.Connection) -> None:
    rows = by_start(weekly_review(filled, WED))
    assert rows["2026-09-28"]["weekend_work_hours"] == pytest.approx(2.0)
    assert rows["2026-10-05"]["weekend_work_hours"] == pytest.approx(4.0)


def screen(conn: sqlite3.Connection, day: str, kind: str, value: float) -> None:
    values = {"date": day, "kind": kind, "value": value, "source": "screen"}
    upsert_counter(conn, {**values, "raw_json": None, "synced_at": "2026-10-08T10:00:00"})


def test_screen_hours_replace_calendar_in_work_hours(conn: sqlite3.Connection) -> None:
    work(conn, "2026-10-13", "09:00", "17:00")  # календарь 8 ч
    screen(conn, "2026-10-13", "screen_work_hours", 3.5)
    assert weekly_review(conn, WED, weeks=1)[0]["work_hours"] == pytest.approx(3.5)


def test_screen_zero_replaces_calendar_in_work_hours(conn: sqlite3.Connection) -> None:
    work(conn, "2026-10-13", "09:00", "17:00")
    screen(conn, "2026-10-13", "screen_work_hours", 0)
    assert weekly_review(conn, WED, weeks=1)[0]["work_hours"] == 0


def test_manual_hours_beat_screen_hours_in_work_hours(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-13", "screen_work_hours", 3.5)
    counter(conn, "2026-10-13", "work_hours", 2.0)  # ручные часы: kind work_hours, source manual
    assert weekly_review(conn, WED, weeks=1)[0]["work_hours"] == pytest.approx(2.0)


def test_screen_work_evening_hours_sum_in_evening_hours(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-12", "screen_work_evening_hours", 1.0)
    screen(conn, "2026-10-13", "screen_work_evening_hours", 1.0)
    assert weekly_review(conn, WED, weeks=1)[0]["evening_hours"] == pytest.approx(2.0)


def test_screen_zero_work_evening_replaces_calendar_evening(conn: sqlite3.Connection) -> None:
    work(conn, "2026-10-13", "19:00", "22:00")  # календарь: 3 ч вечера
    screen(conn, "2026-10-13", "screen_work_evening_hours", 0)
    assert weekly_review(conn, WED, weeks=1)[0]["evening_hours"] == 0


def test_calendar_evening_is_taken_when_screen_has_none(conn: sqlite3.Connection) -> None:
    work(conn, "2026-10-12", "19:00", "21:00")  # календарь 2 ч, экрана нет
    screen(conn, "2026-10-13", "screen_work_evening_hours", 1.5)
    assert weekly_review(conn, WED, weeks=1)[0]["evening_hours"] == pytest.approx(3.5)


def test_screen_and_calendar_days_are_summed_per_day(conn: sqlite3.Connection) -> None:
    work(conn, "2026-10-12", "09:00", "11:00")  # календарь 2 ч, экрана нет
    screen(conn, "2026-10-13", "screen_work_hours", 3.5)
    assert weekly_review(conn, WED, weeks=1)[0]["work_hours"] == pytest.approx(5.5)


def test_screen_hours_on_weekend_go_to_weekend_work_hours(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-10", "screen_work_hours", 4.0)  # суббота недели B
    screen(conn, "2026-10-09", "screen_work_hours", 6.0)  # пятница
    row = by_start(weekly_review(conn, WED))["2026-10-05"]
    assert row["weekend_work_hours"] == pytest.approx(4.0)
    assert row["work_hours"] == pytest.approx(10.0)


def test_day_with_only_screen_counter_is_a_day_with_data(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-13", "screen_work_hours", 3.5)
    assert weekly_review(conn, WED, weeks=1)[0]["days_with_data"] == 1


def test_day_with_only_zero_screen_counter_is_a_day_with_data(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-13", "screen_work_hours", 0)
    assert weekly_review(conn, WED, weeks=1)[0]["days_with_data"] == 1


def test_screen_days_are_counted_once_with_other_data(conn: sqlite3.Connection) -> None:
    work(conn, "2026-10-13", "09:00", "10:00")
    screen(conn, "2026-10-13", "screen_work_hours", 3.5)
    screen(conn, "2026-10-12", "screen_work_hours", 1.0)
    assert weekly_review(conn, WED, weeks=1)[0]["days_with_data"] == 2


def test_todo_closed_sum_and_todo_open(filled: sqlite3.Connection) -> None:
    rows = by_start(weekly_review(filled, WED))
    assert rows["2026-09-28"]["todo_closed"] == 5
    assert rows["2026-10-05"]["todo_closed"] == 1
    assert rows["2026-09-28"]["todo_open"] == 7
    assert rows["2026-10-05"]["todo_open"] == 4


def test_activity_outside_week_is_not_counted(filled: sqlite3.Connection) -> None:
    strength(filled, 9, "2026-10-04", 3600)  # воскресенье недели A
    strength(filled, 10, "2026-10-12", 3600)  # понедельник недели C
    rows = by_start(weekly_review(filled, WED))
    assert rows["2026-09-28"]["tss"] == pytest.approx(87.5)
    assert rows["2026-10-05"]["tss"] == pytest.approx(70.0)
    assert rows["2026-10-12"]["tss"] == pytest.approx(35.0)


# --- средние и None ---


def test_means_of_week(filled: sqlite3.Connection) -> None:
    row = by_start(weekly_review(filled, WED))["2026-09-28"]
    assert row["mood"] == pytest.approx(3.5)
    assert row["stress"] == pytest.approx(1.5)
    assert row["sleep"] == pytest.approx(75)
    assert row["readiness"] == pytest.approx(70)


def test_means_without_data_are_none(filled: sqlite3.Connection) -> None:
    row = by_start(weekly_review(filled, WED))["2026-10-12"]
    for key in ["mood", "stress", "sleep", "readiness"]:
        assert row[key] is None


def test_empty_database_means_are_none(conn: sqlite3.Connection) -> None:
    for row in weekly_review(conn, WED):
        assert [row[k] for k in ["mood", "stress", "sleep", "readiness"]] == [None] * 4


def test_empty_week_has_no_hours_and_no_days(filled: sqlite3.Connection) -> None:
    row = by_start(weekly_review(filled, WED))["2026-10-12"]
    assert row["days_with_data"] == 0
    assert not row["work_hours"]
    assert not row["tss"]


def test_stress_none_when_only_mood_is_given(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, logged_at, score, mood) "
        "VALUES ('2026-10-13', '2026-10-13 21:00:00', 3, 4)"
    )
    row = weekly_review(conn, WED, weeks=1)[0]
    assert row["mood"] == pytest.approx(4)
    assert row["stress"] is None


def test_days_with_data_counts_days_not_records(filled: sqlite3.Connection) -> None:
    row = by_start(weekly_review(filled, WED))["2026-10-05"]
    assert 1 <= row["days_with_data"] <= 7


# --- дельты ---


def test_first_week_has_no_delta(filled: sqlite3.Connection) -> None:
    assert weekly_review(filled, WED)[0]["delta"] is None


def test_delta_is_difference_with_previous_week(filled: sqlite3.Connection) -> None:
    delta = by_start(weekly_review(filled, WED))["2026-10-05"]["delta"]
    assert delta["tss"] == pytest.approx(17.5)
    assert delta["work_hours"] == pytest.approx(1.0)
    assert delta["evening_hours"] == pytest.approx(1.0)
    assert delta["weekend_work_hours"] == pytest.approx(2.0)
    assert delta["todo_closed"] == pytest.approx(-4)
    assert delta["mood"] == pytest.approx(-0.5)
    assert delta["sleep"] == pytest.approx(-15)


def test_delta_of_mean_is_none_when_week_has_no_mean(filled: sqlite3.Connection) -> None:
    delta = by_start(weekly_review(filled, WED))["2026-10-12"]["delta"]
    assert delta is not None
    assert delta["mood"] is None


def test_no_rest_hr_gives_none_tss_and_delta(conn: sqlite3.Connection) -> None:
    strength(conn, 9, "2026-10-13", 3600)
    rows = weekly_review(conn, WED)
    assert all(r["tss"] is None for r in rows)
    assert rows[-1]["delta"]["tss"] is None


# --- шаг Н38, партия 3: усталость и раздражительность ---


def rate(conn: sqlite3.Connection, day: str, at: str = "21:00", **marks: int) -> None:
    """Запись самочувствия с заданными оценками (fatigue, irritability, mood, stress)."""
    columns = ", ".join(["date", "logged_at", "score", *marks])
    holders = ", ".join("?" * (3 + len(marks)))
    conn.execute(
        f"INSERT INTO wellbeing_log ({columns}) VALUES ({holders})",
        (day, f"{day} {at}:00", 3, *marks.values()),
    )


def test_fatigue_and_irritability_means_of_week(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-12", fatigue=4)
    rate(conn, "2026-10-13", fatigue=2, irritability=3)
    row = weekly_review(conn, WED, weeks=1)[0]
    assert row["fatigue"] == pytest.approx(3.0)
    assert row["irritability"] == pytest.approx(3.0)


def test_fatigue_and_irritability_none_without_marks(filled: sqlite3.Connection) -> None:
    row = by_start(weekly_review(filled, WED))["2026-09-28"]
    assert row["fatigue"] is None
    assert row["irritability"] is None


def test_fatigue_and_irritability_none_on_empty_database(conn: sqlite3.Connection) -> None:
    for row in weekly_review(conn, WED):
        assert [row["fatigue"], row["irritability"]] == [None, None]


def test_fatigue_keeps_latest_given_value_of_day(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-13", at="20:00", fatigue=4)
    rate(conn, "2026-10-13", at="22:00", mood=3)
    assert weekly_review(conn, WED, weeks=1)[0]["fatigue"] == pytest.approx(4)


def test_fatigue_takes_last_of_two_values_in_day(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-13", at="20:00", fatigue=2)
    rate(conn, "2026-10-13", at="22:00", fatigue=5)
    assert weekly_review(conn, WED, weeks=1)[0]["fatigue"] == pytest.approx(5)


def test_only_fatigue_leaves_other_means_none(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-13", fatigue=4)
    row = weekly_review(conn, WED, weeks=1)[0]
    assert row["fatigue"] == pytest.approx(4)
    assert [row["mood"], row["stress"], row["irritability"]] == [None] * 3


def test_only_mood_leaves_fatigue_none(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-13", mood=4)
    row = weekly_review(conn, WED, weeks=1)[0]
    assert row["mood"] == pytest.approx(4)
    assert row["fatigue"] is None
    assert row["irritability"] is None


def test_day_with_only_fatigue_is_a_day_with_data(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-13", fatigue=4)
    assert weekly_review(conn, WED, weeks=1)[0]["days_with_data"] == 1


def test_day_with_only_irritability_is_a_day_with_data(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-13", irritability=4)
    assert weekly_review(conn, WED, weeks=1)[0]["days_with_data"] == 1


def test_day_with_wellbeing_record_without_marks_is_not_counted(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, logged_at, score) "
        "VALUES ('2026-10-13', '2026-10-13 21:00:00', 3)"
    )
    assert weekly_review(conn, WED, weeks=1)[0]["days_with_data"] == 0


def test_delta_of_fatigue_and_irritability(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-06", fatigue=3, irritability=2)
    rate(conn, "2026-10-13", fatigue=4, irritability=5)
    delta = weekly_review(conn, WED, weeks=2)[1]["delta"]
    assert delta["fatigue"] == pytest.approx(1.0)
    assert delta["irritability"] == pytest.approx(3.0)


def test_delta_of_fatigue_is_none_when_one_week_has_no_mean(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-13", fatigue=4)
    delta = weekly_review(conn, WED, weeks=2)[1]["delta"]
    assert delta["fatigue"] is None
    assert delta["irritability"] is None


def test_delta_keys_are_fifteen_with_marks_and_rest(conn: sqlite3.Connection) -> None:
    from ai_coach.review.service import DELTA_KEYS

    delta = weekly_review(conn, WED, weeks=2)[1]["delta"]
    assert len(DELTA_KEYS) == 15
    assert set(delta) == set(DELTA_KEYS)
    assert {"fatigue", "irritability", "rest_hours", "days_off"} <= set(delta)


def test_marks_after_today_are_not_in_fatigue_mean(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-13", fatigue=2)
    rate(conn, "2026-10-16", fatigue=5)
    assert weekly_review(conn, WED, weeks=1)[0]["fatigue"] == pytest.approx(2)


def test_existing_means_do_not_change_with_new_marks(filled: sqlite3.Connection) -> None:
    before = by_start(weekly_review(filled, WED))["2026-09-28"]
    rate(filled, "2026-10-02", at="22:00", fatigue=4, irritability=2)
    after = by_start(weekly_review(filled, WED))["2026-09-28"]
    for key in ["mood", "stress", "sleep", "readiness"]:
        assert after[key] == before[key]


# --- границы today и округление сумм ---


def test_marks_of_today_are_in_fatigue_mean(conn: sqlite3.Connection) -> None:
    rate(conn, "2026-10-14", fatigue=4)
    assert weekly_review(conn, WED, weeks=1)[0]["fatigue"] == pytest.approx(4)


def test_week_is_partial_on_saturday(conn: sqlite3.Connection) -> None:
    assert weekly_review(conn, date(2026, 10, 10), weeks=1)[0]["partial"] is True


def test_week_is_complete_on_sunday(conn: sqlite3.Connection) -> None:
    assert weekly_review(conn, date(2026, 10, 11), weeks=1)[0]["partial"] is False


def test_tss_of_week_is_rounded_to_one_decimal(conn: sqlite3.Connection) -> None:
    strength(conn, 9, "2026-10-13", 1000)  # 35 * 1000 / 3600 = 9.72
    metric(conn, "2026-10-13", 80, 60)
    assert weekly_review(conn, WED, weeks=1)[0]["tss"] == 9.7


def test_total_of_week_keeps_two_decimals(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-13", "screen_work_hours", 1.234)
    assert weekly_review(conn, WED, weeks=1)[0]["total"] == 1.23


def test_work_hours_of_week_are_rounded_to_two_decimals(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-13", "screen_work_hours", 1.234)
    assert weekly_review(conn, WED, weeks=1)[0]["work_hours"] == 1.23


def test_evening_hours_of_week_are_rounded_to_two_decimals(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-13", "screen_work_evening_hours", 1.234)
    assert weekly_review(conn, WED, weeks=1)[0]["evening_hours"] == 1.23


def test_weekend_work_hours_are_rounded_to_two_decimals(conn: sqlite3.Connection) -> None:
    screen(conn, "2026-10-10", "screen_work_hours", 1.234)
    assert by_start(weekly_review(conn, WED))["2026-10-05"]["weekend_work_hours"] == 1.23


# --- отдых и выходные (Н7, партия 1б) ---

WEEK_A = "2026-10-05"  # 10-05..10-11, неделя целиком
WEEK_B = "2026-10-12"  # 10-12..10-18, текущая, today = WED (10-14)


def busy(conn: sqlite3.Connection, *days: str) -> None:
    for day in days:
        counter(conn, day, "work_hours", 6.0)


def test_rest_hours_is_mean_of_answered_days(conn: sqlite3.Connection) -> None:
    counter(conn, "2026-10-06", "rest_hours", 2.0)
    counter(conn, "2026-10-08", "rest_hours", 4.0)
    row = by_start(weekly_review(conn, WED))[WEEK_A]
    assert row["rest_hours"] == pytest.approx(3.0)
    assert row["rest_days"] == 2


def test_rest_hours_none_without_answers(conn: sqlite3.Connection) -> None:
    for row in weekly_review(conn, WED):
        assert row["rest_hours"] is None
        assert row["rest_days"] == 0


def test_rest_answer_zero_is_a_value(conn: sqlite3.Connection) -> None:
    counter(conn, "2026-10-06", "rest_hours", 0.0)
    row = by_start(weekly_review(conn, WED))[WEEK_A]
    assert row["rest_hours"] == 0.0
    assert row["rest_days"] == 1


def test_calendar_rest_is_not_rest_hours(conn: sqlite3.Connection) -> None:
    event = stored_event(
        "rest", uid="r-1", start_at="2026-10-06T10:00:00", end_at="2026-10-06T13:00:00"
    )
    replace_calendar_window(conn, "2026-10-06", "2026-10-06", [event])
    row = by_start(weekly_review(conn, WED))[WEEK_A]
    assert row["rest_hours"] is None
    assert row["rest_days"] == 0


def test_days_off_counts_zero_and_empty_days_of_full_week(conn: sqlite3.Connection) -> None:
    busy(conn, "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09")
    counter(conn, "2026-10-10", "work_hours", 0.0)  # выходной с ответом; 10-11 - без данных
    assert by_start(weekly_review(conn, WED))[WEEK_A]["days_off"] == 2


def test_days_off_skips_today_without_manual_work_hours(conn: sqlite3.Connection) -> None:
    # Пн и Вт без данных - выходные; сегодня (Ср) без ручных часов не считается, дни после - тоже
    assert by_start(weekly_review(conn, WED))[WEEK_B]["days_off"] == 2


def test_days_off_counts_today_with_manual_work_hours(conn: sqlite3.Connection) -> None:
    counter(conn, "2026-10-14", "work_hours", 0.0)
    assert by_start(weekly_review(conn, WED))[WEEK_B]["days_off"] == 3


def test_days_off_today_with_manual_hours_above_max_is_not_off(conn: sqlite3.Connection) -> None:
    counter(conn, "2026-10-14", "work_hours", 6.0)
    assert by_start(weekly_review(conn, WED))[WEEK_B]["days_off"] == 2


def test_days_off_on_monday_without_manual_hours_is_zero(conn: sqlite3.Connection) -> None:
    # П1а: в неделе один день - сегодняшний, он не учтён, остаётся пустой список
    row = weekly_review(conn, date(2026, 10, 12), weeks=1)[0]
    assert row["days_off"] == 0


def test_days_off_on_monday_with_manual_zero_is_one(conn: sqlite3.Connection) -> None:
    counter(conn, "2026-10-12", "work_hours", 0.0)
    assert weekly_review(conn, date(2026, 10, 12), weeks=1)[0]["days_off"] == 1


def test_delta_rest_hours_is_difference_of_means(conn: sqlite3.Connection) -> None:
    counter(conn, "2026-10-06", "rest_hours", 2.0)
    counter(conn, "2026-10-13", "rest_hours", 5.0)
    assert by_start(weekly_review(conn, WED))[WEEK_B]["delta"]["rest_hours"] == pytest.approx(3.0)


def test_delta_rest_hours_none_when_previous_week_has_no_answers(
    conn: sqlite3.Connection,
) -> None:
    counter(conn, "2026-10-13", "rest_hours", 5.0)
    assert by_start(weekly_review(conn, WED))[WEEK_B]["delta"]["rest_hours"] is None


def test_delta_rest_hours_none_when_week_has_no_answers(conn: sqlite3.Connection) -> None:
    counter(conn, "2026-10-06", "rest_hours", 2.0)
    assert by_start(weekly_review(conn, WED))[WEEK_B]["delta"]["rest_hours"] is None


def test_delta_days_off_is_a_number(conn: sqlite3.Connection) -> None:
    busy(conn, "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09")
    busy(conn, "2026-10-12")
    # неделя A: выходных 2 (Сб, Вс без данных); неделя B: выходной только Вт -> 1; дельта -1
    assert by_start(weekly_review(conn, WED))[WEEK_B]["delta"]["days_off"] == -1
