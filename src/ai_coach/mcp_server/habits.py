"""Инструменты MCP: практики и привычки (отдельно от tools.py из-за размера)."""

import sqlite3
from typing import Any

from ai_coach.mcp_server.tools import cap, period
from ai_coach.store.habits import list_habit_log, list_habits
from ai_coach.store.practices import list_practices


def practices(conn: sqlite3.Connection) -> dict[str, Any]:
    """Практики восстановления (живые): id, name, kind, minutes, trigger, steps."""
    skip = ("created_at", "updated_at", "deleted_at")
    return cap([{k: v for k, v in row.items() if k not in skip} for row in list_practices(conn)])


def habits(conn: sqlite3.Connection) -> dict[str, Any]:
    """Привычки (живые): id, name, unit (единица числа или None)."""
    skip = ("created_at", "updated_at", "deleted_at")
    return cap([{k: v for k, v in row.items() if k not in skip} for row in list_habits(conn)])


def habit_log(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, Any]:
    """Отметки привычек за период (включительно): date, habit_id, name, unit, done (0/1), amount
    (число или None), logged_at. Только чтение: отмечает пользователь."""
    period(date_from, date_to)
    return cap(list_habit_log(conn, date_from, date_to), newest=True)
