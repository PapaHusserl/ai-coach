"""Продукты дома (pantry_log) и дни с предложенным рационом (meal_plan_log)."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, upsert


def add_entry(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: item, qty, unit (g/ml/pcs), op (add/use/set), logged_at, note (необязателен)."""
    return insert(conn, "pantry_log", values)


def list_entries(conn: sqlite3.Connection, item: str | None = None) -> list[dict[str, Any]]:
    """Записи по времени; item — только этого продукта."""
    if item is None:
        return fetch_all(conn, "SELECT * FROM pantry_log ORDER BY logged_at, id", ())
    sql = "SELECT * FROM pantry_log WHERE item = ? ORDER BY logged_at, id"
    return fetch_all(conn, sql, (item,))


def mark_meal_plan(conn: sqlite3.Connection, day: str, logged_at: str) -> None:
    """Отметить, что рацион на день предложен (повторно — без ошибки)."""
    upsert(conn, "meal_plan_log", ["date"], {"date": day, "logged_at": logged_at})


def has_meal_plan(conn: sqlite3.Connection, day: str) -> bool:
    return fetch_one(conn, "SELECT date FROM meal_plan_log WHERE date = ?", (day,)) is not None
