"""Синхронизация нагрузки -> база: события календаря и счётчики туду и груминга.

Сначала всё читается, потом всё пишется одной транзакцией. Упавший источник — замечание в
итоге и строка error в sync_log, остальные источники пишутся. todo.json и hb-watch только
читаются, в базу идут числа. sync_log kind='workload', а не 'sync': иначе ломается first_run_today.
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach.store.journal import add_sync_log
from ai_coach.store.workload import replace_calendar_window, upsert_counter
from ai_coach.workload import (
    AHEAD_DAYS,
    CalendarError,
    CalendarReader,
    EventReader,
    GroomingError,
    TodoError,
    WorkloadConfig,
    WorkloadConfigError,
    default_config,
    load_config,
    read_grooming,
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
        if category == "ignore":
            continue
        if category == "unknown":
            unknown.add(event["calendar"].strip())
        row: dict[str, Any] = {"raw_json": {}, **event, "date": event["start_at"][:10]}
        rows.append({**row, "category": category, "synced_at": stamp})
    return rows, sorted(unknown)


def sync_workload(
    conn: sqlite3.Connection,
    days: int,
    today: date | None = None,
    reader: EventReader | None = None,
    config: WorkloadConfig | None = None,
) -> str:
    """Читает календарь (окно today-days .. today+AHEAD_DAYS), туду и груминг, пишет в базу,
    возвращает итог. Нет разметки календарей — календарь пропущен, туду и груминг читаются
    по пути из конфига или по умолчанию."""
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
    events: list[dict[str, Any]] | None = None
    if config.has_calendar:
        try:
            raw = (reader or CalendarReader()).read(first, last)
            events, unknown = stored_events(raw, config, started)
            if unknown:
                notes.append(f"неразмеченные календари: {', '.join(unknown)}")
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
    summary = f"событий {len(events) if events is not None else 0}, счётчиков {len(counters)}"
    message = "; ".join([summary, *notes, *errors])
    with conn:
        if events is not None:
            replace_calendar_window(conn, first.isoformat(), last.isoformat(), events)
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
