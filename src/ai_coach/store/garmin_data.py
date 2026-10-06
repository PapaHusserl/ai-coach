"""Данные из Garmin: daily_metrics, activities, strength_sets. Upsert по естественному ключу."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, upsert


def upsert_daily_metrics(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ — date. values: колонки daily_metrics, raw_json обязателен (объект или строка)."""
    upsert(conn, "daily_metrics", ["date"], values)


def get_daily_metrics(conn: sqlite3.Connection, date: str) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM daily_metrics WHERE date = ?", (date,))


def list_daily_metrics(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Дни start..end включительно, по возрастанию даты."""
    sql = "SELECT * FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date"
    return fetch_all(conn, sql, (start, end))


def upsert_activity(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ — activity_id. raw_json обязателен."""
    upsert(conn, "activities", ["activity_id"], values)


def get_activity(conn: sqlite3.Connection, activity_id: int) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM activities WHERE activity_id = ?", (activity_id,))


def list_activities(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Активности с датой старта (local) start..end включительно, по времени старта."""
    sql = (
        "SELECT * FROM activities WHERE substr(start_time_local, 1, 10) BETWEEN ? AND ? "
        "ORDER BY start_time_local"
    )
    return fetch_all(conn, sql, (start, end))


def upsert_strength_set(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ — (activity_id, set_index). Активность должна уже быть в activities."""
    upsert(conn, "strength_sets", ["activity_id", "set_index"], values)


def list_strength_sets(conn: sqlite3.Connection, activity_id: int) -> list[dict[str, Any]]:
    sql = "SELECT * FROM strength_sets WHERE activity_id = ? ORDER BY set_index"
    return fetch_all(conn, sql, (activity_id,))
