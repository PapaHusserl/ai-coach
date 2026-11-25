"""Журнал приёма добавок и курсов (intake_log): только добавление, удаление - пометка."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, insert
from ai_coach.store.meds import MED
from ai_coach.store.sport_nutrition import SUPPLEMENT

INTAKE = "intake_log"
TABLES = {SUPPLEMENT: SUPPLEMENT, "med": MED}  # kind журнала -> таблица, на которую смотрит item_id


def log_intake(conn: sqlite3.Connection, values: dict[str, Any], kind: str = SUPPLEMENT) -> int:
    """Приём добавки (kind supplement) или курса (med). values: item_id, date, taken_at; не
    обязательно dose (нет - по норме), note. Несколько приёмов в день разрешены."""
    return insert(conn, INTAKE, {"kind": kind, **values})


def list_intake(
    conn: sqlite3.Connection, date_from: str, date_to: str, kind: str = SUPPLEMENT
) -> list[dict[str, Any]]:
    """Живые приёмы добавок (или курсов, kind med) за даты включительно, с именем и единицей
    добавки или курса (удалённые тоже видны). dose - принятая доза, None - по норме."""
    sql = (
        "SELECT l.id, l.kind, l.item_id, s.name, l.date, l.taken_at, l.dose, s.unit, l.note "
        f"FROM {INTAKE} l JOIN {TABLES[kind]} s ON s.id = l.item_id "
        "WHERE l.kind = ? AND l.deleted_at IS NULL AND l.date BETWEEN ? AND ? "
        "ORDER BY l.date, l.taken_at, l.id"
    )
    return fetch_all(conn, sql, (kind, date_from, date_to))


def delete_intake(
    conn: sqlite3.Connection, log_id: int, deleted_at: str, kind: str = SUPPLEMENT
) -> bool:
    """Снять приём своего вида: чужой вид (курс при kind supplement и наоборот) не трогается."""
    sql = f"UPDATE {INTAKE} SET deleted_at = ? WHERE id = ? AND kind = ? AND deleted_at IS NULL"
    return conn.execute(sql, (deleted_at, log_id, kind)).rowcount > 0
