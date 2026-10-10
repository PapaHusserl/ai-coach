"""Чтение календаря macOS через EventKit (pyobjc). Только чтение, без save/remove.

EventKit импортируется лениво, внутри read: пакет импортируется и без него (тесты, не macOS).
"""

import importlib
import threading
from datetime import date, datetime, time, timedelta
from typing import Any, Protocol

ACCESS_TIMEOUT = 120
STATUSES = {0: "none", 1: "confirmed", 2: "tentative", 3: "cancelled"}
PARTICIPANT = {
    0: "unknown",
    1: "pending",
    2: "accepted",
    3: "declined",
    4: "tentative",
    5: "delegated",
    6: "completed",
    7: "in_process",
}
HINT = (
    "Системные настройки -> Конфиденциальность и безопасность -> Календари: "
    "разреши доступ терминалу, из которого запускаешь coach sync."
)


class CalendarError(Exception):
    """Календарь не прочитан: нет pyobjc, нет доступа или EventKit вернул ошибку."""


class EventReader(Protocol):
    """Что нужно sync от читателя календаря: CalendarReader или его подмена в тестах."""

    def read(self, date_from: date, date_to: date) -> list[dict[str, Any]]: ...


def _iso(ns_date: Any) -> str:
    moment = datetime.fromtimestamp(ns_date.timeIntervalSince1970())
    return moment.isoformat(timespec="seconds")


def _ns_date(foundation: Any, moment: datetime) -> Any:
    return foundation.NSDate.dateWithTimeIntervalSince1970_(moment.timestamp())


def _request_access(store: Any) -> tuple[bool, str]:
    """Запрос полного доступа к событиям (macOS 14+; старше - обычный запрос)."""
    done = threading.Event()
    box: dict[str, Any] = {}

    def handler(granted: Any, error: Any) -> None:
        box["granted"] = bool(granted)
        box["error"] = "" if error is None else str(error)
        done.set()

    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(handler)
    else:
        store.requestAccessToEntityType_completion_(0, handler)
    if not done.wait(ACCESS_TIMEOUT):
        return False, "нет ответа на запрос доступа"
    return box["granted"], box["error"]


def _my_status(event: Any) -> str | None:
    attendees: list[Any] = list(event.attendees() or [])
    for attendee in attendees:
        if attendee.isCurrentUser():
            return PARTICIPANT.get(int(attendee.participantStatus()), "unknown")
    return None


def _row(event: Any) -> dict[str, Any]:
    zone = event.timeZone()
    title = event.title()
    return {
        "uid": str(event.eventIdentifier() or event.calendarItemIdentifier()),
        "calendar": str(event.calendar().title()),
        "title": str(title) if title else None,
        "start_at": _iso(event.startDate()),
        "end_at": _iso(event.endDate()),
        "all_day": bool(event.isAllDay()),
        "status": STATUSES.get(int(event.status()), "none"),
        "my_status": _my_status(event),
        "raw_json": {
            "availability": int(event.availability()),
            "recurring": bool(event.hasRecurrenceRules()),
            "detached": bool(event.isDetached()),
            "time_zone": str(zone.name()) if zone else None,
        },
    }


class CalendarReader:
    """Читатель календаря macOS (в тестах подменяется объектом с таким же read). read возвращает
    события с днём начала в date_from..date_to: dict с uid, calendar, title, start_at, end_at
    (местное время ISO без пояса), all_day, status, my_status, raw_json (без участников и
    адресов). Ошибка - CalendarError."""

    def read(self, date_from: date, date_to: date) -> list[dict[str, Any]]:
        try:
            event_kit = importlib.import_module("EventKit")
            foundation = importlib.import_module("Foundation")
        except ImportError:
            raise CalendarError(
                "EventKit недоступен: нужен macOS и pyobjc-framework-EventKit (uv sync)."
            ) from None
        store = event_kit.EKEventStore.alloc().init()
        granted, error = _request_access(store)
        if not granted:
            raise CalendarError(f"Нет доступа к календарю{': ' + error if error else ''}. {HINT}")
        try:
            return self._events(event_kit, foundation, store, date_from, date_to)
        except Exception as e:
            raise CalendarError(f"календарь не прочитан: {type(e).__name__}") from None

    def _events(
        self, event_kit: Any, foundation: Any, store: Any, date_from: date, date_to: date
    ) -> list[dict[str, Any]]:
        start = _ns_date(foundation, datetime.combine(date_from, time.min))
        end = _ns_date(foundation, datetime.combine(date_to + timedelta(days=1), time.min))
        calendars = list(store.calendarsForEntityType_(event_kit.EKEntityTypeEvent))
        found = store.eventsMatchingPredicate_(
            store.predicateForEventsWithStartDate_endDate_calendars_(start, end, calendars)
        )
        rows = [_row(event) for event in found]
        return [
            r for r in rows if date_from.isoformat() <= r["start_at"][:10] <= date_to.isoformat()
        ]
