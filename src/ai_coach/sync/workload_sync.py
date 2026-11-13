"""Синхронизация нагрузки -> база: события календаря, счётчики туду, груминга и часы экрана.

Сначала всё читается, потом всё пишется одной транзакцией. Упавший источник — замечание в
итоге и строка error в sync_log, остальные источники пишутся. todo.json и hb-watch только
читаются, в базу идут числа. sync_log kind='workload', а не 'sync': иначе ломается first_run_today.
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach.store.agenda import update_event
from ai_coach.store.journal import add_sync_log
from ai_coach.store.workload import replace_calendar_window, upsert_counter
from ai_coach.sync.coach_calendar import coach_part
from ai_coach.workload import (
    AHEAD_DAYS,
    AwReader,
    CalendarError,
    CalendarReader,
    ClaudeError,
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
from ai_coach.workload.claude import scan_claude

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
        demand = config.demand(category, event.get("title"))
        rows.append({**row, "category": category, "demand": demand, "synced_at": stamp})
    return rows, sorted(unknown)


def read_calendar(
    reader: EventReader | None,
    config: WorkloadConfig,
    conn: sqlite3.Connection,
    stamp: str,
    window: tuple[date, date],
) -> tuple[list[dict[str, Any]], list[int], list[dict[str, Any]], list[str]]:
    """Читает календарь: события для базы, id пропавших событий коуча, переносы и замечания
    для итога."""
    raw = (reader or CalendarReader()).read(window[0], window[1])
    events, unknown = stored_events(raw, config, stamp)
    notes = [f"неразмеченные календари: {', '.join(unknown)}"] if unknown else []
    if not config.coach_calendar:
        return events, [], [], notes
    mine, gone, moves, coach_notes = coach_part(raw, config, conn, stamp, window)
    return events + mine, gone, moves, notes + coach_notes


def resolve_config(config: WorkloadConfig | None, errors: list[str]) -> WorkloadConfig:
    """Готовый конфиг как есть; None - из файла, битый файл - замечание в errors и конфиг по
    умолчанию."""
    if config is not None:
        return config
    try:
        return load_config()
    except WorkloadConfigError as e:
        errors.append(str(e))
        return default_config()


def read_counters(
    config: WorkloadConfig,
    screen: ScreenReader | None,
    first: date,
    today: date,
    notes: list[str],
    errors: list[str],
) -> list[dict[str, Any]]:
    """Счётчики туду, груминга, экрана и Claude Code за дни first..today; замечания и сбои
    источников дописывает в notes и errors в порядке чтения."""
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
    counters += claude_counters(config, first, today, notes, errors)
    return counters


def claude_counters(
    config: WorkloadConfig, first: date, today: date, notes: list[str], errors: list[str]
) -> list[dict[str, Any]]:
    """Счётчики Claude Code за дни first..today; нет каталога и нераспознанный формат -
    замечание в notes, сбой чтения - в errors."""
    try:
        found, files, seen = scan_claude(config.claude_projects_path, first, today)
        if not found:
            notes.append("Claude: каталог не найден")
        elif files and not seen:
            notes.append("Claude: записей не распознано")
    except ClaudeError as e:
        errors.append(f"Claude: {e}")
        return []
    return found


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
    config = resolve_config(config, errors)
    events, gone, moves = None, [], []
    if config.has_calendar:
        try:
            events, gone, moves, found = read_calendar(reader, config, conn, started, (first, last))
            notes += found
        except CalendarError as e:
            errors.append(f"календарь: {e}")
    else:
        notes.append("календарь не настроен")
    counters = read_counters(config, screen, first, today, notes, errors)
    summary = f"событий {len(events) if events is not None else 0}, счётчиков {len(counters)}"
    message = "; ".join([summary, *notes, *errors])
    with conn:
        if events is not None:
            replace_calendar_window(conn, first.isoformat(), last.isoformat(), events)
        for move in moves:
            values = {k: move[k] for k in ("start_at", "end_at", "date")}
            update_event(conn, move["id"], values)
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
