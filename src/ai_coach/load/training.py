"""Нагрузка: hrTSS по резерву ЧСС, CTL/ATL."""

import sqlite3
from datetime import date, timedelta
from typing import Any

from ai_coach.store.garmin_data import list_activities

CTL_DAYS = 42
ATL_DAYS = 7


def hr_tss(duration_s: float | None, avg_hr: float | None, rest_hr: float, lthr: float) -> float:
    """IF = (avg_hr - rest_hr) / (lthr - rest_hr), TSS = часы * IF^2 * 100; нет данных — 0."""
    if lthr <= rest_hr:
        raise ValueError("lthr должен быть больше rest_hr")
    if not duration_s or not avg_hr or avg_hr <= rest_hr:
        return 0.0
    intensity = (avg_hr - rest_hr) / (lthr - rest_hr)
    return duration_s / 3600 * intensity**2 * 100


def daily_tss(
    conn: sqlite3.Connection, start: str, end: str, rest_hr: float, lthr: float
) -> dict[str, float]:
    """TSS по каждому локальному дню start..end включительно (дни без тренировок — 0)."""
    result: dict[str, float] = {}
    day = date.fromisoformat(start)
    while day <= date.fromisoformat(end):
        result[day.isoformat()] = 0.0
        day += timedelta(days=1)
    for activity in list_activities(conn, start, end):
        key = activity["start_time_local"][:10]
        result[key] += hr_tss(activity["duration_s"], activity["avg_hr"], rest_hr, lthr)
    return result


def load_series(tss_by_day: dict[str, float]) -> list[dict[str, Any]]:
    """CTL (τ=42) и ATL (τ=7) по дням: x + (tss - x) / τ."""
    ctl = 0.0
    atl = 0.0
    series: list[dict[str, Any]] = []
    for day in sorted(tss_by_day):
        tss = tss_by_day[day]
        ctl += (tss - ctl) / CTL_DAYS
        atl += (tss - atl) / ATL_DAYS
        series.append({"date": day, "tss": tss, "ctl": ctl, "atl": atl})
    return series
