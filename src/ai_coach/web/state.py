"""Вкладка «Состояние»: сигналы дня и тренды показателей (шаг П4, партия 5)."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach.load.illness import illness_report
from ai_coach.load.overload import overload_report
from ai_coach.load.sleep import sleep_report
from ai_coach.load.who5 import who5_report
from ai_coach.mcp_server import tools
from ai_coach.mcp_server.tools import ToolError, day_deviations
from ai_coach.store.garmin_data import list_daily_metrics, list_recovery_days
from ai_coach.store.journal import list_weights

TREND_DAYS = 14
WEIGHT_DAYS = 30
SECONDS_IN_HOUR = 3600


def _signals(source: str, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"source": source, **signal} for signal in signals]


def _trends(conn: sqlite3.Connection, day: date) -> dict[str, Any]:
    start = day - timedelta(days=TREND_DAYS - 1)
    dates = [(start + timedelta(days=n)).isoformat() for n in range(TREND_DAYS)]
    metrics = {row["date"]: row for row in list_daily_metrics(conn, dates[0], dates[-1])}
    recovery = {row["date"]: row for row in list_recovery_days(conn, dates[0], dates[-1])}

    def sleep_h(found: dict[str, Any] | None) -> float | None:
        seconds = found["sleep_seconds"] if found else None
        return None if seconds is None else round(seconds / SECONDS_IN_HOUR, 1)

    weights = list_weights(conn, (day - timedelta(days=WEIGHT_DAYS)).isoformat(), day.isoformat())
    return {
        "dates": dates,
        "sleep_h": [sleep_h(metrics.get(d)) for d in dates],
        "hrv": [recovery[d]["hrv"] if d in recovery else None for d in dates],
        "rhr": [recovery[d]["rhr"] if d in recovery else None for d in dates],
        "readiness": [metrics[d]["readiness_score"] if d in metrics else None for d in dates],
        "weight": [{"date": r["measured_at"][:10], "kg": r["weight_kg"]} for r in weights],
    }


def state_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """signals (sleep, illness, overload, who5, deviations), trends за 14 дней и вес за 30,
    load_error - текст, если нагрузка не считается (тогда сигналы без неё)."""
    iso = day.isoformat()
    tss: dict[str, float] = {}
    load_row = None
    load_error = None
    try:
        rows = tools.load(conn, (day - timedelta(days=TREND_DAYS - 1)).isoformat(), iso)["rows"]
        tss = {row["date"]: row["tss"] for row in rows}
        load_row = rows[-1]
    except ToolError as error:
        load_error = str(error)
    sleep = sleep_report(conn, iso, now)
    signals = (
        _signals("sleep", sleep["signals"])
        + _signals("illness", illness_report(conn, iso, tss, sleep)["signals"])
        + _signals("overload", overload_report(conn, iso, tss)["signals"])
        + _signals("who5", who5_report(conn, iso)["signals"])
        + _signals("deviations", day_deviations(conn, iso, load_row))
    )
    return {"signals": signals, "trends": _trends(conn, day), "load_error": load_error}
