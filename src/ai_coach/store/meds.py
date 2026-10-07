"""Курсы витаминов и безрецептурных средств (med_course)."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all
from ai_coach.store.sport_nutrition import add_row, delete_row, edit_row, get_row, list_rows

MED = "med_course"


def add_med(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: name, kind, dose, unit, schedule, start_date, created_at; не обязательно
    time_note, end_date, note, updated_at. Имя занято - ValueError."""
    return add_row(conn, MED, values)


def list_meds(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_rows(conn, MED)


def get_med(conn: sqlite3.Connection, key: int | str) -> dict[str, Any] | None:
    return get_row(conn, MED, key)


def edit_med(
    conn: sqlite3.Connection, med_id: int, values: dict[str, Any], updated_at: str
) -> bool:
    return edit_row(conn, MED, med_id, values, updated_at)


def delete_med(conn: sqlite3.Connection, med_id: int, deleted_at: str) -> bool:
    return delete_row(conn, MED, med_id, deleted_at)


def meds_on(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Живые курсы, идущие в этот день (границы включительно; без end_date - бессрочно)."""
    sql = (
        f"SELECT * FROM {MED} WHERE deleted_at IS NULL AND start_date <= ? "
        "AND (end_date IS NULL OR end_date >= ?) ORDER BY name, id"
    )
    return fetch_all(conn, sql, (day, day))
