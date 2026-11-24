"""Инструмент MCP: недельный обзор (отдельно от tools.py из-за размера)."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.load.recovery import RESPONSE_DAYS, recovery_report
from ai_coach.mcp_server import tools
from ai_coach.review import days_tss, weekly_review
from ai_coach.store.journal import wellbeing_day

MAX_WEEKS = 12


def weekly(conn: sqlite3.Connection, weeks: int = 4) -> dict[str, Any]:
    """Недельный обзор: последние weeks ISO-недель (Пн-Вс, от 1 до 12), последняя - текущая
    неполная (partial). По неделе: tss, total, work_hours, evening_hours, weekend_work_hours,
    todo_closed, todo_open, mood, stress, fatigue, irritability, sleep, readiness (средние, null -
    данных нет), rest_hours (среднее ручных часов отдыха по дням с ответом, null - ответов нет),
    rest_days (дней с ответом), days_off (дней без работы: не больше 0,5 ч), days_with_data и
    delta - разница с предыдущей неделей (null - нет базы).
    Выводов нет. recovery - отклик ночи на нагрузку (recovery_report)."""
    if not 1 <= weeks <= MAX_WEEKS:
        raise ToolError(f"weeks от 1 до {MAX_WEEKS}, получено: {weeks}")
    day = wellbeing_day(datetime.now())
    first = (date.fromisoformat(day) - timedelta(days=RESPONSE_DAYS)).isoformat()
    tss = days_tss(conn, first, day)
    return {
        **tools.cap(weekly_review(conn, day, weeks)),
        "recovery": recovery_report(conn, day, tss or {}),
    }
