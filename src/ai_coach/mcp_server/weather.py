"""Инструмент MCP: погода из базы (П7). К сервису и геолокации не ходит."""

import sqlite3
from datetime import timedelta
from typing import Any

from ai_coach.mcp_server import tools
from ai_coach.mcp_server.tools import cap, period
from ai_coach.store.weather import (
    last_weather_now,
    list_weather_days,
    list_weather_hours,
    list_weather_now,
)
from ai_coach.weather import weather_word

HISTORY_KEYS = ("observed_at", "temperature", "pressure")
HOURLY_KEYS = ("time", "temperature", "pressure")
HOURLY_DAYS = 7  # окно чтения: вчера и семь дат после него
HOURLY_STEP = 3


def _with_word(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "word": weather_word(row["code"])}


def weather(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, Any]:
    """now - последнее наблюдение (в том числе вне периода), rows - дни периода со словом
    погоды, history - наблюдения периода (время, температура, давление): точка на каждый синк,
    hourly - прогноз по часам, шаг 3 ч, со вчера на 7,5 суток (период не влияет)."""
    period(date_from, date_to)
    last = last_weather_now(conn)
    now = None
    if last is not None:
        now = _with_word({k: v for k, v in last.items() if k != "fetched_at"})
    answer = cap([_with_word(r) for r in list_weather_days(conn, date_from, date_to)], newest=True)
    points = [{k: r[k] for k in HISTORY_KEYS} for r in list_weather_now(conn, date_from, date_to)]
    return {"now": now, **answer, "history": cap(points, newest=True), "hourly": _hourly(conn)}


def _hourly(conn: sqlite3.Connection) -> dict[str, Any]:
    """Прогноз по часам: часы суток, кратные 3, от вчерашней даты компьютера на 8 дат;
    от периода вызова не зависит, остаются первые 60 строк."""
    yesterday = tools.today() - timedelta(days=1)
    hours = list_weather_hours(
        conn, yesterday.isoformat(), (yesterday + timedelta(days=HOURLY_DAYS)).isoformat()
    )
    rows = [
        {k: h[k] for k in HOURLY_KEYS} for h in hours if int(h["time"][11:13]) % HOURLY_STEP == 0
    ]
    return cap(rows)
