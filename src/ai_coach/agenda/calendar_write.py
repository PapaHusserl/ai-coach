"""Запись событий тренера в календарь macOS через EventKit (pyobjc).

Пишет и снимает только в календаре коуча (точное название из workload.toml [coach] calendar):
чужие календари и чужие события недостижимы. EventKit импортируется лениво, внутри вызовов.
MCP-сервер этот модуль не импортирует.
"""

import importlib
from datetime import datetime
from typing import Any

from ai_coach.workload.calendar_eventkit import (
    HINT,
    CalendarError,
    _ns_date,  # pyright: ignore[reportPrivateUsage]
    _request_access,  # pyright: ignore[reportPrivateUsage]
)

SECONDS_IN_MINUTE = 60


class CalendarWriter:
    """Писатель календаря коуча (в тестах подменяется объектом с такими же write и remove).
    Ошибка - CalendarError."""

    def __init__(self, calendar: str) -> None:
        self.calendar = calendar.strip()

    def _open(self) -> tuple[Any, Any, Any, Any]:
        """EventKit, Foundation, хранилище и календарь коуча (ровно один, доступный для записи)."""
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
        found = [
            c
            for c in store.calendarsForEntityType_(event_kit.EKEntityTypeEvent)
            if str(c.title()).strip() == self.calendar
        ]
        if len(found) != 1:
            raise CalendarError(
                f"Календарей коуча с таким названием найдено {len(found)}, нужен один."
            )
        if not found[0].allowsContentModifications():
            raise CalendarError("В календарь коуча нельзя писать.")
        return event_kit, foundation, store, found[0]

    def write(self, event: dict[str, Any]) -> str:
        """Пишет событие (строка coach_events) в календарь коуча, возвращает eventIdentifier."""
        event_kit, foundation, store, calendar = self._open()
        try:
            item = event_kit.EKEvent.eventWithEventStore_(store)
            item.setCalendar_(calendar)
            item.setTitle_(event["title"])
            item.setNotes_(event["note"])
            item.setAllDay_(bool(event["all_day"]))
            item.setStartDate_(_ns_date(foundation, datetime.fromisoformat(event["start_at"])))
            item.setEndDate_(_ns_date(foundation, datetime.fromisoformat(event["end_at"])))
            item.setTimeZone_(foundation.NSTimeZone.localTimeZone())
            if event["alarm_min"] is not None:
                offset = -event["alarm_min"] * SECONDS_IN_MINUTE
                item.addAlarm_(event_kit.EKAlarm.alarmWithRelativeOffset_(offset))
            if event["repeat"] == "daily":
                rule = event_kit.EKRecurrenceRule.alloc()
                rule = rule.initRecurrenceWithFrequency_interval_end_(
                    event_kit.EKRecurrenceFrequencyDaily, 1, None
                )
                item.addRecurrenceRule_(rule)
            span = event_kit.EKSpanFutureEvents if event["repeat"] else event_kit.EKSpanThisEvent
            ok, error = store.saveEvent_span_commit_error_(item, span, True, None)
            if not ok:
                raise CalendarError(f"календарь не сохранил событие: {str(error)[:120]}")
            return str(item.eventIdentifier())
        except CalendarError:
            raise
        except Exception as e:
            raise CalendarError(f"событие не записано: {type(e).__name__}") from None

    def remove(self, uid: str, future: bool = False) -> None:
        """Снимает событие по eventIdentifier, только если оно в календаре коуча; future -
        и все будущие вхождения (повторяющееся)."""
        event_kit, _, store, calendar = self._open()
        try:
            item = store.eventWithIdentifier_(uid)
            if item is None:
                raise CalendarError("события нет в календаре.")
            if str(item.calendar().calendarIdentifier()) != str(calendar.calendarIdentifier()):
                raise CalendarError("событие не в календаре коуча, не трогаю.")
            span = event_kit.EKSpanFutureEvents if future else event_kit.EKSpanThisEvent
            ok, error = store.removeEvent_span_commit_error_(item, span, True, None)
            if not ok:
                raise CalendarError(f"календарь не снял событие: {str(error)[:120]}")
        except CalendarError:
            raise
        except Exception as e:
            raise CalendarError(f"событие не снято: {type(e).__name__}") from None
