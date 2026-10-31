"""Окна дня для плана дня: занятое, свободные окна, поиск места под блок. Чистая геометрия
отрезков; календарь не пишет."""

import sqlite3
from datetime import date, datetime, time, timedelta

from ai_coach.agenda.service import agenda_rows
from ai_coach.store.workload import list_calendar_events
from ai_coach.workload.service import (
    Span,
    _clip,  # pyright: ignore[reportPrivateUsage]
    _counted,  # pyright: ignore[reportPrivateUsage]
)

MIN_SLOT = 30
STEP_MIN = 5
MEAL_SHIFT_MIN = 120


def minutes_span(count: int) -> timedelta:
    return timedelta(minutes=count)


def ceil_step(moment: datetime) -> datetime:
    """Вверх до шага STEP_MIN."""
    rounded = moment.replace(second=0, microsecond=0)
    if rounded < moment:
        rounded += minutes_span(1)
    return rounded + minutes_span(-rounded.minute % STEP_MIN)


def busy_spans(conn: sqlite3.Connection, day: date) -> list[Span]:
    """Занятое внутри суток day: календарь и события тренера (кроме checkin); начатое накануне
    режется по полуночи."""
    midnight = datetime.combine(day, time.min)
    next_midnight = midnight + timedelta(days=1)
    before = (day - timedelta(days=1)).isoformat()
    found = [
        e
        for e in list_calendar_events(conn, before, day.isoformat())
        if _counted(e) and not e["all_day"]
    ]
    found += [
        e
        for e in agenda_rows(conn, before, day.isoformat())
        if e["kind"] != "checkin" and not e["all_day"]
    ]
    return [span for e in found if (span := _clip(e, midnight, next_midnight))]


def free_slots(window: Span, busy: list[Span]) -> list[Span]:
    """Свободные окна рамки window; начало вверх до STEP_MIN, короче MIN_SLOT не отдаются."""
    cursor, end = window
    gaps: list[Span] = []
    for first, last in sorted(busy):
        if first > cursor:
            gaps.append((cursor, min(first, end)))
        cursor = max(cursor, last)
    if cursor < end:
        gaps.append((cursor, end))
    rounded = [(ceil_step(first), last) for first, last in gaps]
    return [(first, last) for first, last in rounded if last - first >= minutes_span(MIN_SLOT)]


def vacant(span: Span, window: Span, taken: list[Span]) -> bool:
    first, last = span
    inside = window[0] <= first and last <= window[1]
    return inside and all(last <= other[0] or first >= other[1] for other in taken)


def anchored(desired: datetime, minutes: int, window: Span, taken: list[Span]) -> Span | None:
    """Ближайшее место для блока от desired, не позже чем через MEAL_SHIFT_MIN."""
    first = desired
    while first <= desired + minutes_span(MEAL_SHIFT_MIN):
        span = (first, first + minutes_span(minutes))
        if vacant(span, window, taken):
            return span
        first += minutes_span(STEP_MIN)
    return None


def first_fit(window: Span, taken: list[Span], minutes: int) -> Span | None:
    for first, last in free_slots(window, taken):
        if last - first >= minutes_span(minutes):
            return (first, first + minutes_span(minutes))
    return None
