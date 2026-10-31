"""План дня: свободные окна дня минус занятое, по правилам блоки задач, еды, отдыха, тренировки
и фокуса - черновиками coach_events за один вызов.

Занятое: события календаря дня (не отменённые, не отклонённые, не all-day) и события тренера
(draft, written), кроме checkin. Порядок укладки: тренировка (время назвал пользователь) ->
задачи до ужина -> завтрак, перекус, отдых после него, ужин (занято - ближайшее окно после, не
позже чем через MEAL_SHIFT_MIN, иначе skipped) -> задачи, не влезшие до ужина -> фокус
(не в сб/вс, не позже FOCUS_UNTIL). Блоки не пересекаются; окна короче MIN_SLOT пусты для задач
и фокуса. Рамка дня - до полуночи следующего дня. Сюда в календарь не пишем: это делает
пользователь командой coach event write.
"""

import re
import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any, NamedTuple

from ai_coach.agenda.service import AHEAD_DAYS, AgendaError, agenda_rows, create_draft
from ai_coach.agenda.slots import (
    MEAL_SHIFT_MIN,
    anchored,
    busy_spans,
    ceil_step,
    first_fit,
    free_slots,
    minutes_span,
    vacant,
)
from ai_coach.sport_nutrition import workout_duration_min
from ai_coach.store.agenda import ACTIVE, list_events
from ai_coach.store.plans import list_planned_workouts
from ai_coach.workload.service import EVENING_FROM, SATURDAY, Span


class Frame(NamedTuple):
    """Рамка дня: когда день начинается и якорные времена еды."""

    start: time
    breakfast: time
    snack: time
    dinner: time


class Task(NamedTuple):
    title: str
    minutes: int
    category: str


class Training(NamedTuple):
    """Тренировка плана: minutes - длина блока вместе с TRAINING_PAD_MIN."""

    title: str
    start: datetime
    minutes: int
    workout_id: int


WEEKDAY = Frame(time(10, 0), time(11, 0), time(15, 30), time(19, 0))
WEEKEND = Frame(time(11, 0), time(12, 0), time(16, 0), time(19, 0))
DAY_END = time(0, 0)
MEAL_MIN = 60
SNACK_MIN = 15
REST_MIN = 30
FOCUS_MIN = 90
BREAK_MIN = 15
FOCUS_MAX = 3
FOCUS_UNTIL = EVENING_FROM
TRAINING_PAD_MIN = 15
TRAINING_DEFAULT_MIN = 60
PLAN_KINDS = ("focus", "meal")
DRAFT_FIELDS = ("kind", "title", "start_at", "end_at", "category")
CLOCK = re.compile(r"\d\d:\d\d")


class _Layout:
    """Укладка одного дня: занятые отрезки, поставленные блоки, причины отказов."""

    def __init__(self, window: Span, busy: list[Span]) -> None:
        self.window = window
        self.taken = list(busy)
        self.blocks: list[dict[str, Any]] = []
        self.skipped: list[str] = []

    def put(
        self,
        kind: str,
        title: str,
        span: Span,
        category: str | None = None,
        workout_id: int | None = None,
    ) -> None:
        self.taken.append(span)
        self.blocks.append(
            {
                "kind": kind,
                "title": title,
                "start_at": span[0].isoformat(timespec="minutes"),
                "end_at": span[1].isoformat(timespec="minutes"),
                "category": category,
                "workout_id": workout_id,
            }
        )

    def anchor(
        self, title: str, kind: str, desired: datetime, minutes: int, category: str | None = None
    ) -> Span | None:
        """Якорный блок: от desired, ближайшее окно; раньше начала рамки или позже конца -
        пропуск с причиной в skipped."""
        if desired < self.window[0]:
            self.skipped.append(f"{title} {desired:%H:%M}: раньше начала дня")
            return None
        if desired + minutes_span(minutes) > self.window[1]:
            self.skipped.append(f"{title}: вне рамки дня")
            return None
        span = anchored(desired, minutes, self.window, self.taken)
        if span is None:
            self.skipped.append(f"{title}: занято, окна в течение {MEAL_SHIFT_MIN // 60} ч нет")
            return None
        self.put(kind, title, span, category)
        return span

    def training(self, training: Training) -> None:
        span = (training.start, training.start + minutes_span(training.minutes))
        if vacant(span, self.window, self.taken):
            self.put("training", training.title, span, workout_id=training.workout_id)
        else:
            self.skipped.append(
                f"Тренировка {training.start:%H:%M}: время занято или вне рамки дня"
            )

    def tasks(self, window: Span, tasks: list[Task]) -> list[Task]:
        """Задачи first-fit в окне window; возвращает не влезшие."""
        left: list[Task] = []
        for task in tasks:
            span = first_fit(window, self.taken, task.minutes)
            if span is None:
                left.append(task)
            else:
                self.put("task", task.title, span, task.category)
        return left

    def meals(self, frame: Frame) -> None:
        day = self.window[0].date()
        self.anchor("Завтрак", "meal", datetime.combine(day, frame.breakfast), MEAL_MIN)
        snack = self.anchor("Перекус", "meal", datetime.combine(day, frame.snack), SNACK_MIN)
        if snack is not None:
            self.anchor("Прогулка / отдых", "rest", snack[1], REST_MIN, "rest")
        self.anchor("Ужин", "meal", datetime.combine(day, frame.dinner), MEAL_MIN)

    def focus(self) -> None:
        """Фокус-блоки first-fit до FOCUS_UNTIL: не больше FOCUS_MAX, пауза BREAK_MIN."""
        limit = datetime.combine(self.window[0].date(), FOCUS_UNTIL)
        count = 0
        last_end: datetime | None = None
        for first, last in free_slots((self.window[0], min(limit, self.window[1])), self.taken):
            cursor = first
            if last_end is not None:
                cursor = ceil_step(max(first, last_end + minutes_span(BREAK_MIN)))
            while count < FOCUS_MAX and cursor + minutes_span(FOCUS_MIN) <= last:
                last_end = cursor + minutes_span(FOCUS_MIN)
                self.put("focus", "Фокус", (cursor, last_end))
                count += 1
                cursor = ceil_step(last_end + minutes_span(BREAK_MIN))


def plan_day(
    frame: Frame,
    window: Span,
    busy: list[Span],
    tasks: list[Task],
    training: Training | None,
    weekend: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Блоки дня (kind, title, start_at, end_at, category, workout_id; по времени) и причины,
    по которым что-то не поставлено. Чистая функция: базы не знает."""
    layout = _Layout(window, busy)
    if training is not None:
        layout.training(training)
    dinner = datetime.combine(window[0].date(), frame.dinner)
    later = layout.tasks((window[0], min(dinner, window[1])), tasks)
    layout.meals(frame)
    for task in layout.tasks(window, later):
        layout.skipped.append(f"{task.title}: {task.minutes} мин не влезают в день")
    if not weekend:
        layout.focus()
    layout.blocks.sort(key=lambda block: block["start_at"])
    return layout.blocks, layout.skipped


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
    """Черновики плана дня одной транзакцией. tasks: title, minutes, category (по умолчанию work
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
    fresh: list[Task] = []
    for task in checked:
        if task.title.strip().casefold() in titles:
            skipped.append(f"{task.title}: уже стоит в agenda")
        else:
            fresh.append(task)
    checked = fresh
    training = _training(conn, day, at, skipped) if at is not None else None
    busy = busy_spans(conn, day)
    blocks, more = plan_day(frame, (first, last), busy, checked, training, weekend)
    drafts: list[dict[str, Any]] = []
    with conn:
        for block in blocks:
            draft_id = create_draft(conn, block, today)
            drafts.append({"draft_id": draft_id} | {k: block[k] for k in DRAFT_FIELDS})
    return {"date": iso, "drafts": drafts, "skipped": skipped + more, "busy": len(busy)}
