"""Инструмент MCP: ссылка на страницу-плеер с тренировкой (отдельно от tools.py из-за размера)."""

import io
import json
import sqlite3
from typing import Any

import segno
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.utilities.types import Image
from mcp.types import TextContent

from ai_coach.store.plans import get_planned_workout
from ai_coach.workouts import workout_link_url


def workout_link(conn: sqlite3.Connection, workout_id: int, time: str | None = None) -> Any:
    """Ссылка на страницу-плеер с тренировкой плана (для телефона без часов). time - HH:MM.

    Возврат Any и явный TextContent не случайны: FastMCP не сериализует [dict, Image] в
    структурированный ответ. Заменишь TextContent на dict - картинка пропадёт."""
    row = get_planned_workout(conn, workout_id)
    try:
        link = workout_link_url(row, workout_id, time)
    except ValueError as e:
        raise ToolError(str(e)) from None
    buf = io.BytesIO()
    segno.make(link["url"], error="m").save(buf, kind="png", scale=6, border=2)
    text = TextContent(type="text", text=json.dumps(link, ensure_ascii=False))
    return [text, Image(data=buf.getvalue(), format="png")]
