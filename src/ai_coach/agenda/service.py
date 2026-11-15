"""События тренера в календаре: проверка черновика и переходы статусов coach_events.

draft -> written (write_event, запись в календарь) -> removed (remove_event); draft -> cancelled
(cancel_event). Порядок записи и снятия: сначала календарь, потом база; сбой календаря базу не
меняет, сбой базы после календаря - в сообщении uid.
Commit делает вызывающий код, кроме write_event и remove_event: они коммитят
сами, в том же try, что даёт сообщение с uid.
"""

import sqlite3
from datetime import date, datetime
from typing import Any, Protocol

from ai_coach.agenda.draft import AgendaError, parse_moment, validate_draft
from ai_coach.store.agenda import (
    ACTIVE,
    active_repeats,
    add_event,
    get_event,
    list_events,
    update_event,
)

HIDDEN = ("calendar_uid", "created_at", "written_at", "removed_at", "removed_by")


class EventWriter(Protocol):
    """Что нужно сервису от писателя календаря: CalendarWriter или его подмена в тестах."""

    def write(self, event: dict[str, Any]) -> str: ...

    def remove(self, uid: str, future: bool = False) -> None: ...

    def move(self, uid: str, start_at: str, end_at: str) -> None: ...


def _stamp() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def create_draft(
    conn: sqlite3.Connection, values: dict[str, Any], today: date | None = None
) -> int:
    """Проверяет и сохраняет черновик (status=draft), возвращает id."""
    checked = validate_draft(conn, values, today)
    return add_event(conn, {**checked, "status": "draft", "created_at": _stamp()})


def _get(conn: sqlite3.Connection, event_id: int) -> dict[str, Any]:
    row = get_event(conn, event_id)
    if row is None:
        raise AgendaError(f"События {event_id} нет.")
    return row


def cancel_event(conn: sqlite3.Connection, event_id: int) -> None:
    """draft -> cancelled; в календарь не ходит."""
    row = _get(conn, event_id)
    if row["status"] != "draft":
        raise AgendaError(
            f"Отменить можно только черновик, а событие {event_id} — {row['status']}."
        )
    update_event(conn, event_id, {"status": "cancelled"})


def write_event(conn: sqlite3.Connection, event_id: int, writer: EventWriter) -> str:
    """draft -> written: событие пишется в календарь, uid и статус - в базу. Сбой календаря
    базу не меняет; сбой базы после записи - AgendaError с uid. Возвращает uid."""
    row = _get(conn, event_id)
    if row["status"] != "draft":
        raise AgendaError(
            f"Записать можно только черновик, а событие {event_id} — {row['status']}."
        )
    uid = writer.write(row)
    values = {"status": "written", "calendar_uid": uid, "written_at": _stamp()}
    try:
        update_event(conn, event_id, values)
        conn.commit()
    except sqlite3.Error as e:
        raise AgendaError(
            f"Событие {event_id} записано в календарь (uid={uid}), но база не обновлена: {e}"
        ) from e
    return uid


def remove_event(conn: sqlite3.Connection, event_id: int, writer: EventWriter) -> None:
    """written -> removed (removed_by=cli): событие снимается из календаря (у повторяющегося -
    все будущие вхождения). Сбой календаря базу не меняет; сбой базы после снятия - AgendaError
    с uid."""
    row = _get(conn, event_id)
    if row["status"] != "written":
        raise AgendaError(f"Снять можно записанное событие, а {event_id} — {row['status']}.")
    uid = row["calendar_uid"]
    writer.remove(uid, row["repeat"] is not None)
    values = {"status": "removed", "removed_at": _stamp(), "removed_by": "cli"}
    try:
        update_event(conn, event_id, values)
        conn.commit()
    except sqlite3.Error as e:
        raise AgendaError(
            f"Событие {event_id} снято из календаря (uid={uid}), но база не обновлена: {e}"
        ) from e


def shifted(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    start_at: str,
    today: date | None,
    end_at: str | None = None,
) -> dict[str, Any]:
    """Проверенные start_at, end_at, date события при новом начале; без end_at длительность
    сохраняется, с end_at - меняется. Повторяющееся не двигается."""
    if row["repeat"] is not None:
        raise AgendaError(
            f"Событие {row['id']} повторяющееся: снять (event remove) и поставить заново."
        )
    start = parse_moment(start_at, "start_at")
    if end_at is None:
        length = datetime.fromisoformat(row["end_at"]) - datetime.fromisoformat(row["start_at"])
        end = start + length
    else:
        end = parse_moment(end_at, "end_at")
    values = {**row, "start_at": start.isoformat(), "end_at": end.isoformat()}
    checked = validate_draft(conn, values, today)
    return {k: checked[k] for k in ("start_at", "end_at", "date")}


def move_draft(
    conn: sqlite3.Connection,
    event_id: int,
    start_at: str,
    today: date | None = None,
    end_at: str | None = None,
) -> dict[str, Any]:
    """Двигает черновик на новое начало (длительность та же, с end_at - новая), возвращает
    start_at, end_at, date."""
    row = _get(conn, event_id)
    if row["status"] != "draft":
        raise AgendaError(f"Это не черновик: событие {event_id} — {row['status']}.")
    values = shifted(conn, row, start_at, today, end_at)
    update_event(conn, event_id, values)
    return values


def move_event(
    conn: sqlite3.Connection,
    event_id: int,
    start_at: str,
    writer: EventWriter,
    today: date | None = None,
    end_at: str | None = None,
) -> dict[str, Any]:
    """Двигает записанное событие (сначала календарь, потом база) на новое начало, длительность
    та же (с end_at - новая). Сбой календаря базу не меняет; сбой базы после переноса -
    AgendaError с uid. Возвращает start_at, end_at, date. Черновик двигает move_draft."""
    row = _get(conn, event_id)
    if row["status"] != "written":
        raise AgendaError(
            f"Двигать можно записанное, а {event_id} — {row['status']} (черновик — move_draft)."
        )
    values = shifted(conn, row, start_at, today, end_at)
    uid = row["calendar_uid"]
    writer.move(uid, values["start_at"], values["end_at"])
    try:
        update_event(conn, event_id, values)
        conn.commit()
    except sqlite3.Error as e:
        raise AgendaError(
            f"Событие {event_id} перенесено в календаре (uid={uid}), но база не обновлена: {e}"
        ) from e
    return values


def agenda_rows(conn: sqlite3.Connection, date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Живые события (draft, written) с датой начала date_from..date_to и, если начато раньше,
    активные повторяющиеся. Без служебных полей (uid календаря, времена записи и снятия)."""
    rows = list_events(conn, date_from, date_to, ACTIVE)
    earlier = [row for row in active_repeats(conn) if row["date"] < date_from]
    rows[:0] = earlier
    return [{k: v for k, v in row.items() if k not in HIDDEN} for row in rows]
