"""Спайк экранного времени, фаза Б: итоги дня из ActivityWatch. Одноразовый код, не продакшен.

Запуск: uv run python spikes/screen/aw_day.py --date 2026-10-18 [--apps]
Окна ∩ not-afk, слияние по app; категории по spikes/out/screen_rules.toml (work/hobby/браузер/
unmarked — неразмеченное). В stdout только минуты и доли. --apps печатает названия приложений
в терминал (для правки правил); в файлы ничего не пишется.
"""

import argparse
import sys
from datetime import date, datetime, time, timedelta

from common import by_category, day_bounds, load_rules, say, screen_seconds

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


def hour_at(day: date, h: int) -> datetime:
    """Начало часа h (0..28) от полуночи дня, по местному времени (DST учтён)."""
    return datetime.combine(day + timedelta(days=h // 24), time(h % 24)).astimezone()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--apps", action="store_true", help="названия приложений — в терминал")
    args = parser.parse_args()

    rules = load_rules()
    day = args.date
    day_start, day_end = day_bounds(day)
    ev_start = datetime.combine(day, EVENING_FROM).astimezone()
    ev_end = datetime.combine(day + timedelta(days=1), EVENING_TO).astimezone()
    # почасово: 24 часа дня + 4 часа после полуночи (хвост вечера)
    hours = [(hour_at(day, h), hour_at(day, h + 1)) for h in range(28)]
    periods = [(day_start, day_end), (ev_start, ev_end), *hours]
    results = screen_seconds(periods)

    # сверка: часы должны складываться в день и вечер, иначе границы не режутся
    hourly = [sum(r.values()) for r in results[2:]]
    day_gap = abs(sum(hourly[:24]) - sum(results[0].values()))
    evening_gap = abs(sum(hourly[19:]) - sum(results[1].values()))
    if day_gap > TOLERANCE_S or evening_gap > TOLERANCE_S:
        print(f"границы не режутся: расхождение день {day_gap:.0f} с, вечер {evening_gap:.0f} с")
        sys.exit(1)

    say(f"{day}: день 00:00–24:00: {fmt(by_category(results[0], rules))}")
    say(f"{day}: вечер 19:00–04:00: {fmt(by_category(results[1], rules))}")
    for n, per_app in enumerate(results[2:]):
        if not per_app:
            continue
        label = f"{n:02d}" if n < 24 else f"{n - 24:02d}+1"
        say(f"  час {label}: {fmt(by_category(per_app, rules))}")

    if args.apps:
        print("--- приложения за день (только терминал, не копировать в репо) ---")
        for app, sec in sorted(results[0].items(), key=lambda kv: -kv[1]):
            print(f"{sec / 60:6.0f}м  {app}")


if __name__ == "__main__":
    main()
