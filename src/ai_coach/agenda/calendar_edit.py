"""Правка чужих событий Календаря macOS через EventKit (pyobjc), по одному вхождению.

В отличие от CalendarWriter не привязан к календарю коуча: ищет вхождение по uid и началу среди
всех календарей и правит только его (EKSpanThisEvent, Р8 = 1 П5). Календарь без права записи -
CalendarError до сохранения. EventKit импортируется лениво; MCP-сервер модуль не импортирует.
"""

import importlib
from datetime import datetime, time, timedelta
from typing import Any, Protocol

from ai_coach.workload.calendar_eventkit import (
    HINT,
    CalendarError,
    _iso,  # pyright: ignore[reportPrivateUsage]
    _ns_date,  # pyright: ignore[reportPrivateUsage]
    _request_access,  # pyright: ignore[reportPrivateUsage]
)


class ForeignEditor(Protocol):
    """Что нужно пульту от правщика чужих событий: ForeignWriter или подмена в тестах."""

    def update(self, uid: str, start_at: str, values: dict[str, Any]) -> None: ...

    def remove(self, uid: str, start_at: str) -> None: ...

    def note(self, uid: str, start_at: str) -> str: ...

    def writable(self, uid: str, start_at: str) -> bool: ...


class ForeignWriter:
    """Правщик вхождений чужих событий (uid + начало ISO). Ошибка - CalendarError."""

    def _occurrence(self, uid: str, start_at: str) -> tuple[Any, Any, Any, Any]:
        """EventKit, Foundation, хранилище и вхождение с этим uid и началом."""
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
        day = datetime.combine(datetime.fromisoformat(start_at).date(), time.min)
        calendars = list(store.calendarsForEntityType_(event_kit.EKEntityTypeEvent))
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            _ns_date(foundation, day), _ns_date(foundation, day + timedelta(days=1)), calendars
        )
        for item in store.eventsMatchingPredicate_(predicate):
            if str(item.eventIdentifier()) == uid and _iso(item.startDate()) == start_at:
                return event_kit, foundation, store, item
        raise CalendarError("события нет в календаре - обнови синк.")

    def writable(self, uid: str, start_at: str) -> bool:
        return bool(self._occurrence(uid, start_at)[3].calendar().allowsContentModifications())

    def note(self, uid: str, start_at: str) -> str:
        return str(self._occurrence(uid, start_at)[3].notes() or "")

    def _checked(self, uid: str, start_at: str) -> tuple[Any, Any, Any, Any]:
        found = self._occurrence(uid, start_at)
        if not found[3].calendar().allowsContentModifications():
            raise CalendarError("календарь только для чтения.")
        return found

    def update(self, uid: str, start_at: str, values: dict[str, Any]) -> None:
        """Меняет только переданные title, note, start_at, end_at одного вхождения."""
        event_kit, foundation, store, item = self._checked(uid, start_at)
        try:
            if "title" in values:
                item.setTitle_(values["title"])
            if "note" in values:
                item.setNotes_(values["note"])
            for key, setter in (("start_at", item.setStartDate_), ("end_at", item.setEndDate_)):
                if key in values:
                    setter(_ns_date(foundation, datetime.fromisoformat(values[key])))
            ok, error = store.saveEvent_span_commit_error_(
                item, event_kit.EKSpanThisEvent, True, None
            )
            if not ok:
                raise CalendarError(f"календарь не сохранил событие: {str(error)[:120]}")
        except CalendarError:
            raise
        except Exception as e:
            raise CalendarError(f"событие не изменено: {type(e).__name__}") from None

    def remove(self, uid: str, start_at: str) -> None:
        """Снимает одно вхождение."""
        event_kit, _, store, item = self._checked(uid, start_at)
        try:
            ok, error = store.removeEvent_span_commit_error_(
                item, event_kit.EKSpanThisEvent, True, None
            )
            if not ok:
                raise CalendarError(f"календарь не снял событие: {str(error)[:120]}")
        except CalendarError:
            raise
        except Exception as e:
            raise CalendarError(f"событие не снято: {type(e).__name__}") from None
