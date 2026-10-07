"""Спортивное питание: протоколы (nutrition_protocol) и добавки (supplement)."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update

PROTOCOL = "nutrition_protocol"
SUPPLEMENT = "supplement"


def list_rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    """Живые строки по имени."""
    return fetch_all(conn, f"SELECT * FROM {table} WHERE deleted_at IS NULL ORDER BY name, id", ())


def name_taken(
    conn: sqlite3.Connection, table: str, name: str, except_id: int | None = None
) -> bool:
    """Есть ли живая строка с таким именем (без учёта регистра)."""
    return any(
        r["name"].casefold() == name.casefold() and r["id"] != except_id
        for r in list_rows(conn, table)
    )


def add_row(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> int:
    if name_taken(conn, table, values["name"]):
        raise ValueError(f"{values['name']!r} уже есть.")
    return insert(conn, table, {"updated_at": values["created_at"], **values})


def get_row(conn: sqlite3.Connection, table: str, key: int | str) -> dict[str, Any] | None:
    """Живая строка по id или по имени (без учёта регистра); нет или удалена - None."""
    if isinstance(key, int):
        sql = f"SELECT * FROM {table} WHERE id = ? AND deleted_at IS NULL"
        return fetch_one(conn, sql, (key,))
    found = [r for r in list_rows(conn, table) if r["name"].casefold() == key.strip().casefold()]
    return found[0] if found else None


def edit_row(
    conn: sqlite3.Connection, table: str, row_id: int, values: dict[str, Any], updated_at: str
) -> bool:
    """True - исправлено; False - строки нет или она удалена. Имя занято - ValueError."""
    if get_row(conn, table, row_id) is None:
        return False
    if "name" in values and name_taken(conn, table, values["name"], row_id):
        raise ValueError(f"{values['name']!r} уже есть.")
    update(conn, table, row_id, {**values, "updated_at": updated_at})
    return True


def delete_row(conn: sqlite3.Connection, table: str, row_id: int, deleted_at: str) -> bool:
    """Пометка удаления. True - удалена; False - строки нет или уже удалена."""
    sql = f"UPDATE {table} SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL"
    return conn.execute(sql, (deleted_at, row_id)).rowcount > 0


def add_protocol(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: name, phase, created_at; не обязательно sport, min_duration_min, offset_min,
    carbs_g, protein_g, fluid_ml, sodium_mg, note, updated_at. Имя занято - ValueError."""
    return add_row(conn, PROTOCOL, values)


def list_protocols(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_rows(conn, PROTOCOL)


def get_protocol(conn: sqlite3.Connection, key: int | str) -> dict[str, Any] | None:
    return get_row(conn, PROTOCOL, key)


def edit_protocol(
    conn: sqlite3.Connection, protocol_id: int, values: dict[str, Any], updated_at: str
) -> bool:
    return edit_row(conn, PROTOCOL, protocol_id, values, updated_at)


def delete_protocol(conn: sqlite3.Connection, protocol_id: int, deleted_at: str) -> bool:
    return delete_row(conn, PROTOCOL, protocol_id, deleted_at)


def add_supplement(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: name, dose, unit, schedule, created_at; не обязательно time_note, note,
    updated_at. Имя занято - ValueError."""
    return add_row(conn, SUPPLEMENT, values)


def list_supplements(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_rows(conn, SUPPLEMENT)


def get_supplement(conn: sqlite3.Connection, key: int | str) -> dict[str, Any] | None:
    return get_row(conn, SUPPLEMENT, key)


def edit_supplement(
    conn: sqlite3.Connection, supplement_id: int, values: dict[str, Any], updated_at: str
) -> bool:
    return edit_row(conn, SUPPLEMENT, supplement_id, values, updated_at)


def delete_supplement(conn: sqlite3.Connection, supplement_id: int, deleted_at: str) -> bool:
    return delete_row(conn, SUPPLEMENT, supplement_id, deleted_at)
