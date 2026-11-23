"""Очередь отчётов тренера о проблемах системы: system_report. Строки не удаляются."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update


def add_report(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: text (не пуст), created_at."""
    return insert(conn, "system_report", values)


def get_report(conn: sqlite3.Connection, report_id: int) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM system_report WHERE id = ?", (report_id,))


def open_reports(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Открытые отчёты по id."""
    return fetch_all(conn, "SELECT * FROM system_report WHERE status = 'open' ORDER BY id", ())


def list_reports(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Все отчёты по id."""
    return fetch_all(conn, "SELECT * FROM system_report ORDER BY id", ())


def close_report(
    conn: sqlite3.Connection, report_id: int, status: str, closed_at: str, backlog: int | None
) -> bool:
    """open -> done | dropped; не open или нет отчёта — False, строка не меняется."""
    row = get_report(conn, report_id)
    if row is None or row["status"] != "open":
        return False
    update(
        conn,
        "system_report",
        report_id,
        {"status": status, "closed_at": closed_at, "backlog": backlog},
    )
    return True
