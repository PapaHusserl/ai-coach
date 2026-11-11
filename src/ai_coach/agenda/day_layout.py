"""Укладка плана дня: свободные окна дня минус занятое, по правилам блоки задач, еды, отдыха,
тренировки, инбокса и фокуса. Чистая: базы не знает.

Порядок укладки: тренировка (время назвал пользователь) ->
готовка и завтрак (одним отрезком), перекус, отдых после него, готовка и ужин (занято -
ближайшее окно после, не позже чем через MEAL_SHIFT_MIN, иначе skipped) -> инбокс (два блока
по INBOX_MIN, после завтрака и после отдыха, не в сб/вс) -> задачи до ужина ->
задачи, не влезшие до ужина -> фокус (не в сб/вс, по блоку за каждым инбоксом, не позже
FOCUS_UNTIL; при сигнале сна - sleep_limits). Блоки не пересекаются;
окна короче MIN_SLOT пусты для задач и фокуса. Рамка дня - до полуночи следующего дня.
"""

from datetime import datetime, time
from typing import Any, NamedTuple

from ai_coach.agenda.slots import (
    MEAL_SHIFT_MIN,
    anchored,
    ceil_step,
    first_fit,
    minutes_span,
    vacant,
)
from ai_coach.workload.service import EVENING_FROM, Span


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


WEEKDAY = Frame(time(10, 0), time(11, 0), time(15, 30), time(19, 30))
WEEKEND = Frame(time(11, 0), time(12, 0), time(16, 0), time(19, 30))
MEAL_MIN = 60
COOK_MIN = 30
SNACK_MIN = 15
REST_MIN = 30
FOCUS_MIN = 60
BREAK_MIN = 15
FOCUS_MAX = 2
INBOX_MIN = 20
INBOX_TITLE = "Инбокс"
INBOX_CATEGORY = "work"
FOCUS_UNTIL = EVENING_FROM


class _Layout:
    """Укладка одного дня: занятые отрезки, поставленные блоки, причины отказов."""

    def __init__(self, window: Span, busy: list[Span]) -> None:
        self.window = window
        self.taken = list(busy)
        self.blocks: list[dict[str, Any]] = []
        self.skipped: list[str] = []
        self.breakfast_end: datetime | None = None
        self.rest_end: datetime | None = None

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

    def meal(self, title: str, desired: datetime) -> datetime | None:
        """Еда с готовкой перед ней: один отрезок COOK_MIN + MEAL_MIN, ищется и сдвигается
        вместе; начало готовки раньше рамки - отрезок от начала рамки. Возвращает конец еды."""
        if desired < self.window[0]:
            self.skipped.append(f"{title} {desired:%H:%M}: раньше начала дня")
            return None
        start = max(desired - minutes_span(COOK_MIN), self.window[0])
        total = COOK_MIN + MEAL_MIN
        if start + minutes_span(total) > self.window[1]:
            self.skipped.append(f"{title}: вне рамки дня")
            return None
        span = anchored(start, total, self.window, self.taken)
        if span is None:
            self.skipped.append(f"{title}: занято, окна в течение {MEAL_SHIFT_MIN // 60} ч нет")
            return None
        cooked = span[0] + minutes_span(COOK_MIN)
        self.put("meal", "Готовка", (span[0], cooked))
        self.put("meal", title, (cooked, span[1]))
        return span[1]

    def meals(self, frame: Frame) -> None:
        day = self.window[0].date()
        self.breakfast_end = self.meal("Завтрак", datetime.combine(day, frame.breakfast))
        snack = self.anchor("Перекус", "meal", datetime.combine(day, frame.snack), SNACK_MIN)
        if snack is not None:
            rest = self.anchor("Прогулка / отдых", "rest", snack[1], REST_MIN, "rest")
            self.rest_end = None if rest is None else rest[1]
        self.meal("Ужин", datetime.combine(day, frame.dinner))

    def inbox(self, frame: Frame) -> list[datetime | None]:
        """Два блока инбокса: после завтрака и после отдыха; возвращает концы поставленных
        (None - не поставлен)."""
        day = self.window[0].date()
        first = self.breakfast_end or self.window[0]
        second = self.rest_end or (
            datetime.combine(day, frame.snack) + minutes_span(SNACK_MIN + REST_MIN)
        )
        ends: list[datetime | None] = []
        for desired in (first, second):
            span = self.anchor(INBOX_TITLE, "task", desired, INBOX_MIN, INBOX_CATEGORY)
            ends.append(None if span is None else span[1])
        return ends

    def focus(self, focus_until: time, focus_max: int, starts: list[datetime | None]) -> None:
        """По фокус-блоку от каждого из starts (None - от начала рамки) до focus_until: не больше
        focus_max, пауза BREAK_MIN от предыдущего блока."""
        limit = min(datetime.combine(self.window[0].date(), focus_until), self.window[1])
        count = 0
        last_end: datetime | None = None
        for start in starts:
            if count >= focus_max:
                break
            cursor = start or self.window[0]
            if last_end is not None:
                cursor = ceil_step(max(cursor, last_end + minutes_span(BREAK_MIN)))
            if cursor >= limit:
                continue
            span = first_fit((cursor, limit), self.taken, FOCUS_MIN)
            if span is not None:
                self.put("focus", "Фокус", span)
                last_end = span[1]
                count += 1


def plan_day(
    frame: Frame,
    window: Span,
    busy: list[Span],
    tasks: list[Task],
    training: Training | None,
    weekend: bool,
    focus_until: time = FOCUS_UNTIL,
    focus_max: int = FOCUS_MAX,
    inbox: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Блоки дня (kind, title, start_at, end_at, category, workout_id; по времени) и причины,
    по которым что-то не поставлено. Чистая функция: базы не знает. Инбокс - два блока в будни
    (если inbox), фокус за каждым - не позже focus_until и не больше focus_max блоков."""
    layout = _Layout(window, busy)
    if training is not None:
        layout.training(training)
    dinner = datetime.combine(window[0].date(), frame.dinner)
    layout.meals(frame)
    starts: list[datetime | None] = [None, None]
    if not weekend and inbox:
        starts = layout.inbox(frame)
    later = layout.tasks((window[0], min(dinner, window[1])), tasks)
    for task in layout.tasks(window, later):
        layout.skipped.append(f"{task.title}: {task.minutes} мин не влезают в день")
    if not weekend:
        layout.focus(focus_until, focus_max, starts)
    layout.blocks.sort(key=lambda block: block["start_at"])
    return layout.blocks, layout.skipped
