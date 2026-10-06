"""Проверка 2. Метрики за 30 дней: сон, HRV, Body Battery, стресс, Training Readiness.

Запуск: ! uv run python spikes/garmin/metrics.py [--days 30]
Сырьё в spikes/out/metrics_*.json. В консоль - только имена полей и сколько дней заполнено.
"""

import argparse
import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from common import load_client, save_json


def is_empty(value: Any) -> bool:
    return value is None or value == [] or value == {} or value == ""


def field_report(name: str, days: dict[str, Any]) -> None:
    """Печатает по ключам верхнего уровня, в скольких днях они непустые. Значений нет."""
    errors = [d for d, v in days.items() if isinstance(v, dict) and "_error" in v]
    ok = {d: v for d, v in days.items() if d not in errors}
    nonempty = [d for d, v in ok.items() if not is_empty(v)]
    print(f"\n== {name}: дней {len(days)}, с данными {len(nonempty)}, ошибок {len(errors)}")
    if errors:
        print("  типы ошибок:", sorted({days[d]["_error"] for d in errors}))
    counts: dict[str, int] = {}
    for value in nonempty:
        rows = value if isinstance(value, list) else [value]
        for row in rows[:1]:
            if isinstance(row, dict):
                for key, item in row.items():
                    counts[key] = counts.get(key, 0) + (0 if is_empty(item) else 1)
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}/{len(nonempty)}")


def collect(fetch: Callable[[str], Any], dates: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for day in dates:
        try:
            result[day] = fetch(day)
        except Exception as e:
            result[day] = {"_error": type(e).__name__, "_msg": str(e)[:200]}
        time.sleep(0.5)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    client = load_client()
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(args.days)]
    fetchers: dict[str, Callable[[str], Any]] = {
        "sleep": client.get_sleep_data,
        "hrv": client.get_hrv_data,
        "stress": client.get_stress_data,
        "body_battery": lambda d: client.get_body_battery(d),
        "training_readiness": client.get_training_readiness,
    }
    for name, fetch in fetchers.items():
        data = collect(fetch, dates)
        save_json(f"metrics_{name}.json", data)
        field_report(name, data)
    print("\nСырьё: spikes/out/metrics_*.json. Пустые поля / пейволл смотри по ошибкам выше.")


main()
