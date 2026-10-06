"""Журналы: weight_log, food_log, sync_log."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update


def add_weight(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: measured_at, weight_kg."""
    return insert(conn, "weight_log", values)


def list_weights(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Замеры с датой measured_at start..end включительно, по времени."""
    sql = (
        "SELECT * FROM weight_log WHERE substr(measured_at, 1, 10) BETWEEN ? AND ? "
        "ORDER BY measured_at, id"
    )
    return fetch_all(conn, sql, (start, end))


def add_food(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: logged_at, text (сырой текст; КБЖУ пусты до /coach-food)."""
    return insert(conn, "food_log", values)


def update_food(conn: sqlite3.Connection, food_id: int, values: dict[str, Any]) -> None:
    """Запись КБЖУ: kcal, protein_g, fat_g, carbs_g."""
    update(conn, "food_log", food_id, values)


def list_food(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Записи с датой logged_at start..end включительно, по времени."""
    sql = (
        "SELECT * FROM food_log WHERE substr(logged_at, 1, 10) BETWEEN ? AND ? "
        "ORDER BY logged_at, id"
    )
    return fetch_all(conn, sql, (start, end))


def add_sync_log(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: started_at, kind (sync/import), status, finished_at, message."""
    return insert(conn, "sync_log", values)


def last_sync_log(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Последняя запись sync_log (по id)."""
    return fetch_one(conn, "SELECT * FROM sync_log ORDER BY id DESC LIMIT 1", ())
