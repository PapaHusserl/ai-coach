"""Журнал недельных обзоров: review_log."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_one, upsert


def mark_review(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ - week_start (понедельник). values: week_start, done_at; необязательно note.
    Повтор заменяет запись; note обновляется, только если передан."""
    upsert(conn, "review_log", ["week_start"], values)


def get_review(conn: sqlite3.Connection, week_start: str) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM review_log WHERE week_start = ?", (week_start,))
