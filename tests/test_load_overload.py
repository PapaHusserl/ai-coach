"""ai_coach.load.overload (план v2.2+v2.3; сигнатуры - как в реализации кабана):

total_load(day) -> float: линейная сумма по веса-константам; day - строка workload_series
(+ "tss" - TSS тренировок дня, + "manual_work_hours"/"manual_hobby_hours" - ручные часы дня,
главнее календарных, 0 тоже ручное значение; нет ключа или None - 0 / берётся календарное).

find_overload(days, metrics) -> [{"kind", ...}]: days - дни по возрастанию (date, total,
work_hours, work_evening_hours, weekend, todo_open), последний - проверяемый; metrics - строки
daily_metrics (date, readiness_score). Пороги - константы модуля TOTAL_HIGH, TOTAL_STREAK_DAYS,
EVENING_STREAK_DAYS. Виды: total_streak, evening_streak, weekend_work, recovery_drop, todo_growth.
Тесты не привязаны к значениям весов: только к соотношениям и к константам-порогам.
"""

from datetime import date, timedelta
from typing import Any

import pytest

from ai_coach.load import overload
from ai_coach.load.overload import find_overload, hours, total_load

LAST = "2026-10-07"

BIG_EVENING = 3.0


def day(**fields: Any) -> dict[str, Any]:
    return fields


def test_thresholds_are_module_constants() -> None:
    assert overload.TOTAL_HIGH > 0
    assert overload.TOTAL_STREAK_DAYS >= 2
    assert overload.EVENING_STREAK_DAYS >= 2


def test_empty_day_has_zero_load() -> None:
    assert total_load({}) == 0
    assert total_load(day(work_hours=None, hobby_hours=None, tss=None, todo_open=None)) == 0


def test_work_hours_add_load() -> None:
    assert total_load(day(work_hours=1.0)) > 0


def test_total_is_linear_in_work_hours() -> None:
    one = total_load(day(work_hours=1.0))
    assert total_load(day(work_hours=3.0)) == pytest.approx(3 * one)


def test_total_is_linear_in_training_load() -> None:
    one = total_load(day(tss=50.0))
    assert one > 0
    assert total_load(day(tss=100.0)) == pytest.approx(2 * one)


def test_total_is_a_sum_of_parts() -> None:
    work = total_load(day(work_hours=2.0))
    tss = total_load(day(tss=40.0))
    hobby = total_load(day(hobby_hours=1.5))
    both = total_load(day(work_hours=2.0, tss=40.0, hobby_hours=1.5))
    assert both == pytest.approx(work + tss + hobby)


def test_hobby_hours_add_load() -> None:
    assert total_load(day(hobby_hours=2.0)) > 0


def test_more_work_means_more_load() -> None:
    assert total_load(day(work_hours=8.0)) > total_load(day(work_hours=4.0))


def test_manual_hours_override_calendar_hours() -> None:
    row = day(work_hours=8.0, manual_work_hours=2.0)
    assert total_load(row) == pytest.approx(total_load(day(work_hours=2.0)))


def test_manual_zero_overrides_calendar() -> None:
    assert total_load(day(work_hours=8.0, manual_work_hours=0.0)) == 0


def test_manual_none_keeps_calendar_value() -> None:
    row = day(work_hours=8.0, manual_work_hours=None)
    assert total_load(row) == pytest.approx(total_load(day(work_hours=8.0)))


def test_manual_hobby_overrides_calendar_hobby_only() -> None:
    row = day(work_hours=8.0, hobby_hours=1.0, manual_hobby_hours=3.0)
    assert total_load(row) == pytest.approx(total_load(day(work_hours=8.0, hobby_hours=3.0)))


def test_manual_hours_without_calendar_count() -> None:
    row = day(manual_work_hours=5.0)
    assert total_load(row) == pytest.approx(total_load(day(work_hours=5.0)))


def test_screen_hours_override_calendar_hours() -> None:
    row = day(work_hours=7.0, screen_work_hours=3.0, manual_work_hours=None)
    assert hours(row, "work_hours") == 3.0
    assert total_load(row) == pytest.approx(total_load(day(work_hours=3.0)))


def test_manual_hours_override_screen_hours() -> None:
    row = day(work_hours=7.0, screen_work_hours=3.0, manual_work_hours=2.0)
    assert hours(row, "work_hours") == 2.0


def test_manual_zero_overrides_screen() -> None:
    assert hours(day(screen_work_hours=3.0, manual_work_hours=0.0), "work_hours") == 0


def test_screen_zero_is_a_value_not_missing_data() -> None:
    row = day(work_hours=7.0, screen_work_hours=0.0)
    assert hours(row, "work_hours") == 0
    assert total_load(row) == 0


def test_screen_none_keeps_calendar_value() -> None:
    row = day(work_hours=7.0, screen_work_hours=None)
    assert hours(row, "work_hours") == 7.0


def test_screen_hobby_overrides_calendar_hobby_only() -> None:
    row = day(work_hours=7.0, hobby_hours=1.0, screen_hobby_hours=4.0)
    assert hours(row, "hobby_hours") == 4.0
    assert hours(row, "work_hours") == 7.0
    assert total_load(row) == pytest.approx(total_load(day(work_hours=7.0, hobby_hours=4.0)))


def test_manual_hobby_overrides_screen_hobby() -> None:
    row = day(hobby_hours=1.0, screen_hobby_hours=4.0, manual_hobby_hours=0.5)
    assert hours(row, "hobby_hours") == 0.5


def test_screen_zero_hobby_overrides_calendar_hobby() -> None:
    row = day(hobby_hours=2.0, screen_hobby_hours=0.0)
    assert hours(row, "hobby_hours") == 0


def test_screen_hours_without_calendar_count() -> None:
    assert total_load({"screen_work_hours": 5}) == pytest.approx(total_load({"work_hours": 5}))
    assert total_load({"screen_work_hours": 5}) > 0


def test_screen_browser_and_evening_hours_add_no_load() -> None:
    assert total_load(day(screen_browser_hours=6.0, screen_evening_hours=4.0)) == 0


def quiet(count: int = 7) -> list[dict[str, Any]]:
    return [
        {
            "date": f"2026-10-{number + 1:02d}",
            "total": 0.0,
            "work_hours": 0.0,
            "work_evening_hours": 0.0,
            "weekend": False,
            "todo_open": 5,
        }
        for number in range(count)
    ]


def with_tail(days: list[dict[str, Any]], count: int, **fields: Any) -> list[dict[str, Any]]:
    for item in days[len(days) - count :]:
        item.update(fields)
    return days


def readiness(*scores: int | None) -> list[dict[str, Any]]:
    """Строки daily_metrics: последняя оценка - LAST, остальные - по дню назад."""
    last = date.fromisoformat(LAST)
    count = len(scores)
    return [
        {"date": (last - timedelta(days=count - 1 - n)).isoformat(), "readiness_score": score}
        for n, score in enumerate(scores)
    ]


def kinds(days: list[dict[str, Any]], metrics: list[dict[str, Any]] | None = None) -> list[str]:
    return [d["kind"] for d in find_overload(days, metrics or [])]


def test_one_day_no_overload() -> None:
    assert find_overload(quiet(1), []) == []


def test_quiet_period_has_no_overload() -> None:
    assert kinds(quiet()) == []


@pytest.mark.parametrize(
    ("extra", "expected"),
    [(-1, False), (0, True), (1, True)],
    ids=["N-1", "N", "N+1"],
)
def test_total_streak_borders(extra: int, expected: bool) -> None:
    count = overload.TOTAL_STREAK_DAYS + extra
    days = with_tail(quiet(), count, total=overload.TOTAL_HIGH + 1)
    assert ("total_streak" in kinds(days)) is expected


def test_total_streak_is_broken_by_a_quiet_day() -> None:
    count = overload.TOTAL_STREAK_DAYS
    days = with_tail(quiet(), count, total=overload.TOTAL_HIGH + 1)
    days[-2]["total"] = overload.TOTAL_HIGH - 1
    assert "total_streak" not in kinds(days)


def test_total_streak_must_end_on_the_checked_day() -> None:
    days = with_tail(quiet(), overload.TOTAL_STREAK_DAYS + 1, total=overload.TOTAL_HIGH + 1)
    days[-1]["total"] = 0.0
    assert "total_streak" not in kinds(days)


def test_total_below_high_never_makes_a_streak() -> None:
    days = with_tail(quiet(), 10, total=overload.TOTAL_HIGH - 1)
    assert "total_streak" not in kinds(days)


@pytest.mark.parametrize(
    ("extra", "expected"),
    [(-1, False), (0, True), (1, True)],
    ids=["N-1", "N", "N+1"],
)
def test_evening_streak_borders(extra: int, expected: bool) -> None:
    count = overload.EVENING_STREAK_DAYS + extra
    days = with_tail(quiet(), count, work_evening_hours=BIG_EVENING)
    assert ("evening_streak" in kinds(days)) is expected


def test_evening_streak_is_broken_by_a_free_evening() -> None:
    days = with_tail(quiet(), overload.EVENING_STREAK_DAYS, work_evening_hours=BIG_EVENING)
    days[-2]["work_evening_hours"] = 0.0
    assert "evening_streak" not in kinds(days)


def test_work_on_weekend_is_overload() -> None:
    days = with_tail(quiet(), 1, weekend=True, work_hours=4.0)
    assert "weekend_work" in kinds(days)


def test_free_weekend_is_fine() -> None:
    days = with_tail(quiet(), 1, weekend=True, work_hours=0.0)
    assert "weekend_work" not in kinds(days)


def test_screen_work_on_weekend_is_overload() -> None:
    days = with_tail(quiet(), 1, weekend=True, work_hours=0.0, screen_work_hours=4.0)
    assert "weekend_work" in kinds(days)


def test_screen_zero_on_weekend_beats_calendar_work() -> None:
    days = with_tail(quiet(), 1, weekend=True, work_hours=4.0, screen_work_hours=0.0)
    assert "weekend_work" not in kinds(days)


def test_manual_zero_on_weekend_beats_screen_work() -> None:
    days = with_tail(quiet(), 1, weekend=True, screen_work_hours=4.0, manual_work_hours=0.0)
    assert "weekend_work" not in kinds(days)


def test_work_on_weekday_is_not_weekend_work() -> None:
    days = with_tail(quiet(), 1, weekend=False, work_hours=10.0)
    assert "weekend_work" not in kinds(days)


def test_weekend_work_without_data_is_fine() -> None:
    days = with_tail(quiet(), 1, weekend=True, work_hours=None)
    assert "weekend_work" not in kinds(days)


def test_growing_todo_is_overload() -> None:
    days = quiet()
    for number, item in enumerate(days):
        item["todo_open"] = 5 + number * 5
    assert "todo_growth" in kinds(days)


def test_flat_todo_is_fine() -> None:
    assert "todo_growth" not in kinds(quiet())


def test_shrinking_todo_is_fine() -> None:
    days = quiet()
    for number, item in enumerate(days):
        item["todo_open"] = 80 - number * 5
    assert "todo_growth" not in kinds(days)


def test_todo_without_data_is_fine() -> None:
    days = with_tail(quiet(), 7, todo_open=None)
    assert "todo_growth" not in kinds(days)


def test_collapsing_readiness_is_recovery_drop() -> None:
    metrics = readiness(70, 70, 70, 70, 70, 70, 70, 10, 10, 10)
    assert "recovery_drop" in kinds(quiet(), metrics)


def test_stable_readiness_is_fine() -> None:
    metrics = readiness(70, 70, 70, 70, 70, 70, 70, 70, 70, 70)
    assert "recovery_drop" not in kinds(quiet(), metrics)


def test_improving_readiness_is_fine() -> None:
    metrics = readiness(40, 40, 40, 40, 40, 40, 40, 95, 95, 95)
    assert "recovery_drop" not in kinds(quiet(), metrics)


def test_recovery_drop_without_any_data_does_not_fire() -> None:
    assert "recovery_drop" not in kinds(quiet(), [])


def test_recovery_drop_with_empty_scores_does_not_fire() -> None:
    metrics = readiness(None, None, None, None, None, None, None, None, None, None)
    assert "recovery_drop" not in kinds(quiet(), metrics)


def test_recovery_drop_without_baseline_does_not_fire() -> None:
    metrics = readiness(10, 10, 10)
    assert "recovery_drop" not in kinds(quiet(), metrics)


DROPS = {"readiness_score": (10, 70), "mood": (1, 4), "stress": (5, 2)}


def spread(
    key: str, recent: float | None, baseline: float | None, nr: int = 3, nb: int = 7
) -> list[dict[str, Any]]:
    """Строки с ключом key: nr значений recent в последних днях (LAST и назад), потом
    nb значений baseline в предыдущих днях (окно RECOVERY_RECENT_DAYS + RECOVERY_BASELINE_DAYS)."""
    last = date.fromisoformat(LAST)
    rows = []
    for age in range(nr):
        rows.append({"date": (last - timedelta(days=age)).isoformat(), key: recent})
    for n in range(nb):
        age = overload.RECOVERY_RECENT_DAYS + n
        rows.append({"date": (last - timedelta(days=age)).isoformat(), key: baseline})
    return rows


def drop_of(days: list[dict[str, Any]], metrics: list[dict[str, Any]] | None = None) -> Any:
    found = [d for d in find_overload(days, metrics or []) if d["kind"] == "recovery_drop"]
    return found[0] if found else None


def test_recovery_thresholds_are_module_constants() -> None:
    assert overload.READINESS_DROP == 10
    assert overload.MOOD_DROP == 1.0
    assert overload.STRESS_RISE == 1.0
    assert overload.RECOVERY_MIN_RECENT == 2
    assert overload.RECOVERY_MIN_BASELINE == 3
    assert overload.METRICS_DAYS == 10


def test_collapsing_mood_is_recovery_drop() -> None:
    assert "mood" in drop_of(quiet(), spread("mood", 1, 4))["value"]


def test_rising_stress_is_recovery_drop() -> None:
    assert "stress" in drop_of(quiet(), spread("stress", 5, 2))["value"]


def test_stable_mood_and_stress_are_fine() -> None:
    metrics = spread("mood", 4, 4) + spread("stress", 2, 2)
    assert drop_of(quiet(), metrics) is None


def test_improving_mood_and_falling_stress_are_fine() -> None:
    metrics = spread("mood", 5, 2) + spread("stress", 1, 4)
    assert drop_of(quiet(), metrics) is None


def test_mood_drop_without_data_does_not_fire() -> None:
    metrics = spread("mood", None, None) + spread("stress", None, None)
    assert drop_of(quiet(), metrics) is None


def test_mood_drop_with_baseline_only_in_days_7_to_9_fires() -> None:
    last = date.fromisoformat(LAST)
    old = [7, 8, 9]
    rows = [{"date": (last - timedelta(days=a)).isoformat(), "mood": 4} for a in old]
    rows += spread("mood", 1, None, nb=0)
    assert "mood" in drop_of(quiet(), rows)["value"]


def test_baseline_older_than_the_window_is_ignored() -> None:
    last = date.fromisoformat(LAST)
    old = [10, 11, 12]
    rows = [{"date": (last - timedelta(days=a)).isoformat(), "mood": 4} for a in old]
    rows += spread("mood", 1, None, nb=0)
    assert drop_of(quiet(), rows) is None


def test_mood_drop_without_baseline_does_not_fire() -> None:
    assert drop_of(quiet(), spread("mood", 1, None, nb=0)) is None


def test_mood_drop_without_recent_does_not_fire() -> None:
    assert drop_of(quiet(), spread("mood", None, 4, nr=0)) is None


def test_metrics_without_mood_keys_still_work() -> None:
    assert drop_of(quiet(), readiness(70, 70, 70)) is None


def test_mood_drop_exactly_at_threshold_fires() -> None:
    metrics = spread("mood", 4 - overload.MOOD_DROP, 4)
    assert "mood" in drop_of(quiet(), metrics)["value"]


def test_mood_drop_just_below_threshold_does_not_fire() -> None:
    metrics = spread("mood", 4 - overload.MOOD_DROP + 0.5, 4)
    assert drop_of(quiet(), metrics) is None


def test_stress_rise_exactly_at_threshold_fires() -> None:
    metrics = spread("stress", 2 + overload.STRESS_RISE, 2)
    assert "stress" in drop_of(quiet(), metrics)["value"]


def test_stress_rise_just_below_threshold_does_not_fire() -> None:
    metrics = spread("stress", 2 + overload.STRESS_RISE - 0.5, 2)
    assert drop_of(quiet(), metrics) is None


def test_readiness_drop_exactly_at_threshold_fires() -> None:
    metrics = spread("readiness_score", 70 - overload.READINESS_DROP, 70)
    assert "readiness" in drop_of(quiet(), metrics)["value"]


def test_readiness_drop_just_below_threshold_does_not_fire() -> None:
    metrics = spread("readiness_score", 70 - overload.READINESS_DROP + 1, 70)
    assert drop_of(quiet(), metrics) is None


def test_only_fired_signs_are_in_value() -> None:
    found = drop_of(quiet(), spread("mood", 1, 4))
    assert set(found["value"]) == {"mood"}
    assert found["value"]["mood"] >= overload.MOOD_DROP


def test_several_signs_are_all_in_value() -> None:
    metrics = spread("readiness_score", 10, 70) + spread("mood", 1, 4) + spread("stress", 5, 2)
    assert set(drop_of(quiet(), metrics)["value"]) == {"readiness", "mood", "stress"}


def test_limit_has_thresholds_of_every_sign() -> None:
    assert drop_of(quiet(), spread("mood", 1, 4))["limit"] == {
        "readiness": overload.READINESS_DROP,
        "mood": overload.MOOD_DROP,
        "stress": overload.STRESS_RISE,
    }


@pytest.mark.parametrize("key", ["readiness_score", "mood", "stress"])
def test_two_recent_and_three_baseline_values_are_enough(key: str) -> None:
    recent, baseline = DROPS[key]
    assert drop_of(quiet(), spread(key, recent, baseline, nr=2, nb=3)) is not None


@pytest.mark.parametrize("key", ["readiness_score", "mood", "stress"])
def test_one_recent_value_is_not_enough(key: str) -> None:
    recent, baseline = DROPS[key]
    assert drop_of(quiet(), spread(key, recent, baseline, nr=1, nb=3)) is None


@pytest.mark.parametrize("key", ["readiness_score", "mood", "stress"])
def test_two_baseline_values_are_not_enough(key: str) -> None:
    recent, baseline = DROPS[key]
    assert drop_of(quiet(), spread(key, recent, baseline, nr=2, nb=2)) is None


def test_minimums_are_counted_separately_for_each_sign() -> None:
    metrics = spread("mood", 1, 4) + spread("stress", 5, 2, nr=1)
    assert set(drop_of(quiet(), metrics)["value"]) == {"mood"}


def test_every_signal_is_reported_once() -> None:
    days = with_tail(quiet(), 7, total=overload.TOTAL_HIGH + 1, work_evening_hours=BIG_EVENING)
    found = kinds(days)
    assert len(found) == len(set(found))
    assert {"total_streak", "evening_streak"} <= set(found)
