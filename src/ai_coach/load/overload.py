"""Общая нагрузка дня и сигналы перегруза (подступающее выгорание).

Веса и пороги - константы и пока догадка: калибруются по 2-3 неделям данных, меняются только
они. Формула - в docs/architecture.md (раздел v2.2+v2.3).

total_load = W_TSS * tss + W_WORK * work + W_HOBBY * hobby + W_EVENING * work_evening
             + W_WEEKEND * work (в сб/вс) + W_TODO * todo_closed + W_GROOMING * grooming_done.
Ручные часы дня (manual_work_hours, manual_hobby_hours) главнее часов экрана
(screen_work_hours, screen_hobby_hours), экран - часов календаря.
"""

import sqlite3
from datetime import date, timedelta
from typing import Any

from ai_coach.store.garmin_data import list_daily_metrics
from ai_coach.store.journal import list_wellbeing
from ai_coach.store.workload import list_counters
from ai_coach.workload import workload_series

W_TSS = 0.05
W_WORK = 1.0
W_HOBBY = 0.5
W_EVENING = 0.5
W_WEEKEND = 0.5
W_TODO = 0.2
W_GROOMING = 0.5
TOTAL_HIGH = 10.0
TOTAL_STREAK_DAYS = 3
EVENING_STREAK_DAYS = 3
WEEKEND_WORK_MIN = 1.0
READINESS_DROP = 10
MOOD_DROP = 1.0
STRESS_RISE = 1.0
# (ключ строки, ключ в ответе, знак падения, порог)
RECOVERY_SIGNS = (
    ("readiness_score", "readiness", 1, READINESS_DROP),
    ("mood", "mood", 1, MOOD_DROP),
    ("stress", "stress", -1, STRESS_RISE),
)
RECOVERY_RECENT_DAYS = 3
RECOVERY_BASELINE_DAYS = 7
RECOVERY_MIN_RECENT = 2
RECOVERY_MIN_BASELINE = 3
TODO_GROWTH_MIN = 5
OVERLOAD_DAYS = 7
METRICS_DAYS = RECOVERY_RECENT_DAYS + RECOVERY_BASELINE_DAYS
MANUAL_HOURS = ("work_hours", "hobby_hours", "rest_hours")
SCREEN_HOURS = ("screen_work_hours", "screen_hobby_hours")


def hours(day: dict[str, Any], key: str) -> float:
    """Часы дня: ручные (manual_<key>) главнее экрана (screen_<key>), экран - календарных (<key>);
    нет данных - 0. Ноль ручных или экрана - значение, а не отсутствие."""
    manual = day.get(f"manual_{key}")
    screen = day.get(f"screen_{key}")
    return manual if manual is not None else (screen if screen is not None else (day.get(key) or 0))


def total_load(day: dict[str, Any]) -> float:
    """Общая нагрузка дня одним числом. Ключи дня (нет или None - 0): tss, work_hours,
    hobby_hours, work_evening_hours, weekend, todo_closed, grooming_done и ручные
    manual_work_hours, manual_hobby_hours (заданные заменяют экранные и календарные, 0 тоже) и
    screen_work_hours, screen_hobby_hours (заданные заменяют календарные, 0 тоже)."""
    work = hours(day, "work_hours")
    total = (
        W_TSS * (day.get("tss") or 0)
        + W_WORK * work
        + W_HOBBY * hours(day, "hobby_hours")
        + W_EVENING * (day.get("work_evening_hours") or 0)
        + W_TODO * (day.get("todo_closed") or 0)
        + W_GROOMING * (day.get("grooming_done") or 0)
    )
    if day.get("weekend"):
        total += W_WEEKEND * work
    return round(total, 2)


def overloaded(day: dict[str, Any]) -> bool:
    """Нагрузка дня (total_load) не меньше TOTAL_HIGH."""
    return total_load(day) >= TOTAL_HIGH


def _streak(flags: list[bool]) -> int:
    """Сколько последних значений подряд True."""
    count = 0
    for flag in reversed(flags):
        if not flag:
            break
        count += 1
    return count


def _recovery_drop(metrics: list[dict[str, Any]], today: date) -> dict[str, float]:
    """Падение восстановления: среднее за RECOVERY_RECENT_DAYS последних дней против предыдущих
    RECOVERY_BASELINE_DAYS. Ключи: readiness (падение баллов), mood (падение), stress (рост) -
    только дошедшие до порога; данных мало (меньше RECOVERY_MIN_* значений) - ключа нет.
    Строки: date и любой из readiness_score, mood, stress."""
    found: dict[str, float] = {}
    for key, name, sign, limit in RECOVERY_SIGNS:
        recent: list[float] = []
        baseline: list[float] = []
        for row in metrics:
            value = row.get(key)
            age = (today - date.fromisoformat(row["date"])).days
            if value is None or age < 0:
                continue
            if age < RECOVERY_RECENT_DAYS:
                recent.append(value)
            elif age < METRICS_DAYS:
                baseline.append(value)
        if len(recent) < RECOVERY_MIN_RECENT or len(baseline) < RECOVERY_MIN_BASELINE:
            continue
        change = round(sign * (sum(baseline) / len(baseline) - sum(recent) / len(recent)), 1)
        if change >= limit:
            found[name] = change
    return found


def find_overload(
    days: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Сигналы перегруза на последний день списка days: дни по возрастанию даты без пропусков
    (ключи как у total_load плюс date, total и todo_open). metrics - строки по дням за
    METRICS_DAYS дней до последнего: date и readiness_score (daily_metrics) или mood и stress
    (самочувствие); нет ключа или None - нет данных. Пустой список - перегруза нет. Сигнал: kind,
    value, limit (у recovery_drop value и limit - словари по показателям)."""
    found: list[dict[str, Any]] = []
    total = _streak([d["total"] >= TOTAL_HIGH for d in days])
    if total >= TOTAL_STREAK_DAYS:
        found.append({"kind": "total_streak", "value": total, "limit": TOTAL_STREAK_DAYS})
    evening = _streak([(d.get("work_evening_hours") or 0) > 0 for d in days])
    if evening >= EVENING_STREAK_DAYS:
        found.append({"kind": "evening_streak", "value": evening, "limit": EVENING_STREAK_DAYS})
    weekend = round(sum(hours(d, "work_hours") for d in days if d.get("weekend")), 2)
    if weekend >= WEEKEND_WORK_MIN:
        found.append({"kind": "weekend_work", "value": weekend, "limit": WEEKEND_WORK_MIN})
    drop = _recovery_drop(metrics, date.fromisoformat(days[-1]["date"]))
    if drop:
        limits = {name: limit for _, name, _, limit in RECOVERY_SIGNS}
        found.append({"kind": "recovery_drop", "value": drop, "limit": limits})
    opened = [d["todo_open"] for d in days if d.get("todo_open") is not None]
    if len(opened) >= 2 and opened[-1] - opened[0] >= TODO_GROWTH_MIN:
        growth = opened[-1] - opened[0]
        found.append({"kind": "todo_growth", "value": growth, "limit": TODO_GROWTH_MIN})
    return found


def day_entries(
    conn: sqlite3.Connection, first: str, last: str, tss: dict[str, float]
) -> list[dict[str, Any]]:
    """Дни first..last включительно: workload_series, tss (нет дня - 0), ручные часы
    manual_work/hobby/rest_hours (None - не вводились) и total (total_load)."""
    manual: dict[tuple[str, str], float] = {}
    for kind in MANUAL_HOURS:
        for counter in list_counters(conn, first, last, kind):
            manual[(counter["date"], kind)] = counter["value"]
    days: list[dict[str, Any]] = []
    for row in workload_series(conn, first, last):
        entry = {**row, "tss": tss.get(row["date"], 0)}
        for kind in MANUAL_HOURS:
            entry[f"manual_{kind}"] = manual.get((row["date"], kind))
        entry["total"] = total_load(entry)
        days.append(entry)
    return days


def overload_report(conn: sqlite3.Connection, day: str, tss: dict[str, float]) -> dict[str, Any]:
    """Нагрузка за OVERLOAD_DAYS дней до day включительно и сигналы перегруза. tss - TSS
    тренировок по дням (нет дня - 0). Ответ: date, total (нагрузка day), days (date, total и
    ручные часы manual_work/hobby/rest_hours, None - не вводились, и часы экрана
    screen_work/hobby_hours, None - нет данных), signals (find_overload)."""
    last = date.fromisoformat(day)
    first = (last - timedelta(days=OVERLOAD_DAYS - 1)).isoformat()
    days = day_entries(conn, first, day, tss)
    start = (last - timedelta(days=METRICS_DAYS - 1)).isoformat()
    moods: dict[str, dict[str, Any]] = {}
    for mark in list_wellbeing(conn, start, day):
        for key in ("mood", "stress"):
            if mark[key] is not None:  # последнее заданное за день
                moods.setdefault(mark["date"], {"date": mark["date"]})[key] = mark[key]
    metrics = list_daily_metrics(conn, start, day) + list(moods.values())
    signals = find_overload(days, metrics)
    keys = (*(f"manual_{kind}" for kind in MANUAL_HOURS), *SCREEN_HOURS)
    shown = [{"date": d["date"], "total": d["total"], **{k: d[k] for k in keys}} for d in days]
    return {"date": day, "total": days[-1]["total"], "days": shown, "signals": signals}
