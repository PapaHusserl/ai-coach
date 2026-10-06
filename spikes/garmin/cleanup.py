"""Проверка 7. Удаление тестовых тренировок (только с префиксом SPIKE) из Garmin Connect.

Запуск: ! uv run python spikes/garmin/cleanup.py
Сначала снимает запланированные в календаре, потом удаляет шаблоны. Каждое - после y/N.
"""

import argparse
import json
from datetime import date
from typing import Any

from common import OUT, PREFIX, confirm, load_client, save_json
from garminconnect import Garmin


def spike_templates(client: Garmin) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for start in range(0, 300, 100):
        items += client.get_workouts(start, 100)
    return [w for w in items if str(w.get("workoutName", "")).startswith(PREFIX)]


def spike_calendar(client: Garmin) -> list[dict[str, Any]]:
    path = OUT / "uploaded.json"
    entries = json.loads(path.read_text()) if path.exists() else []
    months = {tuple(map(int, e["date"].split("-")[:2])) for e in entries if e.get("date")}
    months = months or {(date.today().year, date.today().month)}
    found: list[dict[str, Any]] = []
    for year, month in sorted(months):
        data = client.get_scheduled_workouts(year, month) or {}
        items = data.get("calendarItems", [])
        found += [i for i in items if str(i.get("title", "")).startswith(PREFIX)]
    return found


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    client = load_client()
    calendar = spike_calendar(client)
    save_json("cleanup_calendar_before.json", calendar)
    print(f"В календаре SPIKE-записей: {len(calendar)}")
    for item in calendar:
        print(f"  calendar id={item.get('id')} date={item.get('date')} title={item.get('title')}")
    if calendar and confirm("Снять эти записи из календаря (unschedule)"):
        for item in calendar:
            client.unschedule_workout(item["id"])
        print("Снято.")
    templates = spike_templates(client)
    print(f"Шаблонов SPIKE в библиотеке: {len(templates)}")
    for w in templates:
        print(f"  workoutId={w['workoutId']} {w['workoutName']}")
    if templates and confirm("Удалить эти шаблоны (delete_workout)"):
        for w in templates:
            client.delete_workout(w["workoutId"])
        print("Удалено.")
    left_templates = len(spike_templates(client))
    print(f"Осталось: шаблонов {left_templates}, в календаре {len(spike_calendar(client))}")
    print("Проверь на часах/в приложении после синхронизации, что тренировок SPIKE нет.")


main()
