"""Правка плана из пульта: перенос, длительность и новый пункт (шаг П4). Те же функции agenda,
что у `coach event move` и `coach event write`; календарь коуча - через писатель."""

import sqlite3
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ai_coach.agenda.calendar_write import CalendarWriter
from ai_coach.agenda.service import (
    AgendaError,
    EventWriter,
    create_draft,
    move_draft,
    move_event,
    write_event,
)
from ai_coach.store.agenda import get_event
from ai_coach.web.errors import MarkError, NoEvent
from ai_coach.workload import CalendarError, WorkloadConfigError, load_config

PULT_KINDS = ("task", "focus", "rest", "meal")
MAX_ID = 2**63 - 1  # предел INTEGER sqlite
CREATE_FIELDS = ("kind", "title", "start_at", "end_at", "category")


def default_writer() -> EventWriter:
    """Писатель календаря коуча из конфига; имя не задано - WorkloadConfigError."""
    name = load_config().coach_calendar
    if name is None:
        raise WorkloadConfigError(
            "Календарь коуча не задан: добавь [coach] calendar в workload.toml."
        )
    return CalendarWriter(name)


def _move(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    now: datetime,
    writer_factory: Callable[[], EventWriter],
    resize: bool,
) -> dict[str, Any]:
    event_id = payload.get("id")
    if isinstance(event_id, bool) or not isinstance(event_id, int) or abs(event_id) > MAX_ID:
        raise MarkError("id: нужен номер события.")
    row = get_event(conn, event_id)
    if row is None:
        raise NoEvent(f"События {event_id} нет.")
    end_at = payload.get("end_at") if resize else None
    start_at = row["start_at"] if resize else payload.get("start_at", "")
    if resize and end_at is None:
        raise MarkError("end_at: нужно время конца.")
    if row["status"] == "written":
        return move_event(conn, row["id"], start_at, writer_factory(), now.date(), end_at=end_at)
    return move_draft(conn, row["id"], start_at, now.date(), end_at=end_at)


def _create(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    now: datetime,
    writer_factory: Callable[[], EventWriter],
) -> dict[str, Any]:
    if payload.get("kind") not in PULT_KINDS:
        raise MarkError("kind: задача, фокус, отдых или еда.")
    if not isinstance(payload.get("title", ""), str):
        raise MarkError("title: нужна строка.")
    values = {k: payload.get(k) for k in CREATE_FIELDS}
    event_id = create_draft(conn, values, now.date())
    conn.commit()
    try:
        write_event(conn, event_id, writer_factory())
    except (CalendarError, WorkloadConfigError) as error:
        return {"id": event_id, "status": "draft", "error": f"записан черновиком: {error}"}
    return {"id": event_id, "status": "written"}


def apply_event(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    now: datetime,
    writer_factory: Callable[[], EventWriter] = default_writer,
) -> dict[str, Any]:
    """POST /api/event: action move | resize | create. Ошибки agenda и календаря - MarkError
    текстом, нет события - NoEvent. Сбой календаря при create оставляет черновик (в ответе)."""
    action = payload.get("action")
    try:
        if action == "create":
            return _create(conn, payload, now, writer_factory)
        if action in ("move", "resize"):
            return _move(conn, payload, now, writer_factory, action == "resize")
    except (AgendaError, CalendarError, WorkloadConfigError) as error:
        raise MarkError(str(error)) from error
    raise MarkError("action: move, resize или create.")
