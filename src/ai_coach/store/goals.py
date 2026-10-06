"""Цели, фазы и события целей. Логика — в goals/, здесь только доступ к таблицам."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update


def add_goal(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    return insert(conn, "goals", values)


def update_goal(conn: sqlite3.Connection, goal_id: int, values: dict[str, Any]) -> None:
    update(conn, "goals", goal_id, values)


def get_goal(conn: sqlite3.Connection, goal_id: int) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM goals WHERE id = ?", (goal_id,))


def list_goals(conn: sqlite3.Connection, status: str | None = None) -> list[dict[str, Any]]:
    if status is None:
        return fetch_all(conn, "SELECT * FROM goals ORDER BY id", ())
    return fetch_all(conn, "SELECT * FROM goals WHERE status = ? ORDER BY id", (status,))


def add_goal_event(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: goal_id, event_type, occurred_at, payload_json (объект или строка)."""
    return insert(conn, "goal_events", values)


def list_goal_events(conn: sqlite3.Connection, goal_id: int | None = None) -> list[dict[str, Any]]:
    """События по возрастанию occurred_at, затем id; goal_id=None — по всем целям."""
    if goal_id is None:
        return fetch_all(conn, "SELECT * FROM goal_events ORDER BY occurred_at, id", ())
    sql = "SELECT * FROM goal_events WHERE goal_id = ? ORDER BY occurred_at, id"
    return fetch_all(conn, sql, (goal_id,))


def add_phase(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """По умолчанию status='proposed'."""
    return insert(conn, "phases", values)


def update_phase(conn: sqlite3.Connection, phase_id: int, values: dict[str, Any]) -> None:
    update(conn, "phases", phase_id, values)


def get_phase(conn: sqlite3.Connection, phase_id: int) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM phases WHERE id = ?", (phase_id,))


def list_phases(conn: sqlite3.Connection, status: str | None = None) -> list[dict[str, Any]]:
    if status is None:
        return fetch_all(conn, "SELECT * FROM phases ORDER BY id", ())
    return fetch_all(conn, "SELECT * FROM phases WHERE status = ? ORDER BY id", (status,))


def add_phase_goal(conn: sqlite3.Connection, phase_id: int, goal_id: int) -> None:
    conn.execute("INSERT INTO phase_goals (phase_id, goal_id) VALUES (?, ?)", (phase_id, goal_id))


def delete_phase_goals(conn: sqlite3.Connection, phase_id: int) -> None:
    conn.execute("DELETE FROM phase_goals WHERE phase_id = ?", (phase_id,))


def list_phase_goal_ids(conn: sqlite3.Connection, phase_id: int) -> list[int]:
    sql = "SELECT goal_id FROM phase_goals WHERE phase_id = ? ORDER BY goal_id"
    return [row["goal_id"] for row in fetch_all(conn, sql, (phase_id,))]


def add_phase_event(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: phase_id, event_type (proposed/accepted), occurred_at, payload_json."""
    return insert(conn, "phase_events", values)


def list_phase_events(
    conn: sqlite3.Connection, phase_id: int | None = None
) -> list[dict[str, Any]]:
    """События по возрастанию occurred_at, затем id; phase_id=None — по всем фазам."""
    if phase_id is None:
        return fetch_all(conn, "SELECT * FROM phase_events ORDER BY occurred_at, id", ())
    sql = "SELECT * FROM phase_events WHERE phase_id = ? ORDER BY occurred_at, id"
    return fetch_all(conn, sql, (phase_id,))
