"""Журнал приёма добавок (intake_log): только добавление, удаление - пометка."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, insert
from ai_coach.store.sport_nutrition import SUPPLEMENT, delete_row

INTAKE = "intake_log"


def log_intake(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """Приём добавки. values: item_id, date, taken_at; не обязательно dose (нет - по норме),
    note. Несколько приёмов в день разрешены."""
    return insert(conn, INTAKE, {"kind": SUPPLEMENT, **values})


def list_intake(conn: sqlite3.Connection, date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Живые приёмы добавок за даты включительно, с именем и единицей добавки (удалённая
    добавка тоже видна). dose - принятая доза, None - по норме."""
    sql = (
        "SELECT l.id, l.kind, l.item_id, s.name, l.date, l.taken_at, l.dose, s.unit, l.note "
        f"FROM {INTAKE} l JOIN {SUPPLEMENT} s ON s.id = l.item_id "
        "WHERE l.kind = 'supplement' AND l.deleted_at IS NULL AND l.date BETWEEN ? AND ? "
        "ORDER BY l.date, l.taken_at, l.id"
    )
    return fetch_all(conn, sql, (date_from, date_to))


def delete_intake(conn: sqlite3.Connection, log_id: int, deleted_at: str) -> bool:
    return delete_row(conn, INTAKE, log_id, deleted_at)
