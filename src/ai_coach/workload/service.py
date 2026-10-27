"""Метрики дня из событий календаря и счётчиков. Часы считаются на чтении, в базе не хранятся.

Правила: в часы идут не отменённые и не отклонённые события без all-day (tentative считается),
повторы - каждый экземпляр, пересечения - объединение, событие через полночь режется по дням.
All-day рабочее событие даёт только флаг all_day_work. Вечер - после EVENING_FROM.
"""

import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

from ai_coach.store.workload import list_calendar_events, list_counters

EVENING_FROM = time(19, 0)
AHEAD_DAYS = 14
HOURS = ("work", "personal", "hobby", "rest")
INT_COUNTERS = ("todo_open", "todo_closed", "grooming_done", "grooming_pending")
SCREEN_COUNTERS = (
    "screen_work_hours",
    "screen_hobby_hours",
    "screen_browser_hours",
    "screen_evening_hours",
)
COUNTERS = INT_COUNTERS + SCREEN_COUNTERS
EVENT_FIELDS = (
    "title",
    "start_at",
    "end_at",
    "all_day",
    "calendar",
    "category",
    "status",
    "my_status",
)
SATURDAY = 5
SECONDS_IN_HOUR = 3600

Span = tuple[datetime, datetime]


def _counted(event: dict[str, Any]) -> bool:
    """В нагрузку входят не отменённые и не отклонённые мной события."""
    return event["status"] != "cancelled" and event["my_status"] != "declined"


def _clip(event: dict[str, Any], start: datetime, end: datetime) -> Span | None:
    """Часть события внутри [start, end); None - пересечения нет."""
    first = max(datetime.fromisoformat(event["start_at"]), start)
    last = min(datetime.fromisoformat(event["end_at"]), end)
    return (first, last) if last > first else None


def _hours(spans: list[Span]) -> float:
    """Сумма часов после объединения пересекающихся отрезков."""
    total = 0.0
    reach: datetime | None = None
    for first, last in sorted(spans):
        if reach is not None and first < reach:
            first = reach
        if last > first:
            total += (last - first).total_seconds()
            reach = last
    return round(total / SECONDS_IN_HOUR, 2)


def _covers_day(event: dict[str, Any], day: date) -> bool:
    """All-day событие захватывает день; конец ровно в полночь не включается."""
    last = datetime.fromisoformat(event["end_at"])
    if last.time() == time.min and last.date() > date.fromisoformat(event["date"]):
        last -= timedelta(days=1)
    return date.fromisoformat(event["date"]) <= day <= last.date()


def _day_row(
    day: date, events: list[dict[str, Any]], counters: dict[str, int | float]
) -> dict[str, Any]:
    midnight = datetime.combine(day, time.min)
    evening = datetime.combine(day, EVENING_FROM)
    next_midnight = midnight + timedelta(days=1)
    live = [e for e in events if _counted(e)]
    timed = [e for e in live if not e["all_day"]]
    weekend = day.weekday() >= SATURDAY
    row: dict[str, Any] = {"date": day.isoformat(), "weekend": weekend}
    for category in HOURS:
        mine = [e for e in timed if e["category"] == category]
        whole = [s for e in mine if (s := _clip(e, midnight, next_midnight))]
        late = [s for e in mine if (s := _clip(e, evening, next_midnight))]
        row[f"{category}_hours"] = _hours(whole)
        row[f"{category}_evening_hours"] = _hours(late)
    row["all_day_work"] = any(
        e["all_day"] and e["category"] == "work" and _covers_day(e, day) for e in live
    )
    for kind in COUNTERS:
        row[kind] = counters.get(f"{day.isoformat()}|{kind}")
    return row


def _rows(conn: sqlite3.Connection, start: date, end: date) -> list[dict[str, Any]]:
    # событие, начатое накануне, может заходить за полночь в первый день
    found = list_calendar_events(conn, (start - timedelta(days=1)).isoformat(), end.isoformat())
    counters = {
        f"{c['date']}|{c['kind']}": float(c["value"])
        if c["kind"] in SCREEN_COUNTERS
        else int(c["value"])
        for c in list_counters(conn, start.isoformat(), end.isoformat())
    }
    rows: list[dict[str, Any]] = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        rows.append(_day_row(day, found, counters))
    return rows


def workload_series(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Метрики по дням start..end включительно (YYYY-MM-DD), по возрастанию даты, без названий.
    Ключи дня: date, weekend (сб/вс),
    {work,personal,hobby,rest}_hours и _evening_hours (после 19:00),
    all_day_work, todo_open, todo_closed, grooming_done, grooming_pending (None - не считались),
    screen_work/hobby/browser/evening_hours (часы экрана 04:00→04:00, вечер 19:00→04:00;
    None - нет данных экрана за день)."""
    return _rows(conn, date.fromisoformat(start), date.fromisoformat(end))


def workload_day(conn: sqlite3.Connection, day: str, events: bool = False) -> dict[str, Any]:
    """Метрики одного дня; events=True - ещё и список событий дня с названиями (events)."""
    row = _rows(conn, date.fromisoformat(day), date.fromisoformat(day))[0]
    if events:
        # событие, начатое накануне, попадает в день, если заходит за полночь
        current = date.fromisoformat(day)
        before = (current - timedelta(days=1)).isoformat()
        midnight = datetime.combine(current, time.min)
        found = [
            e
            for e in list_calendar_events(conn, before, day)
            if e["date"] == day
            or (
                _covers_day(e, current)
                if e["all_day"]
                else _clip(e, midnight, midnight + timedelta(days=1))
            )
        ]
        row["events"] = [{k: e[k] for k in EVENT_FIELDS} for e in found]
    return row
