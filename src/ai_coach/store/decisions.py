"""Очередь решений на будущее: decision_log. Строки не удаляются."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update


def add_decision(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: text (не пуст), created_at; необязательные kind, ref_id, target_date."""
    return insert(conn, "decision_log", values)


def get_decision(conn: sqlite3.Connection, decision_id: int) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM decision_log WHERE id = ?", (decision_id,))


def open_by_ref(conn: sqlite3.Connection, kind: str, ref_id: int) -> dict[str, Any] | None:
    """Открытый пункт объекта (тренировки или фазы)."""
    sql = "SELECT * FROM decision_log WHERE kind = ? AND ref_id = ? AND status = 'open'"
    return fetch_one(conn, sql, (kind, ref_id))


def open_decisions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Открытые пункты: ближайший target_date, без даты в конце, затем старший created_at."""
    sql = (
        "SELECT * FROM decision_log WHERE status = 'open' "
        "ORDER BY target_date IS NULL, target_date, created_at, id"
    )
    return fetch_all(conn, sql, ())


def list_decisions(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Пункты с created_at или decided_at в днях start..end включительно, по created_at."""
    sql = (
        "SELECT * FROM decision_log WHERE substr(created_at, 1, 10) BETWEEN ?1 AND ?2 "
        "OR substr(decided_at, 1, 10) BETWEEN ?1 AND ?2 ORDER BY created_at, id"
    )
    return fetch_all(conn, sql, (start, end))


def close_decision(
    conn: sqlite3.Connection, decision_id: int, status: str, decided_at: str
) -> bool:
    """open -> yes | no | dropped; не open или нет пункта — False, строка не меняется."""
    row = get_decision(conn, decision_id)
    if row is None or row["status"] != "open":
        return False
    update(conn, "decision_log", decision_id, {"status": status, "decided_at": decided_at})
    return True


def set_result(conn: sqlite3.Connection, decision_id: int, result: str, result_at: str) -> bool:
    """Исполнение пункта yes, один раз; иначе False, строка не меняется."""
    row = get_decision(conn, decision_id)
    if row is None or row["status"] != "yes" or row["result"] is not None:
        return False
    update(conn, "decision_log", decision_id, {"result": result, "result_at": result_at})
    return True
