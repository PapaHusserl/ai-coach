"""Переключения и длинные отрезки по ленте окон (шаг Н8).

Лента - список (начало, конец, класс окна): классы work, challenge, hindrance, hobby, browser,
unmarked. Чистый счёт: названий приложений и заголовков здесь нет.
"""

from datetime import date, datetime
from typing import Any

SOURCE = "screen"
Segment = tuple[datetime, datetime, str]

MIN_EVENT_SECONDS = 5  # окно короче - мимолётный фокус, переходом не считается
MIN_ACTIVE_HOURS = 1  # при меньшем экране число в час шумит
PAUSE_MINUTES = 5  # пауза от этого значения рвёт рабочий отрезок
WORK_CLASSES = ("work", "challenge", "hindrance")
SECONDS_IN_HOUR = 3600


def _seconds(segment: Segment) -> float:
    return (segment[1] - segment[0]).total_seconds()


def switch_rate(segments: list[Segment]) -> float | None:
    """Переходы между соседними отрезками разных классов (не короче MIN_EVENT_SECONDS) в час
    активного экрана (сумма длительностей всех отрезков); экрана меньше MIN_ACTIVE_HOURS - None."""
    active = sum(_seconds(s) for s in segments)
    if active < MIN_ACTIVE_HOURS * SECONDS_IN_HOUR:
        return None
    classes = [s[2] for s in segments if _seconds(s) >= MIN_EVENT_SECONDS]
    changes = sum(a != b for a, b in zip(classes, classes[1:], strict=False))
    return round(changes / (active / SECONDS_IN_HOUR), 1)


def counter_row(day: date, kind: str, value: float) -> dict[str, Any]:
    """Строка для upsert_counter: счётчик экрана за день."""
    return {
        "date": day.isoformat(),
        "kind": kind,
        "value": value,
        "source": SOURCE,
        "raw_json": None,
    }


def timeline_rows(day: date, segments: list[Segment]) -> list[dict[str, Any]]:
    """screen_stretch_hours и (экрана хватает) screen_switches_hour; пустая лента - ничего."""
    if not segments:
        return []
    rows = [counter_row(day, "screen_stretch_hours", longest_stretch(segments))]
    rate = switch_rate(segments)
    if rate is not None:
        rows.append(counter_row(day, "screen_switches_hour", rate))
    return rows


def longest_stretch(segments: list[Segment]) -> float:
    """Самый длинный рабочий отрезок в часах: рабочие окна склеиваются, пока промежуток между
    ними короче PAUSE_MINUTES; длина - от начала первого до конца последнего. Нет работы - 0."""
    best = 0.0
    first = last = None
    for start, end, cls in sorted(segments, key=lambda s: s[0]):
        if cls not in WORK_CLASSES:
            continue
        if last is not None and (start - last).total_seconds() >= PAUSE_MINUTES * 60:
            first = last = None
        if first is None:
            first = start
        last = max(last, end) if last is not None else end
        best = max(best, (last - first).total_seconds())
    return round(best / SECONDS_IN_HOUR, 2)
