"""Сигнал «нет полного выходного»: дней подряд без выходного (Н7).

Выходной - день, где часы работы (overload.hours: ручные, экран, календарь) не больше
DAY_OFF_WORK_MAX; день недели не смотрится, день без данных - выходной.
"""

from typing import Any

from ai_coach.load import overload

DAY_OFF_WORK_MAX = 0.5
DAY_OFF_LIMIT = 7
DAY_OFF_LOOKBACK = 14


def day_off(day: dict[str, Any]) -> bool:
    """Часы работы дня не больше DAY_OFF_WORK_MAX."""
    return overload.hours(day, "work_hours") <= DAY_OFF_WORK_MAX


def counted_days(days: list[dict[str, Any]], today: str) -> list[dict[str, Any]]:
    """Дни без сегодняшнего, если у него нет manual_work_hours (вечерний чек-ин не сделан)."""
    last = days[-1]
    if last["date"] == today and last.get("manual_work_hours") is None:
        return days[:-1]
    return days


def days_without_off(days: list[dict[str, Any]], today: str) -> int:
    """Сколько дней подряд до конца списка без выходного, не больше DAY_OFF_LOOKBACK. days - дни
    по возрастанию даты, последний - today; сегодняшний входит в счёт, только если у него есть
    manual_work_hours."""
    count = 0
    for day in reversed(counted_days(days, today)[-DAY_OFF_LOOKBACK:]):
        if day_off(day):
            break
        count += 1
    return count


def find_rest(days: list[dict[str, Any]], today: str) -> list[dict[str, Any]]:
    """[{kind: no_day_off, value, limit}], когда дней без выходного не меньше DAY_OFF_LIMIT."""
    count = days_without_off(days, today)
    if count < DAY_OFF_LIMIT:
        return []
    return [{"kind": "no_day_off", "value": count, "limit": DAY_OFF_LIMIT}]
