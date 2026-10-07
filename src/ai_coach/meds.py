"""Курсы витаминов и безрецептурных средств для MCP: без служебных полей и компактно.
Ничего не пишет в базу."""

import sqlite3
from typing import Any

from ai_coach.sport_nutrition import without_service
from ai_coach.store.meds import list_meds, meds_on

SHORT_FIELDS = ("id", "name", "kind", "dose", "unit", "schedule", "time_note", "end_date")


def public_meds(conn: sqlite3.Connection, day: str | None) -> list[dict[str, Any]]:
    """Курсы на день (YYYY-MM-DD) или все живые (day None), без служебных полей."""
    rows = list_meds(conn) if day is None else meds_on(conn, day)
    return [without_service(row) for row in rows]


def short_meds(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Курсы на день для сводки: без заметки и дат начала."""
    return [{k: row[k] for k in SHORT_FIELDS} for row in meds_on(conn, day)]
