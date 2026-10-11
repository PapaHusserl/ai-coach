"""Инструменты MCP: события тренера в календаре (отдельно от tools.py из-за размера).

Пишут только черновики; в календарь события кладёт пользователь командой coach event write.
"""

import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.agenda import AgendaError, agenda_rows, cancel_event, create_draft
from ai_coach.mcp_server.tools import cap, period


def create_draft_event(
    conn: sqlite3.Connection,
    kind: str,
    title: str,
    start_at: str,
    end_at: str,
    note: str | None = None,
    category: str | None = None,
    alarm_min: int | None = None,
    repeat: str | None = None,
    workout_id: int | None = None,
    practice_id: int | None = None,
    all_day: bool = False,
) -> dict[str, Any]:
    """Черновик события календаря (status=draft). kind: training / practice / rest / sleep /
    checkin / task; start_at, end_at - местное время YYYY-MM-DDTHH:MM; день начала от 30 дней
    назад до 14 вперёд; не длиннее 24 часов. category (work / personal / hobby / rest) - для
    нагрузки, у rest и sleep по умолчанию rest, у task задаётся явно, у остальных не задаётся.
    alarm_min - за сколько минут напомнить. repeat=daily - только у checkin и один на всех."""
    values = {
        "kind": kind,
        "title": title,
        "start_at": start_at,
        "end_at": end_at,
        "note": note,
        "category": category,
        "alarm_min": alarm_min,
        "repeat": repeat,
        "workout_id": workout_id,
        "practice_id": practice_id,
        "all_day": all_day,
    }
    try:
        with conn:
            return {"draft_id": create_draft(conn, values)}
    except AgendaError as e:
        raise ToolError(str(e)) from None


def cancel_draft_event(conn: sqlite3.Connection, event_id: int) -> dict[str, Any]:
    """Отмена черновика события (draft -> cancelled). Записанные в календарь не трогает."""
    try:
        with conn:
            cancel_event(conn, event_id)
    except AgendaError as e:
        raise ToolError(str(e)) from None
    return {"cancelled_id": event_id}


def agenda(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, Any]:
    """События тренера (черновики и записанные в календарь) с днём начала в периоде, плюс
    активный повторяющийся чек-ин: id, kind, title, date, start_at, end_at, all_day, note,
    category, alarm_min, repeat, workout_id, practice_id, status."""
    period(date_from, date_to)
    return cap(agenda_rows(conn, date_from, date_to))
