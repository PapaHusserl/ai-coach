"""План: planned_workouts и plan_actual."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update


def add_planned_workout(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: date, sport, name, workout_json (объект или строка); status по умолчанию draft."""
    return insert(conn, "planned_workouts", values)


def update_planned_workout(
    conn: sqlite3.Connection, workout_id: int, values: dict[str, Any]
) -> None:
    update(conn, "planned_workouts", workout_id, values)


def get_planned_workout(conn: sqlite3.Connection, workout_id: int) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM planned_workouts WHERE id = ?", (workout_id,))


def list_planned_workouts(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Тренировки с датой start..end включительно, по дате и id."""
    sql = "SELECT * FROM planned_workouts WHERE date BETWEEN ? AND ? ORDER BY date, id"
    return fetch_all(conn, sql, (start, end))


def add_plan_actual(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: date, kind (done/skipped/extra/different), planned_id, activity_id, details_json."""
    return insert(conn, "plan_actual", values)


def list_plan_actual(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    sql = "SELECT * FROM plan_actual WHERE date BETWEEN ? AND ? ORDER BY date, id"
    return fetch_all(conn, sql, (start, end))


def delete_plan_actual(conn: sqlite3.Connection, start: str, end: str) -> None:
    """Очистка периода перед пересчётом сопоставления."""
    conn.execute("DELETE FROM plan_actual WHERE date BETWEEN ? AND ?", (start, end))
