"""Синхронизация нагрузки -> база: события календаря, счётчики туду, груминга и часы экрана.

Сначала всё читается, потом всё пишется одной транзакцией. Упавший источник — замечание в
итоге и строка error в sync_log, остальные источники пишутся. todo.json и hb-watch только
читаются, в базу идут числа. sync_log kind='workload', а не 'sync': иначе ломается first_run_today.
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach.store.agenda import find_by_uid, list_events, update_event
from ai_coach.store.journal import add_sync_log
from ai_coach.store.workload import replace_calendar_window, upsert_counter
from ai_coach.workload import (
    AHEAD_DAYS,
    AwReader,
    CalendarError,
    CalendarReader,
    EventReader,
    GroomingError,
    ScreenError,
    ScreenReader,
    TodoError,
    WorkloadConfig,
    WorkloadConfigError,
    default_config,
    load_config,
    read_grooming,
    read_screen,
    read_todo,
)

KIND = "workload"


def stored_events(
    raw: list[dict[str, Any]], config: WorkloadConfig, stamp: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """События для базы: категория по календарю (ignore пропускается) и названия
    неразмеченных календарей."""
    rows: list[dict[str, Any]] = []
    unknown: set[str] = set()
    for event in raw:
        category = config.category(event["calendar"])
        if category in ("ignore", "coach"):
            continue
        if category == "unknown":
            unknown.add(event["calendar"].strip())
        row: dict[str, Any] = {"raw_json": {}, **event, "date": event["start_at"][:10]}
        rows.append({**row, "category": category, "synced_at": stamp})
    return rows, sorted(unknown)


def own_events(
    raw: list[dict[str, Any]], config: WorkloadConfig, conn: sqlite3.Connection, stamp: str
) -> tuple[list[dict[str, Any]], int, set[str]]:
    """События календаря коуча: свои (записанные тренером, по uid) с категорией из coach_events -
    в базу, если категория есть; чужие (добавлены руками) пропускаются. Возвращает строки для
    базы, число чужих и uid всех своих."""
    rows: list[dict[str, Any]] = []
    foreign = 0
    seen: set[str] = set()
    for event in raw:
        if config.category(event["calendar"]) != "coach":
            continue
        found = find_by_uid(conn, event["uid"])
        if found is None or found["status"] != "written":
            foreign += 1
            continue
        seen.add(event["uid"])
        if found["category"] is not None:
            row: dict[str, Any] = {"raw_json": {}, **event, "date": event["start_at"][:10]}
            rows.append({**row, "category": found["category"], "synced_at": stamp})
    return rows, foreign, seen


def vanished(conn: sqlite3.Connection, first: date, last: date, seen: set[str]) -> list[int]:
    """id записанных тренером событий, пропавших из календаря: с днём начала в окне и повторяющиеся
    (их вхождения есть в окне всегда), чьего uid в календаре коуча нет."""
    written = list_events(conn, first.isoformat(), last.isoformat(), ("written",))
    ids = {e["id"]: e for e in written}
    for event in list_events(conn, "0000-01-01", first.isoformat(), ("written",)):
        if event["repeat"] is not None:
            ids[event["id"]] = event
    return [i for i, e in ids.items() if e["calendar_uid"] not in seen]


def coach_part(
    raw: list[dict[str, Any]],
    config: WorkloadConfig,
    conn: sqlite3.Connection,
    stamp: str,
    window: tuple[date, date],
) -> tuple[list[dict[str, Any]], list[int], list[str]]:
    """Календарь коуча: строки своих событий для базы, id пропавших и замечания для итога."""
    mine, foreign, seen = own_events(raw, config, conn, stamp)
    gone = vanished(conn, window[0], window[1], seen)
    notes: list[str] = []
    if foreign:
        notes.append(f"чужих событий в календаре коуча: {foreign}")
    if gone:
        notes.append(f"пропало из календаря коуча: {len(gone)}")
    return mine, gone, notes


def read_calendar(
    reader: EventReader | None,
    config: WorkloadConfig,
    conn: sqlite3.Connection,
    stamp: str,
    window: tuple[date, date],
) -> tuple[list[dict[str, Any]], list[int], list[str]]:
    """Читает календарь: события для базы, id пропавших событий коуча и замечания для итога."""
    raw = (reader or CalendarReader()).read(window[0], window[1])
    events, unknown = stored_events(raw, config, stamp)
    notes = [f"неразмеченные календари: {', '.join(unknown)}"] if unknown else []
    if not config.coach_calendar:
        return events, [], notes
    mine, gone, coach_notes = coach_part(raw, config, conn, stamp, window)
    return events + mine, gone, notes + coach_notes


def sync_workload(
    conn: sqlite3.Connection,
    days: int,
    today: date | None = None,
    reader: EventReader | None = None,
    config: WorkloadConfig | None = None,
    screen: ScreenReader | None = None,
) -> str:
    """Читает календарь (окно today-days .. today+AHEAD_DAYS), туду, груминг и экран (дни
    today-days .. today), пишет в базу, возвращает итог. Нет разметки календарей — календарь
    пропущен, туду и груминг читаются по пути из конфига или по умолчанию; нет [screen] —
    экран пропущен (замечание в итоге)."""
    started = datetime.now().isoformat(timespec="seconds")
    today = today or date.today()
    first = today - timedelta(days=days)
    last = today + timedelta(days=AHEAD_DAYS)
    errors: list[str] = []
    notes: list[str] = []
    if config is None:
        try:
            config = load_config()
        except WorkloadConfigError as e:
            errors.append(str(e))
            config = default_config()
    events, gone = None, []
    if config.has_calendar:
        try:
            events, gone, found = read_calendar(reader, config, conn, started, (first, last))
            notes += found
        except CalendarError as e:
            errors.append(f"календарь: {e}")
    else:
        notes.append("календарь не настроен")
    counters: list[dict[str, Any]] = []
    try:
        counters += read_todo(config.todo_path, first, today, today)
    except TodoError as e:
        errors.append(f"туду: {e}")
    try:
        counters += read_grooming(config.hb_watch_path, first, today, today)
    except GroomingError as e:
        errors.append(f"груминг: {e}")
    if config.screen is None:
        notes.append("экран не настроен")
    else:
        try:
            found, screen_notes = read_screen(
                screen or AwReader(config.screen), config.screen, first, today
            )
            counters += found
            notes += screen_notes
        except ScreenError as e:
            errors.append(f"экран: {e}")
    summary = f"событий {len(events) if events is not None else 0}, счётчиков {len(counters)}"
    message = "; ".join([summary, *notes, *errors])
    with conn:
        if events is not None:
            replace_calendar_window(conn, first.isoformat(), last.isoformat(), events)
        for event_id in gone:
            removed = {"status": "removed", "removed_at": started, "removed_by": "calendar"}
            update_event(conn, event_id, removed)
        for row in counters:
            upsert_counter(conn, {**row, "synced_at": started})
        add_sync_log(
            conn,
            {
                "started_at": started,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "kind": KIND,
                "status": "error" if errors else "ok",
                "message": message,
            },
        )
    return message
