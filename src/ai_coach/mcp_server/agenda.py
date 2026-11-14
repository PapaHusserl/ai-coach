"""Инструменты MCP: события тренера в календаре (отдельно от tools.py из-за размера).

Пишут только черновики (в том числе create_day_plan - план дня); в календарь события кладёт
пользователь командой coach event write.
"""

import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.agenda import AgendaError, agenda_rows, cancel_event, create_draft, move_draft
from ai_coach.agenda.day_plan import create_day_plan as build_day_plan
from ai_coach.agenda.service import SURVEYS, shifted
from ai_coach.mcp_server import tools
from ai_coach.mcp_server.tools import cap, parse_day, period
from ai_coach.store.agenda import get_event


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
    survey: str | None = None,
) -> dict[str, Any]:
    """Черновик события календаря (status=draft). kind: training / practice / rest / sleep /
    checkin / task / focus / meal; start_at, end_at - местное время YYYY-MM-DDTHH:MM; день
    начала от 30 дней назад до 14 вперёд; не длиннее 24 часов. category (work / personal /
    hobby / rest) - для нагрузки, у rest и sleep по умолчанию rest, у task обязательна, у
    остальных не задаётся. alarm_min - за сколько минут напомнить. repeat=daily / weekly /
    biweekly - только у checkin, не два на одно время суток с пересечением по дням. survey -
    опросник чек-ина, у checkin обязателен: evening (анкета вечера) / feel (самочувствие) /
    focus (оценка фокуса) / none (без анкеты: Сделал / Пропустил); у остальных не задаётся."""
    if kind == "checkin" and survey is None:
        raise ToolError(f"У чек-ина нужен survey: {list(SURVEYS)}.")
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
        "survey": survey,
    }
    try:
        with conn:
            return {"draft_id": create_draft(conn, values)}
    except AgendaError as e:
        raise ToolError(str(e)) from None


def create_day_plan(
    conn: sqlite3.Connection,
    date: str,
    tasks: list[dict[str, Any]] | None = None,
    training_at: str | None = None,
    day_start: str | None = None,
    day_end: str | None = None,
    breakfast_at: str | None = None,
    snack_at: str | None = None,
    dinner_at: str | None = None,
) -> dict[str, Any]:
    """План дня черновиками (status=draft) за один вызов: свободные окна дня минус занятое
    (календарь и события тренера) - тренировка, готовка и завтрак, перекус, отдых,
    готовка и ужин, инбокс 2x20 мин после завтрака и отдыха (будни), задачи (только названные
    пользователем), фокус. Если на день уже есть focus/meal - ничего не создаёт, ответ
    already_planned с id.
    При сигнале сна, сигнале «возможно, заболеваешь» или низком WHO-5 фокус-блоков меньше,
    причина в skipped."""
    try:
        return build_day_plan(
            conn,
            parse_day(date),
            tasks,
            training_at=training_at,
            day_start=day_start,
            day_end=day_end,
            breakfast_at=breakfast_at,
            snack_at=snack_at,
            dinner_at=dinner_at,
            now=tools.now(),
        )
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


def move_draft_event(conn: sqlite3.Connection, event_id: int, start_at: str) -> dict[str, Any]:
    """Перенос события на новое начало (длительность та же). Черновик (draft) двигается сразу:
    ответ start_at, end_at, date. Записанное в календарь (written) MCP не трогает: ответ -
    command (готовая команда coach event move, её выполняет пользователь; время сначала
    проверяется, в базу не пишет). Повторяющееся не двигается."""
    row = get_event(conn, event_id)
    try:
        if row is not None and row["status"] == "written":
            shifted(conn, row, start_at, None)
            return {"command": f"uv run coach event move {event_id} {start_at}"}
        with conn:
            return move_draft(conn, event_id, start_at)
    except AgendaError as e:
        raise ToolError(str(e)) from None


def agenda(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, Any]:
    """События тренера (черновики и записанные в календарь) с днём начала в периоде, плюс
    активный повторяющийся чек-ин: id, kind, title, date, start_at, end_at, all_day, note,
    category, survey (опросник чек-ина или null), alarm_min, repeat, workout_id, practice_id,
    status."""
    period(date_from, date_to)
    return cap(agenda_rows(conn, date_from, date_to))
