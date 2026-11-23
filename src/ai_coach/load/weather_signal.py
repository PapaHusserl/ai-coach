"""Погодный сигнал: перепад давления и температуры в ближайшие 24 часа (П7, партия 8).

Счёт идёт от текущего часа (по началу часа) до экстремума в следующих 24 часах, только вперёд.
Наружу сигнал пока не подключён: его пишет только синк в weather_signals.
"""

import sqlite3
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from ai_coach.store.weather import list_weather_hours

# Пороги сигнала (None - порога нет, строк этого кода нет): числа назвал Влад по таблице
# spikes/weather/threshold_table.py, «Решения» docs/plan-p7.md п. 75-77; раздел
# «Пороги и окно» docs/research-weather-wellbeing.md.
# Порог выбран по частоте на ряде Влада, наукой не проверен.
PRESSURE_LIMIT: float | None = 4  # гПа, падение давления
TEMPERATURE_LIMIT: float | None = 10  # °C, один порог на рост и падение

AHEAD_HOURS = 24
Hours = list[dict[str, Any]]
Extreme = tuple[float, datetime]


def _window(
    hours: Hours, now: datetime, column: str
) -> tuple[float, list[tuple[datetime, float]]] | None:
    """Значение текущего часа и значения следующих 24 часов (NULL пропущены) или None."""
    start = now.replace(minute=0, second=0, microsecond=0)
    by_time = {datetime.fromisoformat(h["time"]): h[column] for h in hours}
    ahead = [start + timedelta(hours=i) for i in range(1, AHEAD_HOURS + 1)]
    current = by_time.get(start)
    if current is None or any(t not in by_time for t in ahead):
        return None
    values = [(t, by_time[t]) for t in ahead if by_time[t] is not None]
    return (current, values) if values else None


def pressure_ahead(hours: Hours, now: datetime) -> Extreme | None:
    """Падение давления: текущий час минус минимум за 24 часа вперёд и час минимума."""
    window = _window(hours, now, "pressure")
    if window is None:
        return None
    current, values = window
    at, low = min(values, key=lambda item: item[1])
    return current - low, at


def temperature_ahead(hours: Hours, now: datetime) -> tuple[Extreme, Extreme] | None:
    """Рост (максимум минус текущий час) и падение (текущий час минус минимум) с часами."""
    window = _window(hours, now, "temperature")
    if window is None:
        return None
    current, values = window
    high_at, high = max(values, key=lambda item: item[1])
    low_at, low = min(values, key=lambda item: item[1])
    return (high - current, high_at), (current - low, low_at)


def _row(kind: str, value: float, limit: float, at: datetime, now: datetime) -> dict[str, Any]:
    return {
        "kind": kind,
        "value": round(value, 1),
        "limit": limit,
        "at": at.strftime("%H:%M"),
        "next_day": at.date() > now.date(),
    }


def _temperature_row(
    rise: Extreme, fall: Extreme, limit: float, now: datetime
) -> dict[str, Any] | None:
    """Рост и падение выше порога - одна строка: больше число, при равных - раньше час."""
    found = [
        (round(value, 1), at, kind)
        for (value, at), kind in ((rise, "temperature_rise"), (fall, "temperature_drop"))
        if round(value, 1) > limit
    ]
    if not found:
        return None
    value, at, kind = min(found, key=lambda item: (-item[0], item[1]))
    return _row(kind, value, limit, at, now)


def find_weather_signals(
    hours: Hours, now: datetime, limits: Mapping[str, float | None]
) -> list[dict[str, Any]]:
    """Строки {kind, value, limit, at, next_day}: давление первым; порог None - кода нет."""
    rows: list[dict[str, Any]] = []
    pressure_limit = limits["pressure"]
    if pressure_limit is not None and (drop := pressure_ahead(hours, now)) is not None:
        value, at = drop
        if round(value, 1) > pressure_limit:
            rows.append(_row("pressure_drop", value, pressure_limit, at, now))
    temperature_limit = limits["temperature"]
    if temperature_limit is not None and (swing := temperature_ahead(hours, now)) is not None:
        row = _temperature_row(*swing, temperature_limit, now)
        if row is not None:
            rows.append(row)
    return rows


def weather_report(conn: sqlite3.Connection, day: str, now: datetime) -> dict[str, Any]:
    """{date, signals} по часам базы; день не сегодня - сигналов нет."""
    if day != now.date().isoformat():
        return {"date": day, "signals": []}
    end = (now.date() + timedelta(days=1)).isoformat()
    limits = {"pressure": PRESSURE_LIMIT, "temperature": TEMPERATURE_LIMIT}
    return {
        "date": day,
        "signals": find_weather_signals(list_weather_hours(conn, day, end), now, limits),
    }
