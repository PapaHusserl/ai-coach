"""ai_coach.load.rest (Н7, партия 1а; сигнатуры - из «Партия 1: сигнатуры» плана):

day_off(day) -> bool: work_hours дня (hours: ручные, экран, календарь) не больше DAY_OFF_WORK_MAX.
days_without_off(days, today) -> int: дней подряд без выходного до конца списка; сегодняшний день
(последний, today - строка YYYY-MM-DD) входит, только если у него есть manual_work_hours.
find_rest(days, today) -> [{"kind": "no_day_off", "value", "limit"}] при value >= DAY_OFF_LIMIT.
"""

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from ai_coach.load import rest
from ai_coach.load.rest import day_off, days_without_off, find_rest

TODAY = "2026-10-07"
WORK = 6.0


def shift(days: int) -> str:
    return (date.fromisoformat(TODAY) + timedelta(days=days)).isoformat()


def entry(offset: int, work: float | None = WORK, **fields: Any) -> dict[str, Any]:
    """День TODAY+offset; work - ручные рабочие часы (None - не вводились)."""
    return {"date": shift(offset), "manual_work_hours": work, **fields}


def run(past: Sequence[float | None], today: float | None = None) -> list[dict[str, Any]]:
    """Дни до вчера (past, по возрастанию даты) и сегодняшний с ручными часами today."""
    count = len(past)
    days = [entry(index - count, work) for index, work in enumerate(past)]
    return [*days, entry(0, today)]


def test_constants() -> None:
    assert rest.DAY_OFF_WORK_MAX == 0.5
    assert rest.DAY_OFF_LIMIT == 7
    assert rest.DAY_OFF_LOOKBACK == 14


def test_day_off_manual_zero() -> None:
    assert day_off({"manual_work_hours": 0}) is True


def test_day_off_manual_at_max() -> None:
    assert day_off({"manual_work_hours": 0.5}) is True


def test_day_off_manual_above_max() -> None:
    assert day_off({"manual_work_hours": 0.51}) is False


def test_day_off_screen_only() -> None:
    assert day_off({"screen_work_hours": 0.3}) is True


def test_day_off_manual_beats_screen() -> None:
    assert day_off({"manual_work_hours": 0, "screen_work_hours": 3.0}) is True


def test_day_off_calendar_work_is_not_off() -> None:
    assert day_off({"work_hours": 2.0}) is False


def test_day_off_without_any_source() -> None:
    assert day_off({}) is True


def test_seven_work_days_and_today_without_answer() -> None:
    assert days_without_off(run([WORK] * 7), TODAY) == 7


def test_today_with_manual_zero_resets() -> None:
    assert days_without_off(run([WORK] * 7, today=0), TODAY) == 0


def test_today_with_manual_work_counts() -> None:
    assert days_without_off(run([WORK] * 7, today=6.0), TODAY) == 8


def test_day_off_the_day_before_yesterday() -> None:
    assert days_without_off(run([WORK, 0, WORK]), TODAY) == 1


def test_fourteen_work_days() -> None:
    assert days_without_off(run([WORK] * 13, today=WORK), TODAY) == 14


def test_value_is_capped_at_lookback_with_fifteen_rows() -> None:
    days = run([WORK] * 14, today=WORK)
    assert len(days) == 15
    assert days_without_off(days, TODAY) == 14
    assert find_rest(days, TODAY) == [{"kind": "no_day_off", "value": 14, "limit": 7}]


def test_midweek_day_off_resets() -> None:
    # вчера - вторник: выходной не в сб/вс обнуляет счёт
    assert date.fromisoformat(shift(-1)).weekday() == 1
    days = run([WORK] * 5 + [0])
    assert days_without_off(days, TODAY) == 0


def test_today_without_answer_is_skipped_even_if_empty() -> None:
    assert days_without_off(run([WORK, WORK]), TODAY) == 2


def test_find_rest_below_limit_is_empty() -> None:
    assert find_rest(run([WORK] * 6), TODAY) == []


def test_find_rest_at_limit() -> None:
    assert find_rest(run([WORK] * 7), TODAY) == [{"kind": "no_day_off", "value": 7, "limit": 7}]


def test_find_rest_above_limit() -> None:
    found = find_rest(run([WORK] * 8), TODAY)
    assert found == [{"kind": "no_day_off", "value": 8, "limit": 7}]
