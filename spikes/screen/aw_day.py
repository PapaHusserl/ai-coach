"""Спайк экранного времени, фаза Б: итоги дня из ActivityWatch. Одноразовый код, не продакшен.

Запуск: uv run python spikes/screen/aw_day.py --date 2026-10-18 [--apps]
Окна ∩ not-afk, слияние по app; категории по spikes/out/screen_rules.toml (work/hobby/браузер/
unmarked — неразмеченное). В stdout только минуты и доли. --apps печатает названия приложений
в терминал (для правки правил); --titles APP — заголовки окон APP (топ-40), тоже только в tty
(иначе exit 1); в файлы ничего не пишется. Приложения из [title.<app>] делит на work/hobby
сам aw-server по regex на заголовок; скрипт читает из ответа только app и категорию.
"""

import argparse
import sys
from datetime import date, datetime, time, timedelta

from common import (
    by_category,
    day_bounds,
    load_rules,
    say,
    screen_seconds,
    title_seconds,
    title_split,
)

EVENING_FROM = time(19, 0)
EVENING_TO = time(4, 0)  # следующего дня
TOLERANCE_S = 60  # допуск сверки часов с итогами
ORDER = ("work", "hobby", "browser", "unmarked")


def fmt(cats: dict[str, float]) -> str:
    total = sum(cats.values())
    parts = ", ".join(f"{k}={cats[k] / 60:.0f}м" for k in ORDER)
    unmarked = cats["unmarked"] / total * 100 if total else 0
    browser = cats["browser"] / total * 100 if total else 0
    return f"всего {total / 60:.0f}м ({parts}); браузер {browser:.0f}%, unmarked {unmarked:.0f}%"


def fmt_title(split: dict[str, float]) -> str:
    total = sum(split.values())
    share = split["none"] / total * 100 if total else 0
    return (
        f"по заголовку: work={split['work'] / 60:.0f}м, hobby={split['hobby'] / 60:.0f}м, "
        f"без правила={split['none'] / 60:.0f}м ({share:.0f}%)"
    )


def hour_at(day: date, h: int) -> datetime:
    """Начало часа h (0..28) от полуночи дня, по местному времени (DST учтён)."""
    return datetime.combine(day + timedelta(days=h // 24), time(h % 24)).astimezone()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--apps", action="store_true", help="названия приложений — в терминал")
    parser.add_argument("--titles", metavar="APP", help="заголовки окон APP — в терминал")
    args = parser.parse_args()
    if (args.apps or args.titles) and not sys.stdout.isatty():
        print("--apps/--titles — только в терминал (stdout не tty)")
        sys.exit(1)

    rules = load_rules()
    day = args.date
    day_start, day_end = day_bounds(day)
    ev_start = datetime.combine(day, EVENING_FROM).astimezone()
    ev_end = datetime.combine(day + timedelta(days=1), EVENING_TO).astimezone()
    # почасово: 24 часа дня + 4 часа после полуночи (хвост вечера)
    hours = [(hour_at(day, h), hour_at(day, h + 1)) for h in range(28)]
    periods = [(day_start, day_end), (ev_start, ev_end), *hours]
    results = screen_seconds(periods, rules)

    # сверка: часы должны складываться в день и вечер, иначе границы не режутся
    hourly = [sum(r.values()) for r in results[2:]]
    day_gap = abs(sum(hourly[:24]) - sum(results[0].values()))
    evening_gap = abs(sum(hourly[19:]) - sum(results[1].values()))
    if day_gap > TOLERANCE_S or evening_gap > TOLERANCE_S:
        print(f"границы не режутся: расхождение день {day_gap:.0f} с, вечер {evening_gap:.0f} с")
        sys.exit(1)

    titled = rules.get("title", {})
    if titled:
        say(f"правил по заголовку: {len(titled)} app")
    for name, per_app in (("день 00:00–24:00", results[0]), ("вечер 19:00–04:00", results[1])):
        say(f"{day}: {name}: {fmt(by_category(per_app, rules))}")
        if titled:
            say(f"{day}: {name}: {fmt_title(title_split(per_app, rules))}")
    for n, per_app in enumerate(results[2:]):
        if not per_app:
            continue
        label = f"{n:02d}" if n < 24 else f"{n - 24:02d}+1"
        say(f"  час {label}: {fmt(by_category(per_app, rules))}")

    if args.apps:
        per_name: dict[str, float] = {}
        for (app, _), sec in results[0].items():
            per_name[app] = per_name.get(app, 0) + sec
        print("--- приложения за день (только терминал, не копировать в репо) ---")
        for app, sec in sorted(per_name.items(), key=lambda kv: -kv[1]):
            print(f"{sec / 60:6.0f}м  {app}")

    if args.titles:
        print(f"--- заголовки окон {args.titles} (только терминал, не копировать в репо) ---")
        for sec, title in title_seconds((day_start, day_end), args.titles, rules):
            print(f"{sec / 60:6.0f}м  {title[:100]}")


if __name__ == "__main__":
    main()
