"""Практики восстановления: practice."""

import sqlite3
from typing import Any

from ai_coach.store.sport_nutrition import add_row, get_row, list_rows

PRACTICE = "practice"


def add_practice(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: name, kind, minutes, steps, created_at; не обязательно trigger, updated_at.
    Имя занято живой практикой - ValueError."""
    return add_row(conn, PRACTICE, values)


def list_practices(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Живые практики по имени."""
    return list_rows(conn, PRACTICE)


def get_practice(conn: sqlite3.Connection, key: int | str) -> dict[str, Any] | None:
    """Живая практика по id или по имени (без учёта регистра); нет или удалена - None."""
    return get_row(conn, PRACTICE, key)
