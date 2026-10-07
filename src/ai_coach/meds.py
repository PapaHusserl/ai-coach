"""Курсы витаминов и безрецептурных средств для MCP: без служебных полей и компактно.
Ничего не пишет в базу."""

import sqlite3
from typing import Any

from ai_coach.sport_nutrition import has_training, without_service
from ai_coach.store.meds import list_meds, meds_on

SHORT_FIELDS = ("id", "name", "kind", "dose", "unit", "schedule", "time_note", "end_date")


def meds_for_day(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Курсы дня: daily всегда, training_day/before/after - только в день тренировки."""
    training = has_training(conn, day)
    return [m for m in meds_on(conn, day) if training or m["schedule"] == "daily"]


def public_meds(conn: sqlite3.Connection, day: str | None) -> list[dict[str, Any]]:
    """Курсы дня (YYYY-MM-DD; тренировочные - при тренировке) или все живые (day None),
    без служебных полей."""
    rows = list_meds(conn) if day is None else meds_for_day(conn, day)
    return [without_service(row) for row in rows]


def short_meds(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Курсы на день для сводки: без заметки и дат начала."""
    return [{k: row[k] for k in SHORT_FIELDS} for row in meds_for_day(conn, day)]
