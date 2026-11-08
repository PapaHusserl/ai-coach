"""Еда в пульте: остаток дня и запись текстом в food_log (без commit)."""

import sqlite3
from typing import Any

from ai_coach.profile.nutrition import remaining
from ai_coach.store.journal import add_food, list_food
from ai_coach.web.errors import MarkError


def meal_view(conn: sqlite3.Connection, day: str, target: dict[str, Any]) -> dict[str, Any]:
    """Остаток дня day: {"remaining": {...} | None}; target - цель дня (profile_nutrition).
    Считается раз на день, записи пункта кладёт в meal day._items из marks."""
    return {"remaining": remaining(target, list_food(conn, day, day))}


def save_food(conn: sqlite3.Connection, payload: dict[str, Any], base: dict[str, Any]) -> int:
    """Запись еды пункта текстом; КБЖУ пусты до /coach-food. base: event_id, date, logged_at."""
    value = payload.get("text")
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise MarkError("Текст не может быть пустым.")
    return add_food(
        conn, {"event_id": base["event_id"], "logged_at": base["logged_at"], "text": text}
    )
