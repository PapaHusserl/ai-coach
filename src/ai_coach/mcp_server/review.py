"""Инструмент MCP: недельный обзор (отдельно от tools.py из-за размера)."""

import sqlite3
from datetime import datetime
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.mcp_server import tools
from ai_coach.review import weekly_review
from ai_coach.store.journal import wellbeing_day

MAX_WEEKS = 12


def weekly(conn: sqlite3.Connection, weeks: int = 4) -> dict[str, Any]:
    """Недельный обзор: последние weeks ISO-недель (Пн-Вс, от 1 до 12), последняя - текущая
    неполная (partial). По неделе: tss, total, work_hours, evening_hours, weekend_work_hours,
    todo_closed, todo_open, mood, stress, sleep, readiness (средние, null - данных нет),
    days_with_data и delta - разница с предыдущей неделей (null - нет базы). Выводов нет."""
    if not 1 <= weeks <= MAX_WEEKS:
        raise ToolError(f"weeks от 1 до {MAX_WEEKS}, получено: {weeks}")
    return tools.cap(weekly_review(conn, wellbeing_day(datetime.now()), weeks))
