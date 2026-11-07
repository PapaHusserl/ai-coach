"""CalendarWriter.move: перенос на подмене EventKit (macOS не нужен)."""

import sys
from unittest.mock import MagicMock

import pytest

from ai_coach.agenda import calendar_write
from ai_coach.agenda.calendar_write import CalendarWriter
from ai_coach.workload.calendar_eventkit import CalendarError

THIS_EVENT, FUTURE_EVENTS = 30, 40


@pytest.fixture
def kit(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    event_kit = MagicMock()
    event_kit.EKSpanThisEvent = THIS_EVENT
    event_kit.EKSpanFutureEvents = FUTURE_EVENTS
    calendar = MagicMock()
    calendar.title.return_value = "Coach"
    calendar.calendarIdentifier.return_value = "cal-coach"
    calendar.allowsContentModifications.return_value = True
    store = event_kit.EKEventStore.alloc.return_value.init.return_value
    store.calendarsForEntityType_.return_value = [calendar]
    store.saveEvent_span_commit_error_.return_value = (True, None)
    item = MagicMock()
    item.calendar.return_value.calendarIdentifier.return_value = "cal-coach"
    store.eventWithIdentifier_.return_value = item
    monkeypatch.setitem(sys.modules, "EventKit", event_kit)
    monkeypatch.setitem(sys.modules, "Foundation", MagicMock())
    monkeypatch.setattr(calendar_write, "_request_access", lambda store: (True, None))
    monkeypatch.setattr(calendar_write, "_ns_date", lambda foundation, moment: moment)
    return event_kit


def store_of(kit: MagicMock) -> MagicMock:
    return kit.EKEventStore.alloc.return_value.init.return_value


def test_move_sets_new_times_and_saves_with_this_span(kit: MagicMock) -> None:
    CalendarWriter("Coach").move("u1", "2026-11-09T15:30:00", "2026-11-09T17:30:00")
    store = store_of(kit)
    store.eventWithIdentifier_.assert_called_once_with("u1")
    item = store.eventWithIdentifier_.return_value
    assert item.setStartDate_.call_args.args[0].isoformat() == "2026-11-09T15:30:00"
    assert item.setEndDate_.call_args.args[0].isoformat() == "2026-11-09T17:30:00"
    args = store.saveEvent_span_commit_error_.call_args.args
    assert (args[0], args[1]) == (item, THIS_EVENT)


def test_move_foreign_calendar_is_error_and_not_saved(kit: MagicMock) -> None:
    store = store_of(kit)
    item = store.eventWithIdentifier_.return_value
    item.calendar.return_value.calendarIdentifier.return_value = "other"
    with pytest.raises(CalendarError, match="не в календаре коуча"):
        CalendarWriter("Coach").move("u1", "2026-11-09T15:30:00", "2026-11-09T17:30:00")
    store.saveEvent_span_commit_error_.assert_not_called()


def test_move_missing_event_is_error(kit: MagicMock) -> None:
    store_of(kit).eventWithIdentifier_.return_value = None
    with pytest.raises(CalendarError, match="нет в календаре"):
        CalendarWriter("Coach").move("u1", "2026-11-09T15:30:00", "2026-11-09T17:30:00")


def test_move_save_failure_is_calendar_error(kit: MagicMock) -> None:
    store_of(kit).saveEvent_span_commit_error_.return_value = (False, "сбой")
    with pytest.raises(CalendarError, match="не перенёс"):
        CalendarWriter("Coach").move("u1", "2026-11-09T15:30:00", "2026-11-09T17:30:00")
