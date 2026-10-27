"""Инструмент MCP: нагрузка вне тренировок (отдельно от tools.py из-за размера)."""

import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.mcp_server.tools import cap, period
from ai_coach.workload import workload_day, workload_series


def workload(
    conn: sqlite3.Connection, date_from: str, date_to: str, events: bool = False
) -> dict[str, Any]:
    """Нагрузка вне тренировок по дням: часы встреч (work/personal/hobby/rest, всего и после 19:00),
    all_day_work, weekend, счётчики туду и груминга, часы экрана screen_* (только числа, без
    названий приложений и окон). events=true — только на один день
    (date_from = date_to): ещё и события с названиями."""
    period(date_from, date_to)
    if events:
        if date_from != date_to:
            raise ToolError("events=true только на один день: date_from = date_to.")
        return cap([workload_day(conn, date_from, True)])
    return cap(workload_series(conn, date_from, date_to), newest=True)
