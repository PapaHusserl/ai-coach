"""Сигналы внимания (Н8): много переключений окон и долгий рабочий отрезок без паузы.

Оценивается вчерашний день (Р8): переключения в час сравниваются с медианой BASE_DAYS
предыдущих дней (не меньше MIN_BASE_DAYS значений), отрезок - с порогом STRETCH_LIMIT_HOURS.
"""

import sqlite3
from collections.abc import Sequence
from datetime import date, timedelta
from statistics import median
from typing import Any

from ai_coach.store.workload import list_counters

SWITCH_FACTOR = 1.5
BASE_DAYS = 28
MIN_BASE_DAYS = 14
STRETCH_LIMIT_HOURS = 2.0

SWITCHES = "screen_switches_hour"
STRETCH = "screen_stretch_hours"


def baseline(values: Sequence[float | None]) -> float | None:
    """Медиана значений без None; значений меньше MIN_BASE_DAYS - None."""
    found = [value for value in values if value is not None]
    if len(found) < MIN_BASE_DAYS:
        return None
    return median(found)


def find_attention(
    rate: float | None, typical: float | None, stretch: float | None
) -> list[dict[str, Any]]:
    """switching_high - rate не меньше SWITCH_FACTOR медиан; long_stretch - отрезок не короче
    STRETCH_LIMIT_HOURS. Порядок - переключения, затем отрезок."""
    signals: list[dict[str, Any]] = []
    if rate is not None and typical is not None and rate >= SWITCH_FACTOR * typical:
        limit = round(SWITCH_FACTOR * typical, 1)
        signals.append({"kind": "switching_high", "value": rate, "limit": limit})
    if stretch is not None and stretch >= STRETCH_LIMIT_HOURS:
        signals.append({"kind": "long_stretch", "value": stretch, "limit": STRETCH_LIMIT_HOURS})
    return signals


def attention_report(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Оценивается день day - 1. Ответ: date (оцениваемый день), switches_hour, switches_median
    (None - в базе меньше MIN_BASE_DAYS значений), base_days (значений в базе), stretch_hours,
    signals (find_attention). Нет счётчиков оцениваемого дня - значения None, signals пуст."""
    evaluated = date.fromisoformat(day) - timedelta(days=1)
    first = (evaluated - timedelta(days=BASE_DAYS)).isoformat()
    shown = evaluated.isoformat()
    values: dict[str, dict[str, float]] = {SWITCHES: {}, STRETCH: {}}
    for counter in list_counters(conn, first, shown):
        if counter["kind"] in values:
            values[counter["kind"]][counter["date"]] = counter["value"]
    rate = values[SWITCHES].get(shown)
    stretch = values[STRETCH].get(shown)
    past = [value for when, value in values[SWITCHES].items() if when < shown]
    typical = baseline(past)
    return {
        "date": shown,
        "switches_hour": rate,
        "switches_median": typical,
        "base_days": len(past),
        "stretch_hours": stretch,
        "signals": find_attention(rate, typical, stretch),
    }
