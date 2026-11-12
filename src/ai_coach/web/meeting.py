"""Чужие события Календаря в пульте (шаг П5): карточка с описанием и правом записи живьём и
правка/удаление одного вхождения. Календарь правится первым, строка базы - после него (как
move_event). Тренерские события (uid из coach_events) и встречи с участниками - только просмотр."""

import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach.agenda.calendar_edit import ForeignEditor, ForeignWriter
from ai_coach.store.agenda import own_uids
from ai_coach.store.workload import (
    delete_calendar_event,
    get_calendar_event,
    update_calendar_event,
)
from ai_coach.web.day import recurring
from ai_coach.web.errors import MarkError, NoEvent
from ai_coach.web.plan import MAX_ID
from ai_coach.workload import CalendarError

MEETING_ACTIONS = ("update", "remove")
VALUE_KEYS = ("title", "note", "start_at", "end_at")
MAX_SPAN = timedelta(hours=24)


def default_editor() -> ForeignEditor:
    return ForeignWriter()


def _row(conn: sqlite3.Connection, event_id: Any) -> dict[str, Any]:
    if isinstance(event_id, bool) or not isinstance(event_id, int) or abs(event_id) > MAX_ID:
        raise MarkError("id: нужен номер встречи.")
    row = get_calendar_event(conn, event_id)
    if row is None:
        raise NoEvent("Встречи нет — обнови синк.")
    return row


def _refusal(conn: sqlite3.Connection, row: dict[str, Any]) -> str | None:
    """Почему строку нельзя править по снимку; None - можно."""
    if row["uid"] in own_uids(conn):
        return "событие тренера"
    if row["my_status"] is not None:
        return "встреча с участниками"
    return None


def meeting_view(
    conn: sqlite3.Connection,
    day: date,
    now: datetime,
    query: dict[str, list[str]],
    editor_factory: Callable[[], ForeignEditor] = default_editor,
) -> dict[str, Any]:
    """GET /api/meeting?id=: карточка встречи; note и право записи - живьём из календаря
    (day, now не нужны). Календарь недоступен - окно открывается: note None, причина - текстом."""
    try:
        event_id = int(query["id"][0])
    except (KeyError, ValueError):
        raise MarkError("id: нужен номер встречи.") from None
    row = _row(conn, event_id)
    reason = _refusal(conn, row)
    note = None
    try:
        editor = editor_factory()
        note = editor.note(row["uid"], row["start_at"])
        if reason is None and not editor.writable(row["uid"], row["start_at"]):
            reason = "календарь только для чтения"
    except CalendarError as error:
        note = None
        reason = reason or str(error)
    return {
        "id": row["id"],
        "calendar": row["calendar"],
        "title": row["title"],
        "note": note,
        "start_at": row["start_at"],
        "end_at": row["end_at"],
        "all_day": row["all_day"],
        "recurring": recurring(row),
        "editable": reason is None,
        "reason": reason,
    }


def _values(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Переданные title/note/start_at/end_at; конец позже начала, не дольше 24 ч."""
    values = {k: payload[k] for k in VALUE_KEYS if k in payload}
    if not values:
        raise MarkError("Нечего менять: нужны title, note, start_at или end_at.")
    if any(not isinstance(v, str) for v in values.values()):
        raise MarkError("title, note, start_at, end_at: нужны строки.")
    if "title" in values and not values["title"]:
        raise MarkError("title: нужно название.")
    if "start_at" in values or "end_at" in values:
        try:
            moments = {
                k: datetime.fromisoformat(values.get(k, row[k])) for k in ("start_at", "end_at")
            }
        except ValueError:
            raise MarkError("start_at, end_at: нужно время YYYY-MM-DDTHH:MM:SS.") from None
        if not timedelta(0) < moments["end_at"] - moments["start_at"] <= MAX_SPAN:
            raise MarkError("Конец должен быть позже начала, не больше суток.")
        for key in ("start_at", "end_at"):
            if key in values:
                values[key] = moments[key].isoformat(timespec="seconds")
    return values


def apply_meeting(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    now: datetime,
    editor_factory: Callable[[], ForeignEditor] = default_editor,
) -> dict[str, Any]:
    """POST /api/meeting: action update (title/note/start_at/end_at одного вхождения) или remove.
    Ответ update - {start_at, end_at}, remove - {}. now не нужен."""
    action = payload.get("action")
    if action not in MEETING_ACTIONS:
        raise MarkError(f"action: нужно одно из {', '.join(MEETING_ACTIONS)}.")
    row = _row(conn, payload.get("id"))
    reason = _refusal(conn, row)
    if reason == "событие тренера":
        raise MarkError("событие тренера — двигай его блок.")
    if reason:
        raise MarkError("Встреча с участниками — только просмотр.")
    try:
        if action == "remove":
            editor_factory().remove(row["uid"], row["start_at"])
            delete_calendar_event(conn, row["id"])
            return {}
        values = _values(row, payload)
        editor_factory().update(row["uid"], row["start_at"], values)
    except CalendarError as error:
        raise MarkError(str(error)) from None
    start_at = values.get("start_at", row["start_at"])
    stored = {k: v for k, v in values.items() if k != "note"}
    if "start_at" in values:
        stored["date"] = start_at[:10]
    if stored:
        update_calendar_event(conn, row["id"], stored)
    return {"start_at": start_at, "end_at": values.get("end_at", row["end_at"])}
