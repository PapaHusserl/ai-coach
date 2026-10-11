"""Привычки: habit и отметки habit_log."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, upsert
from ai_coach.store.sport_nutrition import add_row, delete_row, edit_row, get_row, list_rows

HABIT = "habit"


def add_habit(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: name, created_at; не обязательно unit, updated_at. Имя занято - ValueError."""
    return add_row(conn, HABIT, values)


def list_habits(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Живые привычки по имени."""
    return list_rows(conn, HABIT)


def get_habit(conn: sqlite3.Connection, key: int | str) -> dict[str, Any] | None:
    """Живая привычка по id или по имени (без учёта регистра); нет или удалена - None."""
    return get_row(conn, HABIT, key)


def edit_habit(
    conn: sqlite3.Connection, habit_id: int, values: dict[str, Any], updated_at: str
) -> bool:
    return edit_row(conn, HABIT, habit_id, values, updated_at)


def delete_habit(conn: sqlite3.Connection, habit_id: int, deleted_at: str) -> bool:
    """Пометка удаления; отметки остаются."""
    return delete_row(conn, HABIT, habit_id, deleted_at)


def mark_habit(
    conn: sqlite3.Connection,
    habit_id: int,
    day: str,
    done: int,
    amount: float | None,
    logged_at: str,
) -> None:
    """Отметка за день: повтор заменяет прежнюю (done 1 - сделано, 0 - нет)."""
    values = {"date": day, "habit_id": habit_id, "done": done, "amount": amount}
    upsert(conn, "habit_log", ["date", "habit_id"], {**values, "logged_at": logged_at})


def unmark_habit(conn: sqlite3.Connection, habit_id: int, day: str) -> bool:
    """Снять отметку за день (строка удаляется; другие дни не трогает). False - отметки нет."""
    sql = "DELETE FROM habit_log WHERE habit_id = ? AND date = ?"
    return conn.execute(sql, (habit_id, day)).rowcount > 0


def list_habit_log(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Отметки с датой start..end включительно (в т.ч. по удалённым привычкам), по дате:
    date, habit_id, name, unit, done, amount, logged_at."""
    sql = (
        "SELECT l.date, l.habit_id, h.name, h.unit, l.done, l.amount, l.logged_at "
        "FROM habit_log l JOIN habit h ON h.id = l.habit_id "
        "WHERE l.date BETWEEN ? AND ? ORDER BY l.date, h.name, l.id"
    )
    return fetch_all(conn, sql, (start, end))


def habits_on(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Живые привычки с отметкой за день: id, name, unit, done, amount (done True/False,
    None - не отмечена)."""
    sql = (
        "SELECT h.id, h.name, h.unit, l.done, l.amount FROM habit h "
        "LEFT JOIN habit_log l ON l.habit_id = h.id AND l.date = ? "
        "WHERE h.deleted_at IS NULL ORDER BY h.name, h.id"
    )
    rows = fetch_all(conn, sql, (day,))
    return [{**r, "done": None if r["done"] is None else bool(r["done"])} for r in rows]
