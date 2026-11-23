"""Погода: weather_now (наблюдения на момент синка) и weather_days (прогноз по дням).

Читающие функции отдают строки без lat, lon, place_source и utc_offset_seconds.
"""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, upsert

NOW_COLUMNS = "observed_at, temperature, apparent, code, wind, pressure, fetched_at"
HOUR_COLUMNS = "time, temperature, pressure, pressure_surface, humidity, wind, fetched_at, source"
DAY_COLUMNS = "date, code, t_max, t_min, precip_prob, fetched_at"


def add_weather_now(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Наблюдение: observed_at (ключ), temperature, apparent, code, wind, pressure, fetched_at,
    lat, lon, place_source, utc_offset_seconds; то же время - перезапись."""
    upsert(conn, "weather_now", ["observed_at"], values)


def upsert_weather_day(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """День прогноза: date (ключ), code, t_max, t_min, precip_prob, fetched_at, lat, lon."""
    upsert(conn, "weather_days", ["date"], values)


def upsert_weather_hours(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    """Часы: готовые строки (time - ключ, шесть значений часа, fetched_at, lat, lon,
    place_source, source); тот же час - перезапись. Транзакцию держит вызывающий."""
    for row in rows:
        upsert(conn, "weather_hours", ["time"], row)


def list_weather_hours(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Часы с датой time от start до end включительно, по возрастанию времени."""
    sql = (
        f"SELECT {HOUR_COLUMNS} FROM weather_hours WHERE substr(time, 1, 10) BETWEEN ? AND ? "
        "ORDER BY time"
    )
    return fetch_all(conn, sql, (start, end))


def days_with_hours(conn: sqlite3.Connection, start: str, end: str) -> set[str]:
    """Даты start..end, где есть час с fetched_at позже даты time (старый прогноз не в счёт)."""
    sql = (
        "SELECT DISTINCT substr(time, 1, 10) AS day FROM weather_hours "
        "WHERE substr(time, 1, 10) BETWEEN ? AND ? "
        "AND substr(fetched_at, 1, 10) > substr(time, 1, 10)"
    )
    return {row["day"] for row in fetch_all(conn, sql, (start, end))}


def last_weather_now(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Последнее наблюдение по времени observed_at."""
    sql = f"SELECT {NOW_COLUMNS} FROM weather_now ORDER BY observed_at DESC LIMIT 1"
    return fetch_one(conn, sql, ())


def list_weather_now(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Наблюдения с датой observed_at от start до end включительно, по возрастанию времени."""
    sql = (
        f"SELECT {NOW_COLUMNS} FROM weather_now WHERE substr(observed_at, 1, 10) BETWEEN ? AND ? "
        "ORDER BY observed_at"
    )
    return fetch_all(conn, sql, (start, end))


def list_weather_days(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Дни прогноза от start до end включительно, по возрастанию даты."""
    sql = f"SELECT {DAY_COLUMNS} FROM weather_days WHERE date BETWEEN ? AND ? ORDER BY date"
    return fetch_all(conn, sql, (start, end))
