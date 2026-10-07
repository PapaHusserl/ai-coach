"""Профиль спортсмена: profile_log. Записи только добавляются."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert


def add_profile_entry(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: key, value (текст), source (manual/garmin), logged_at, raw_json (необязателен)."""
    return insert(conn, "profile_log", values)


def list_profile_entries(conn: sqlite3.Connection, end: str | None = None) -> list[dict[str, Any]]:
    """Записи по времени. end — дата, записи с датой logged_at до неё включительно."""
    sql = "SELECT * FROM profile_log WHERE substr(logged_at, 1, 10) <= ? ORDER BY logged_at, id"
    return fetch_all(conn, sql, (end or "9999-12-31",))


def last_garmin_entry(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    """Последняя запись ключа из Garmin."""
    sql = (
        "SELECT * FROM profile_log WHERE key = ? AND source = 'garmin' "
        "ORDER BY logged_at DESC, id DESC LIMIT 1"
    )
    return fetch_one(conn, sql, (key,))
