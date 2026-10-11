"""Недельный обзор: цифры по ISO-неделям (Пн-Вс) и дельты к предыдущей неделе. Выводов нет -
их делает агент (coach-week.md)."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach.load import daily_tss
from ai_coach.load.overload import MANUAL_HOURS, day_entries, hours
from ai_coach.load.thresholds import resolve_thresholds
from ai_coach.store.garmin_data import last_rest_hr, list_daily_metrics
from ai_coach.store.journal import list_wellbeing, wellbeing_day
from ai_coach.store.review import get_review
from ai_coach.workload.service import HOURS

SUNDAY = 6
DELTA_KEYS = (
    "tss",
    "total",
    "work_hours",
    "evening_hours",
    "weekend_work_hours",
    "todo_closed",
    "todo_open",
    "mood",
    "stress",
    "sleep",
    "readiness",
)


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_of_review(day: date) -> str:
    """Понедельник недели, которую обзор закрывает в этот день: в Пн - прошедшей, иначе текущей."""
    if day.weekday() == 0:
        day -= timedelta(days=7)
    return monday(day).isoformat()


def review_week(moment: datetime) -> str:
    """Неделя обзора на момент; день считается как у coach feel (до 04:00 - вчера)."""
    return week_of_review(date.fromisoformat(wellbeing_day(moment)))


def review_due(conn: sqlite3.Connection, day: str) -> bool:
    """Обзор пора проводить: day (день самочувствия) - Вс или Пн, и записи за неделю нет."""
    current = date.fromisoformat(day)
    if current.weekday() not in (0, SUNDAY):
        return False
    return get_review(conn, week_of_review(current)) is None


def _tss(conn: sqlite3.Connection, start: str, end: str) -> dict[str, float] | None:
    """TSS по дням; нет пульса покоя - None (TSS недели неизвестен)."""
    found = last_rest_hr(conn, end)
    if found is None:
        return None
    rest_hr = found[1]
    thresholds = resolve_thresholds(conn, end)
    lthr = {sport: t["lthr"] for sport, t in thresholds.items() if t["lthr"] > rest_hr}
    return daily_tss(conn, start, end, rest_hr, lthr)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _has_data(day: dict[str, Any]) -> bool:
    """В дне есть хоть что-то: тренировка, календарь, ручные часы, счётчики туду."""
    manual = [day[f"manual_{kind}"] is not None for kind in MANUAL_HOURS]
    calendar = [day[f"{kind}_hours"] for kind in HOURS]
    counters = [day["todo_closed"] is not None, day["todo_open"] is not None]
    return bool(day["tss"] or any(manual) or any(calendar) or any(counters))


def _wellbeing(conn: sqlite3.Connection, start: str, end: str) -> dict[str, dict[str, Any]]:
    """mood и stress по дням: последнее заданное за день."""
    found: dict[str, dict[str, Any]] = {}
    for mark in list_wellbeing(conn, start, end):
        for key in ("mood", "stress"):
            if mark[key] is not None:
                found.setdefault(mark["date"], {})[key] = mark[key]
    return found


def _delta(week: dict[str, Any], before: dict[str, Any]) -> dict[str, float | None]:
    """Разница недели с предыдущей; нет значения в одной из них - None."""
    return {
        key: round(week[key] - before[key], 2)
        if week[key] is not None and before[key] is not None
        else None
        for key in DELTA_KEYS
    }


def _week(
    first: date,
    today: date,
    days: dict[str, dict[str, Any]],
    has_tss: bool,
    wellbeing: dict[str, dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    keys = [(first + timedelta(days=i)).isoformat() for i in range(7)]
    past = [k for k in keys if k <= today.isoformat()]
    rows = [days[k] for k in past]
    opened = [d["todo_open"] for d in rows if d["todo_open"] is not None]
    counted = [
        k for k, d in zip(past, rows, strict=True) if _has_data(d) or k in wellbeing or k in metrics
    ]

    def average(source: dict[str, dict[str, Any]], key: str) -> float | None:
        return _mean([source[k][key] for k in past if source.get(k, {}).get(key) is not None])

    return {
        "week_start": keys[0],
        "week_end": keys[-1],
        "partial": keys[-1] > today.isoformat(),
        "tss": round(sum(d["tss"] for d in rows), 1) if has_tss else None,
        "total": round(sum(d["total"] for d in rows), 2),
        "work_hours": round(sum(hours(d, "work_hours") for d in rows), 2),
        "evening_hours": round(sum(d["work_evening_hours"] for d in rows), 2),
        "weekend_work_hours": round(sum(hours(d, "work_hours") for d in rows if d["weekend"]), 2),
        "todo_closed": sum(d["todo_closed"] or 0 for d in rows),
        "todo_open": opened[-1] if opened else None,
        "mood": average(wellbeing, "mood"),
        "stress": average(wellbeing, "stress"),
        "sleep": average(metrics, "sleep_score"),
        "readiness": average(metrics, "readiness_score"),
        "days_with_data": len(counted),
    }


def weekly_review(
    conn: sqlite3.Connection,
    today: str | date,
    weeks: int = 4,
    tss: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Последние weeks ISO-недель (последняя - текущая, partial) от старой к новой. Поля недели:
    week_start, week_end, partial, tss, total (сумма total_load дней), work_hours (ручные часы
    главнее календарных), evening_hours, weekend_work_hours, todo_closed, todo_open (последний
    снимок недели), mood, stress (среднее последних за день), sleep (sleep_score), readiness
    (средние; None - данных нет), days_with_data, delta - разница числовых полей с предыдущей
    неделей (у первой недели delta - None, где нет данных - None в значении). tss по дням можно
    передать, иначе считается из активностей (нет пульса покоя - tss недель None)."""
    current = date.fromisoformat(today) if isinstance(today, str) else today
    first = monday(current) - timedelta(days=7 * (weeks - 1))
    start, end = first.isoformat(), current.isoformat()
    if tss is None:
        tss = _tss(conn, start, end)
    has_tss = tss is not None
    days = {d["date"]: d for d in day_entries(conn, start, end, tss or {})}
    wellbeing = _wellbeing(conn, start, end)
    metrics = {m["date"]: m for m in list_daily_metrics(conn, start, end)}
    result: list[dict[str, Any]] = []
    for number in range(weeks):
        week = _week(first + timedelta(days=7 * number), current, days, has_tss, wellbeing, metrics)
        week["delta"] = _delta(week, result[-1]) if result else None
        result.append(week)
    return result
