"""ForeignWriter: правка чужих событий Календаря на подмене EventKit (шаг П5, партия 3)."""

import sys
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from ai_coach.workload.calendar_eventkit import CalendarError

THIS_EVENT, FUTURE_EVENTS = 30, 40
START = "2026-11-09T15:00:00"


def occurrence(uid: str, start_at: str, writable: bool = True) -> MagicMock:
    item = MagicMock()
    item.eventIdentifier.return_value = uid
    item.startDate.return_value.timeIntervalSince1970.return_value = datetime.fromisoformat(
        start_at
    ).timestamp()
    item.calendar.return_value.allowsContentModifications.return_value = writable
    return item


@pytest.fixture
def kit(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    from ai_coach.agenda import calendar_edit

    event_kit = MagicMock()
    event_kit.EKSpanThisEvent = THIS_EVENT
    event_kit.EKSpanFutureEvents = FUTURE_EVENTS
    store = event_kit.EKEventStore.alloc.return_value.init.return_value
    store.calendarsForEntityType_.return_value = [MagicMock(), MagicMock()]
    store.eventsMatchingPredicate_.return_value = [occurrence("u1", START)]
    store.saveEvent_span_commit_error_.return_value = (True, None)
    store.removeEvent_span_commit_error_.return_value = (True, None)
    monkeypatch.setitem(sys.modules, "EventKit", event_kit)
    monkeypatch.setitem(sys.modules, "Foundation", MagicMock())
    monkeypatch.setattr(calendar_edit, "_request_access", lambda store: (True, None))
    monkeypatch.setattr(calendar_edit, "_ns_date", lambda foundation, moment: moment)
    return event_kit


def store_of(kit: MagicMock) -> MagicMock:
    return kit.EKEventStore.alloc.return_value.init.return_value


def writer() -> Any:
    from ai_coach.agenda.calendar_edit import ForeignWriter

    return ForeignWriter()


def test_update_sets_fields_and_saves_with_this_span(kit: MagicMock) -> None:
    values = {
        "title": "Новое",
        "note": "заметка",
        "start_at": "2026-11-09T16:00:00",
        "end_at": "2026-11-09T17:00:00",
    }
    writer().update("u1", START, values)
    item = store_of(kit).eventsMatchingPredicate_.return_value[0]
    item.setTitle_.assert_called_once_with("Новое")
    item.setNotes_.assert_called_once_with("заметка")
    assert item.setStartDate_.call_args.args[0].isoformat() == "2026-11-09T16:00:00"
    assert item.setEndDate_.call_args.args[0].isoformat() == "2026-11-09T17:00:00"
    args = store_of(kit).saveEvent_span_commit_error_.call_args.args
    assert (args[0], args[1]) == (item, THIS_EVENT)


def test_update_touches_only_given_fields(kit: MagicMock) -> None:
    writer().update("u1", START, {"title": "Новое"})
    item = store_of(kit).eventsMatchingPredicate_.return_value[0]
    item.setStartDate_.assert_not_called()
    item.setNotes_.assert_not_called()


def test_occurrence_searches_the_day_of_start_in_all_calendars(kit: MagicMock) -> None:
    writer().update("u1", START, {"title": "Новое"})
    store = store_of(kit)
    start, end, calendars = store.predicateForEventsWithStartDate_endDate_calendars_.call_args.args
    assert (start.isoformat(), end.isoformat()) == ("2026-11-09T00:00:00", "2026-11-10T00:00:00")
    assert calendars == store.calendarsForEntityType_.return_value


def test_occurrence_picks_the_one_with_same_uid_and_start(kit: MagicMock) -> None:
    morning = occurrence("u1", "2026-11-09T09:00:00")
    other = occurrence("u2", START)
    wanted = occurrence("u1", START)
    store_of(kit).eventsMatchingPredicate_.return_value = [morning, other, wanted]
    writer().update("u1", START, {"title": "Новое"})
    wanted.setTitle_.assert_called_once_with("Новое")
    morning.setTitle_.assert_not_called()
    other.setTitle_.assert_not_called()


def test_missing_occurrence_asks_to_sync_and_saves_nothing(kit: MagicMock) -> None:
    store_of(kit).eventsMatchingPredicate_.return_value = [occurrence("u1", "2026-11-09T09:00:00")]
    with pytest.raises(CalendarError, match="обнови синк"):
        writer().update("u1", START, {"title": "Новое"})
    store_of(kit).saveEvent_span_commit_error_.assert_not_called()


def test_update_readonly_calendar_is_error_before_save(kit: MagicMock) -> None:
    store_of(kit).eventsMatchingPredicate_.return_value = [occurrence("u1", START, writable=False)]
    with pytest.raises(CalendarError, match="только для чтения"):
        writer().update("u1", START, {"title": "Новое"})
    store_of(kit).saveEvent_span_commit_error_.assert_not_called()


def test_update_save_failure_is_calendar_error_with_text(kit: MagicMock) -> None:
    store_of(kit).saveEvent_span_commit_error_.return_value = (False, "сбой записи")
    with pytest.raises(CalendarError, match="сбой записи"):
        writer().update("u1", START, {"title": "Новое"})


def test_remove_uses_this_span(kit: MagicMock) -> None:
    writer().remove("u1", START)
    item = store_of(kit).eventsMatchingPredicate_.return_value[0]
    args = store_of(kit).removeEvent_span_commit_error_.call_args.args
    assert (args[0], args[1]) == (item, THIS_EVENT)


def test_remove_readonly_calendar_is_error_before_remove(kit: MagicMock) -> None:
    store_of(kit).eventsMatchingPredicate_.return_value = [occurrence("u1", START, writable=False)]
    with pytest.raises(CalendarError, match="только для чтения"):
        writer().remove("u1", START)
    store_of(kit).removeEvent_span_commit_error_.assert_not_called()


def test_remove_failure_is_calendar_error_with_text(kit: MagicMock) -> None:
    store_of(kit).removeEvent_span_commit_error_.return_value = (False, "сбой снятия")
    with pytest.raises(CalendarError, match="сбой снятия"):
        writer().remove("u1", START)


@pytest.mark.parametrize("allowed", [True, False])
def test_writable_follows_the_calendar(kit: MagicMock, allowed: bool) -> None:
    store_of(kit).eventsMatchingPredicate_.return_value = [
        occurrence("u1", START, writable=allowed)
    ]
    assert writer().writable("u1", START) is allowed


def test_missing_eventkit_is_calendar_error_with_hint(
    kit: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "EventKit", None)
    with pytest.raises(CalendarError) as raised:
        writer().note("u1", START)
    assert str(raised.value) == (
        "EventKit недоступен: нужен macOS и pyobjc-framework-EventKit (uv sync)."
    )


def test_missing_foundation_is_calendar_error(
    kit: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "Foundation", None)
    with pytest.raises(CalendarError, match="EventKit недоступен"):
        writer().note("u1", START)


def test_dates_are_built_through_foundation_and_access_asked_of_the_store(
    kit: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach.agenda import calendar_edit

    seen: list[Any] = []
    asked: list[Any] = []
    monkeypatch.setattr(
        calendar_edit, "_ns_date", lambda foundation, moment: seen.append(foundation) or moment
    )
    monkeypatch.setattr(
        calendar_edit, "_request_access", lambda store: asked.append(store) or (True, None)
    )
    writer().note("u1", START)
    assert seen == [sys.modules["Foundation"]] * 2
    assert asked == [store_of(kit)]


def test_update_converts_new_times_through_foundation(
    kit: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach.agenda import calendar_edit

    seen: list[Any] = []
    monkeypatch.setattr(
        calendar_edit, "_ns_date", lambda foundation, moment: seen.append(foundation) or moment
    )
    writer().update("u1", START, {"end_at": "2026-11-09T17:00:00"})
    assert seen[-1] is sys.modules["Foundation"]


@pytest.mark.parametrize(
    ("error", "tail"),
    [("нет прав", ": нет прав"), (None, ""), ("", "")],
    ids=["text", "none", "empty"],
)
def test_denied_access_message(
    kit: MagicMock, monkeypatch: pytest.MonkeyPatch, error: str | None, tail: str
) -> None:
    from ai_coach.agenda import calendar_edit

    monkeypatch.setattr(calendar_edit, "_request_access", lambda store: (False, error))
    with pytest.raises(CalendarError) as raised:
        writer().note("u1", START)
    assert str(raised.value) == f"Нет доступа к календарю{tail}. {calendar_edit.HINT}"


def test_occurrence_asks_event_calendars_and_searches_with_the_predicate(kit: MagicMock) -> None:
    writer().note("u1", START)
    store = store_of(kit)
    store.calendarsForEntityType_.assert_called_once_with(kit.EKEntityTypeEvent)
    store.eventsMatchingPredicate_.assert_called_once_with(
        store.predicateForEventsWithStartDate_endDate_calendars_.return_value
    )


def test_missing_occurrence_message(kit: MagicMock) -> None:
    store_of(kit).eventsMatchingPredicate_.return_value = []
    with pytest.raises(CalendarError) as raised:
        writer().note("u1", START)
    assert str(raised.value) == "события нет в календаре - обнови синк."


def test_note_returns_the_notes_of_the_occurrence(kit: MagicMock) -> None:
    store_of(kit).eventsMatchingPredicate_.return_value[0].notes.return_value = "описание"
    assert writer().note("u1", START) == "описание"


def test_note_of_event_without_notes_is_empty_string(kit: MagicMock) -> None:
    store_of(kit).eventsMatchingPredicate_.return_value[0].notes.return_value = None
    assert writer().note("u1", START) == ""


def test_note_looks_for_the_given_uid_and_start(kit: MagicMock) -> None:
    with pytest.raises(CalendarError, match="обнови синк"):
        writer().note("other", START)
    with pytest.raises(CalendarError, match="обнови синк"):
        writer().note("u1", "2026-11-09T09:00:00")


def test_readonly_message_is_exact(kit: MagicMock) -> None:
    store_of(kit).eventsMatchingPredicate_.return_value = [occurrence("u1", START, writable=False)]
    with pytest.raises(CalendarError) as raised:
        writer().update("u1", START, {"title": "Х"})
    assert str(raised.value) == "календарь только для чтения."


def test_save_and_remove_use_commit_and_no_error_out_param(kit: MagicMock) -> None:
    writer().update("u1", START, {"title": "Х"})
    writer().remove("u1", START)
    item = store_of(kit).eventsMatchingPredicate_.return_value[0]
    assert store_of(kit).saveEvent_span_commit_error_.call_args.args == (
        item,
        THIS_EVENT,
        True,
        None,
    )
    assert store_of(kit).removeEvent_span_commit_error_.call_args.args == (
        item,
        THIS_EVENT,
        True,
        None,
    )


def test_save_failure_text_is_cut_to_120_characters(kit: MagicMock) -> None:
    store_of(kit).saveEvent_span_commit_error_.return_value = (False, "я" * 200)
    with pytest.raises(CalendarError) as raised:
        writer().update("u1", START, {"title": "Х"})
    assert str(raised.value) == "календарь не сохранил событие: " + "я" * 120


def test_remove_failure_text_is_cut_to_120_characters(kit: MagicMock) -> None:
    store_of(kit).removeEvent_span_commit_error_.return_value = (False, "я" * 200)
    with pytest.raises(CalendarError) as raised:
        writer().remove("u1", START)
    assert str(raised.value) == "календарь не снял событие: " + "я" * 120


def test_unexpected_save_exception_is_calendar_error_with_type_name(kit: MagicMock) -> None:
    store_of(kit).saveEvent_span_commit_error_.side_effect = RuntimeError("секрет")
    with pytest.raises(CalendarError) as raised:
        writer().update("u1", START, {"title": "Х"})
    assert str(raised.value) == "событие не изменено: RuntimeError"


def test_unexpected_remove_exception_is_calendar_error_with_type_name(kit: MagicMock) -> None:
    store_of(kit).removeEvent_span_commit_error_.side_effect = RuntimeError("секрет")
    with pytest.raises(CalendarError) as raised:
        writer().remove("u1", START)
    assert str(raised.value) == "событие не снято: RuntimeError"
