"""Спайк экранного времени, фаза Б: экранное work против ручных часов и календаря. Не продакшен.

Запуск: uv run python spikes/screen/aw_compare.py --days 7
Только чтение: coach.db открывается read-only, миграции не применяются. Все три источника
считаются по дню 04:00→04:00, как ручные часы; календарные часы — из событий coach.db, события
режутся по границам дня (правила как в workload.service, его хелперы переиспользованы).
Сегодня в сравнение не входит, последний день — вчера. Печатает часы по дням:
экран work (без браузера), экран work+браузер (верхняя оценка), ручные `coach feel --work`,
календарь work; дельты экран−ручные и экран−календарь. Без названий приложений и событий.
"""

import argparse
import sqlite3
import sys
from datetime import date, datetime, time, timedelta
from typing import Any

from common import by_category, day_bounds, load_rules, say, screen_seconds

from ai_coach.store.db import db_path
from ai_coach.store.workload import list_calendar_events, list_counters
from ai_coach.workload.service import _clip, _counted, _hours

DAY_FROM_HOUR = 4  # день 04:00→04:00, как у ручных часов (до 04:00 — вчера)
TOLERANCE_H = 1.0  # критерий «годится»: ±1 ч в будни
LIMIT_H = 2.0  # «не годится», если регулярно больше


def fmt(value: float | None) -> str:
    return f"{'—':>7}" if value is None else f"{value:7.1f}"


def calendar_work_hours(events: list[dict[str, Any]], day: date) -> float:
    """Часы work из календаря за день 04:00→04:00: те же правила, что в workload.service
    (не отменённые и не отклонённые, без all-day, пересечения объединяются), событие режется
    по границам дня."""
    first = datetime.combine(day, time(DAY_FROM_HOUR))
    last = first + timedelta(days=1)
    mine = [e for e in events if _counted(e) and not e["all_day"] and e["category"] == "work"]
    return _hours([s for e in mine if (s := _clip(e, first, last))])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    path = db_path()
    if not path.exists():
        print("нет coach.db")
        sys.exit(1)

    end = date.today() - timedelta(days=1)  # сегодняшний день ещё не закончен
    start = end - timedelta(days=args.days - 1)
    rules = load_rules()
    days = [start + timedelta(days=i) for i in range(args.days)]
    screen = screen_seconds([day_bounds(d, DAY_FROM_HOUR) for d in days])

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        manual = {
            c["date"]: c["value"]
            for c in list_counters(conn, start.isoformat(), end.isoformat(), "work_hours")
        }
        # событие, начатое накануне, может заходить в день; начатое в конце дня end — в следующий
        found = list_calendar_events(
            conn, (start - timedelta(days=1)).isoformat(), (end + timedelta(days=1)).isoformat()
        )
        calendar = {d.isoformat(): calendar_work_hours(found, d) for d in days}
    finally:
        conn.close()

    say(
        f"{'дата':5}  {'день':5}  {'экран':>7}  {'+брауз':>7}  {'ручные':>7}  {'календ':>7}  "
        f"{'Δручные':>7}  {'Δкаленд':>7}"
    )
    off_manual = []  # будни с ручными часами: |Δ| для итога
    for d, per_app in zip(days, screen, strict=True):
        cats = by_category(per_app, rules)
        work = cats["work"] / 3600
        upper = work + cats["browser"] / 3600
        hand = manual.get(d.isoformat())
        cal = calendar.get(d.isoformat())
        d_hand = None if hand is None else work - hand
        d_cal = None if cal is None else work - cal
        weekday = d.weekday() < 5
        if weekday and d_hand is not None:
            off_manual.append(abs(d_hand))
        say(
            f"{d:%m-%d}  {'будни' if weekday else 'вых. '}  {fmt(work)}  {fmt(upper)}  "
            f"{fmt(hand)}  {fmt(cal)}  {fmt(d_hand)}  {fmt(d_cal)}"
        )

    if not off_manual:
        say("итог: будней с ручными часами нет — сравнивать не с чем")
        return
    over1 = sum(1 for x in off_manual if x > TOLERANCE_H)
    over2 = sum(1 for x in off_manual if x > LIMIT_H)
    say(
        f"итог (будни с ручными часами, {len(off_manual)} дн): средний |Δ| "
        f"{sum(off_manual) / len(off_manual):.1f} ч, > {TOLERANCE_H:.0f} ч: {over1}, "
        f"> {LIMIT_H:.0f} ч: {over2}"
    )


if __name__ == "__main__":
    main()
