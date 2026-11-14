"""События тренера в календаре: coach_events. Функции записи НЕ делают commit."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update, upsert

ACTIVE = ("draft", "written")


def mark_done(conn: sqlite3.Connection, event_id: int, day: str, done: int, logged_at: str) -> None:
    """Отметка пункта за день: повтор заменяет прежнюю (done 1 - сделал, 0 - пропустил)."""
    values = {"event_id": event_id, "date": day, "done": done, "logged_at": logged_at}
    upsert(conn, "done_log", ["event_id", "date"], values)


def unmark_done(conn: sqlite3.Connection, event_id: int, day: str) -> bool:
    """Снять отметку пункта за день (другие дни не трогает). False - отметки нет."""
    sql = "DELETE FROM done_log WHERE event_id = ? AND date = ?"
    return conn.execute(sql, (event_id, day)).rowcount > 0


def list_done(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Отметки пунктов с датой start..end включительно, по дате и времени."""
    sql = "SELECT * FROM done_log WHERE date BETWEEN ? AND ? ORDER BY date, logged_at, id"
    return fetch_all(conn, sql, (start, end))


def add_event(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: kind, title, date, start_at, end_at, created_at; не обязательно all_day, note,
    category, survey, alarm_min, repeat, workout_id, practice_id, status (по умолчанию draft)."""
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


def own_uids(conn: sqlite3.Connection) -> set[str]:
    """calendar_uid всех событий тренера, записанных в календарь."""
    sql = "SELECT calendar_uid FROM coach_events WHERE calendar_uid IS NOT NULL"
    return {r["calendar_uid"] for r in fetch_all(conn, sql, ())}


def active_repeats(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Повторяющиеся события в статусе draft или written, по времени начала."""
    sql = (
        "SELECT * FROM coach_events WHERE repeat IS NOT NULL AND status IN ('draft', 'written') "
        "ORDER BY start_at, id"
    )
    return fetch_all(conn, sql, ())
