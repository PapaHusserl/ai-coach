"""События тренера в календаре: проверка черновика и переходы статусов coach_events.

draft -> written (write_event, запись в календарь) -> removed (remove_event); draft -> cancelled
(cancel_event). Порядок записи и снятия: сначала календарь, потом база; сбой календаря базу не
меняет, сбой базы после календаря - в сообщении uid.
Commit делает вызывающий код, кроме write_event и remove_event: они коммитят
сами, в том же try, что даёт сообщение с uid.
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from ai_coach.store.agenda import (
    ACTIVE,
    active_repeats,
    add_event,
    get_event,
    list_events,
    update_event,
)
from ai_coach.store.plans import get_planned_workout
from ai_coach.store.practices import get_practice
from ai_coach.workload.config import CATEGORIES

KINDS = ("training", "practice", "rest", "sleep", "checkin", "task", "focus", "meal")
REST_KINDS = ("rest", "sleep")
REPEATS = ("daily",)
PAST_DAYS = 30
AHEAD_DAYS = 14
MAX_HOURS = 24
MAX_ALARM_MIN = 1440
HIDDEN = ("calendar_uid", "created_at", "written_at", "removed_at", "removed_by")


class AgendaError(Exception):
    """Событие нельзя так создавать или менять. Текст - для консоли и MCP."""


class EventWriter(Protocol):
    """Что нужно сервису от писателя календаря: CalendarWriter или его подмена в тестах."""

    def write(self, event: dict[str, Any]) -> str: ...

    def remove(self, uid: str, future: bool = False) -> None: ...


def _moment(value: Any, name: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise AgendaError(f"{name}: нужно YYYY-MM-DDTHH:MM, получено: {value!r}") from None
    if moment.tzinfo is not None:
        raise AgendaError(f"{name}: время местное, без часового пояса.")
    return moment


def _category(kind: str, given: str | None) -> str | None:
    """Категория для нагрузки: у отдыха и сна по умолчанию rest; у задачи обязательна;
    у тренировки, практики и чек-ина нет."""
    if given is not None and given not in CATEGORIES:
        raise AgendaError(f"category должна быть из {list(CATEGORIES)}, получено: {given!r}")
    if kind in REST_KINDS:
        return given or "rest"
    if kind == "task":
        if given is None:
            raise AgendaError("У задачи нужна категория: work, hobby или personal.")
        return given
    if given is not None:
        raise AgendaError(f"category только у task, rest и sleep, а kind={kind}.")
    return None


def _links(conn: sqlite3.Connection, workout_id: Any, practice_id: Any) -> None:
    if workout_id is not None:
        workout = get_planned_workout(conn, workout_id)
        if workout is None or workout["status"] == "cancelled":
            raise AgendaError(f"Тренировки {workout_id} нет или она отменена.")
    if practice_id is not None and get_practice(conn, practice_id) is None:
        raise AgendaError(f"Практики {practice_id} нет.")


def validate_draft(
    conn: sqlite3.Connection, values: dict[str, Any], today: date | None = None
) -> dict[str, Any]:
    """Проверенные значения черновика для add_event (без status, created_at). values: kind, title,
    start_at, end_at (местное время ISO); не обязательно all_day, note, category, alarm_min,
    repeat, workout_id, practice_id. Начало раньше конца, событие не длиннее MAX_HOURS, день
    начала от PAST_DAYS назад до AHEAD_DAYS вперёд; repeat только daily у checkin и не два
    активных на одно время суток; тренировка и практика живы; категория по умолчанию только у
    rest и sleep (rest)."""
    today = today or date.today()
    kind = values["kind"]
    if kind not in KINDS:
        raise AgendaError(f"kind должен быть из {list(KINDS)}, получено: {kind!r}")
    title = (values.get("title") or "").strip()
    if not title:
        raise AgendaError("Название события пустое.")
    start = _moment(values["start_at"], "start_at")
    end = _moment(values["end_at"], "end_at")
    if end <= start:
        raise AgendaError("Начало события должно быть раньше конца.")
    if end - start > timedelta(hours=MAX_HOURS):
        raise AgendaError(f"Событие не длиннее {MAX_HOURS} часов.")
    if not today - timedelta(days=PAST_DAYS) <= start.date() <= today + timedelta(days=AHEAD_DAYS):
        raise AgendaError(f"День начала от {PAST_DAYS} дней назад до {AHEAD_DAYS} дней вперёд.")
    alarm = values.get("alarm_min")
    if alarm is not None and not 0 <= alarm <= MAX_ALARM_MIN:
        raise AgendaError(f"alarm_min от 0 до {MAX_ALARM_MIN} минут, получено: {alarm}")
    repeat = values.get("repeat")
    if repeat is not None:
        if repeat not in REPEATS or kind != "checkin":
            raise AgendaError(f"repeat только {list(REPEATS)} и только у checkin.")
        clock = start.isoformat(timespec="seconds")[11:16]
        if any(row["start_at"][11:16] == clock for row in active_repeats(conn)):
            raise AgendaError(
                f"Повторяющийся чек-ин на {clock} уже есть (черновик или в календаре)."
            )
    _links(conn, values.get("workout_id"), values.get("practice_id"))
    note = (values.get("note") or "").strip() or None
    return {
        "kind": kind,
        "title": title,
        "date": start.date().isoformat(),
        "start_at": start.isoformat(timespec="seconds"),
        "end_at": end.isoformat(timespec="seconds"),
        "all_day": int(bool(values.get("all_day"))),
        "note": note,
        "category": _category(kind, values.get("category")),
        "alarm_min": alarm,
        "repeat": repeat,
        "workout_id": values.get("workout_id"),
        "practice_id": values.get("practice_id"),
    }


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


def agenda_rows(conn: sqlite3.Connection, date_from: str, date_to: str) -> list[dict[str, Any]]:
    """Живые события (draft, written) с датой начала date_from..date_to и, если начато раньше,
    активные повторяющиеся. Без служебных полей (uid календаря, времена записи и снятия)."""
    rows = list_events(conn, date_from, date_to, ACTIVE)
    earlier = [row for row in active_repeats(conn) if row["date"] < date_from]
    rows[:0] = earlier
    return [{k: v for k, v in row.items() if k not in HIDDEN} for row in rows]
