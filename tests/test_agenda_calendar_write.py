"""CalendarWriter.write: правило повтора и span на подмене EventKit (macOS не нужен)."""

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest
from workload_fakes import coach_event

from ai_coach.agenda import calendar_write
from ai_coach.agenda.calendar_write import CalendarWriter

DAILY, WEEKLY, THIS_EVENT, FUTURE_EVENTS = 10, 20, 30, 40


@pytest.fixture
def kit(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    event_kit = MagicMock()
    event_kit.EKRecurrenceFrequencyDaily = DAILY
    event_kit.EKRecurrenceFrequencyWeekly = WEEKLY
    event_kit.EKSpanThisEvent = THIS_EVENT
    event_kit.EKSpanFutureEvents = FUTURE_EVENTS
    calendar = MagicMock()
    calendar.title.return_value = "Coach"
    calendar.allowsContentModifications.return_value = True
    store = event_kit.EKEventStore.alloc.return_value.init.return_value
    store.calendarsForEntityType_.return_value = [calendar]
    store.saveEvent_span_commit_error_.return_value = (True, None)
    monkeypatch.setitem(sys.modules, "EventKit", event_kit)
    monkeypatch.setitem(sys.modules, "Foundation", MagicMock())
    monkeypatch.setattr(calendar_write, "_request_access", lambda store: (True, None))
    monkeypatch.setattr(calendar_write, "_ns_date", lambda foundation, moment: moment)
    return event_kit


def write(repeat: str | None) -> None:
    event: dict[str, Any] = coach_event(
        kind="checkin", category=None, note=None, alarm_min=None, repeat=repeat
    )
    CalendarWriter("Coach").write(event)


def rule_call(kit: MagicMock) -> Any:
    return kit.EKRecurrenceRule.alloc.return_value.initRecurrenceWithFrequency_interval_end_


def span_of(kit: MagicMock) -> Any:
    store = kit.EKEventStore.alloc.return_value.init.return_value
    return store.saveEvent_span_commit_error_.call_args.args[1]


@pytest.mark.parametrize(
    ("repeat", "frequency", "interval"),
    [("daily", DAILY, 1), ("weekly", WEEKLY, 1), ("biweekly", WEEKLY, 2)],
)
def test_repeat_becomes_recurrence_rule(
    kit: MagicMock, repeat: str, frequency: int, interval: int
) -> None:
    write(repeat)
    rule_call(kit).assert_called_once_with(frequency, interval, None)


@pytest.mark.parametrize("repeat", ["daily", "weekly", "biweekly"])
def test_repeating_event_is_saved_with_future_span(kit: MagicMock, repeat: str) -> None:
    write(repeat)
    assert span_of(kit) == FUTURE_EVENTS


def test_event_without_repeat_has_no_rule_and_this_span(kit: MagicMock) -> None:
    write(None)
    rule_call(kit).assert_not_called()
    assert span_of(kit) == THIS_EVENT
