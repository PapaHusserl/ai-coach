"""События тренера в календаре: coach_events. Функции записи НЕ делают commit."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update

ACTIVE = ("draft", "written")


def add_event(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: kind, title, date, start_at, end_at, created_at; не обязательно all_day, note,
    category, alarm_min, repeat, workout_id, practice_id, status (по умолчанию draft)."""
    return insert(conn, "coach_events", values)


def get_event(conn: sqlite3.Connection, event_id: int) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM coach_events WHERE id = ?", (event_id,))


def update_event(conn: sqlite3.Connection, event_id: int, values: dict[str, Any]) -> None:
    update(conn, "coach_events", event_id, values)


def list_events(
    conn: sqlite3.Connection,
    date_from: str,
    date_to: str,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """События с датой начала date_from..date_to включительно (statuses - только эти статусы),
    по времени начала и id."""
    sql = "SELECT * FROM coach_events WHERE date BETWEEN ? AND ?"
    args: tuple[Any, ...] = (date_from, date_to)
    if statuses is not None:
        sql += f" AND status IN ({', '.join('?' for _ in statuses)})"
        args += statuses
    return fetch_all(conn, sql + " ORDER BY start_at, id", args)


def category_by_uid(conn: sqlite3.Connection, calendar_uid: str) -> str | None:
    """Категория события с этим calendar_uid; нет события или категории - None."""
    found = find_by_uid(conn, calendar_uid)
    return found["category"] if found else None


def find_by_uid(conn: sqlite3.Connection, calendar_uid: str) -> dict[str, Any] | None:
    """Последнее событие с этим calendar_uid (любого статуса)."""
    sql = "SELECT * FROM coach_events WHERE calendar_uid = ? ORDER BY id DESC"
    return fetch_one(conn, sql, (calendar_uid,))


def active_repeat(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Повторяющееся событие в статусе draft или written (одно на всю базу)."""
    sql = "SELECT * FROM coach_events WHERE repeat IS NOT NULL AND status IN ('draft', 'written')"
    return fetch_one(conn, sql, ())
