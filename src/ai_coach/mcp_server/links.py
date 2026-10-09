"""Инструмент MCP: ссылка на страницу-плеер с тренировкой (отдельно от tools.py из-за размера)."""

import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.store.plans import get_planned_workout
from ai_coach.workouts import workout_link_url


def workout_link(
    conn: sqlite3.Connection, workout_id: int, time: str | None = None
) -> dict[str, Any]:
    """Ссылка на страницу-плеер с тренировкой плана (для телефона без часов). time - HH:MM."""
    row = get_planned_workout(conn, workout_id)
    try:
        return workout_link_url(row, workout_id, time)
    except ValueError as e:
        raise ToolError(str(e)) from None
