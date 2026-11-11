"""План дня: разбор параметров, занятое и тренировка из базы, укладка - agenda.day_layout,
черновики coach_events одной транзакцией. В календарь не пишем: это делает пользователь
командой coach event write.
"""

import re
import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

from ai_coach.agenda.day_layout import (
    FOCUS_MAX,
    FOCUS_UNTIL,
    INBOX_TITLE,
    WEEKDAY,
    WEEKEND,
    Frame,
    Task,
    Training,
    plan_day,
)
from ai_coach.agenda.service import AHEAD_DAYS, AgendaError, agenda_rows, create_draft
from ai_coach.agenda.sleep_limits import sleep_limits
from ai_coach.agenda.slots import busy_spans, ceil_step
from ai_coach.sport_nutrition import workout_duration_min
from ai_coach.store.agenda import ACTIVE, list_events
from ai_coach.store.plans import list_planned_workouts
from ai_coach.workload.service import SATURDAY, Span

DAY_END = time(0, 0)
TRAINING_PAD_MIN = 15
TRAINING_DEFAULT_MIN = 60
PLAN_KINDS = ("focus", "meal")
DRAFT_FIELDS = ("kind", "title", "start_at", "end_at", "category")
CLOCK = re.compile(r"\d\d:\d\d")


def _clock(value: str | None, name: str) -> time | None:
    if value is None:
        return None
    try:
        if not CLOCK.fullmatch(value):
            raise ValueError
        return time.fromisoformat(value)
    except ValueError:
        raise AgendaError(f"{name}: нужно HH:MM, получено: {value!r}") from None


def _window(day: date, frame: Frame, day_start: str | None, day_end: str | None) -> Span:
    midnight = datetime.combine(day, time.min)
    start = _clock(day_start, "day_start")
    finish = _clock(day_end, "day_end")
    first = datetime.combine(day, frame.start if start is None else start)
    if finish is None or finish == DAY_END:
        last = midnight + timedelta(days=1)
    else:
        last = datetime.combine(day, finish)
    if last <= first:
        raise AgendaError("day_end должен быть позже day_start.")
    return first, last


def _tasks(tasks: list[dict[str, Any]] | None, weekend: bool) -> list[Task]:
    checked: list[Task] = []
    for task in tasks or []:
        title = str(task.get("title") or "").strip()
        minutes = task.get("minutes")
        if not title:
            raise AgendaError("У задачи нет названия.")
        if not isinstance(minutes, int) or minutes <= 0:
            raise AgendaError(f"Задача {title!r}: minutes должно быть целым больше нуля.")
        default = "personal" if weekend else "work"
        checked.append(Task(title, minutes, task.get("category") or default))
    return checked


def _training(conn: sqlite3.Connection, day: date, at: time, skipped: list[str]) -> Training | None:
    """Тренировка плана дня (не отменённая, ещё не стоящая в agenda) на время at."""
    iso = day.isoformat()
    standing = {e["workout_id"] for e in agenda_rows(conn, iso, iso) if e["kind"] == "training"}
    planned = [w for w in list_planned_workouts(conn, iso, iso) if w["status"] != "cancelled"]
    if not planned:
        skipped.append("Тренировки плана на этот день нет.")
        return None
    left = [w for w in planned if w["id"] not in standing]
    if not left:
        skipped.append("Тренировка плана уже стоит в agenda.")
        return None
    workout = left[0]
    minutes = (workout_duration_min(workout) or TRAINING_DEFAULT_MIN) + TRAINING_PAD_MIN
    return Training(workout["name"], datetime.combine(day, at), minutes, workout["id"])


def create_day_plan(
    conn: sqlite3.Connection,
    day: date,
    tasks: list[dict[str, Any]] | None = None,
    *,
    training_at: str | None = None,
    day_start: str | None = None,
    day_end: str | None = None,
    breakfast_at: str | None = None,
    snack_at: str | None = None,
    dinner_at: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Черновики плана дня одной транзакцией. Будни: после завтрака и отдыха инбокс 2x20 мин,
    за каждым фокус. tasks: title, minutes, category (по умолчанию work
    в будни, personal в сб/вс). Сегодня - блоки не раньше now. Если на день уже есть focus или
    meal (draft, written) - ничего не создаёт, отвечает already_planned с id. Ответ: date, drafts
    (draft_id, kind, title, start_at, end_at, category), skipped, busy (число занятых отрезков)."""
    now = now or datetime.now()
    today = now.date()
    if not today <= day <= today + timedelta(days=AHEAD_DAYS):
        raise AgendaError(f"Дата от сегодня до {AHEAD_DAYS} дней вперёд.")
    weekend = day.weekday() >= SATURDAY
    frame = WEEKEND if weekend else WEEKDAY
    frame = frame._replace(
        breakfast=_clock(breakfast_at, "breakfast_at") or frame.breakfast,
        snack=_clock(snack_at, "snack_at") or frame.snack,
        dinner=_clock(dinner_at, "dinner_at") or frame.dinner,
    )
    first, last = _window(day, frame, day_start, day_end)
    if day == today:
        first = max(first, ceil_step(now))
    checked = _tasks(tasks, weekend)
    at = _clock(training_at, "training_at")
    iso = day.isoformat()
    standing = [e["id"] for e in list_events(conn, iso, iso, ACTIVE) if e["kind"] in PLAN_KINDS]
    if standing:
        return {"date": iso, "already_planned": standing}
    skipped: list[str] = []
    titles = {
        e["title"].strip().casefold() for e in agenda_rows(conn, iso, iso) if e["kind"] == "task"
    }
    inbox = INBOX_TITLE.casefold() not in titles
    if not inbox:
        skipped.append(f"{INBOX_TITLE}: уже стоит в agenda")
    fresh: list[Task] = []
    for task in checked:
        if task.title.strip().casefold() in titles:
            skipped.append(f"{task.title}: уже стоит в agenda")
        else:
            fresh.append(task)
    checked = fresh
    training = _training(conn, day, at, skipped) if at is not None else None
    busy = busy_spans(conn, day)
    until, focus_max, reasons = sleep_limits(conn, day, today, now, FOCUS_UNTIL, FOCUS_MAX)
    blocks, more = plan_day(
        frame, (first, last), busy, checked, training, weekend, until, focus_max, inbox
    )
    more.extend(reasons)
    drafts: list[dict[str, Any]] = []
    with conn:
        for block in blocks:
            draft_id = create_draft(conn, block, today)
            drafts.append({"draft_id": draft_id} | {k: block[k] for k in DRAFT_FIELDS})
    return {"date": iso, "drafts": drafts, "skipped": skipped + more, "busy": len(busy)}
