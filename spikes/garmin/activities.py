"""Проверка 3. Активности за 30 дней, подходы/повторы/веса у силовой.

Запуск: ! uv run python spikes/garmin/activities.py [--days 30] [--fit]
--fit дополнительно скачивает оригинал (zip с FIT) последней активности в spikes/out/.
"""

import argparse
from collections import Counter
from datetime import date, timedelta
from typing import Any

from common import OUT, load_client, save_json
from garminconnect import Garmin


def strength_report(client: Garmin, activity_id: int) -> None:
    sets = client.get_activity_exercise_sets(activity_id)
    save_json(f"activity_sets_{activity_id}.json", sets)
    rows = sets.get("exerciseSets") or []
    print(f"  exerciseSets: {len(rows)}")
    keys = Counter(key for row in rows for key, item in row.items() if item not in (None, [], 0))
    print("  ключи подходов (сколько подходов с непустым):", dict(keys))
    active = [row for row in rows if row.get("setType") == "ACTIVE"]
    with_reps = sum(1 for r in active if r.get("repetitionCount"))
    with_weight = sum(1 for r in active if r.get("weight"))
    print(f"  ACTIVE-подходов {len(active)}, с reps {with_reps}, с weight {with_weight}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--fit", action="store_true")
    args = parser.parse_args()
    client = load_client()
    start = (date.today() - timedelta(days=args.days)).isoformat()
    raw: Any = client.get_activities_by_date(start, date.today().isoformat())
    save_json("activities_list.json", raw)
    print(f"Активностей за {args.days} дн.: {len(raw)}")
    types = Counter(a.get("activityType", {}).get("typeKey") for a in raw)
    print("По типам:", dict(types))
    strength = [a for a in raw if a.get("activityType", {}).get("typeKey") == "strength_training"]
    print(f"Силовых: {len(strength)} (разбираем до 3)")
    for activity in strength[:3]:
        print(f"- активность {activity['activityId']}")
        strength_report(client, activity["activityId"])
    if args.fit and raw:
        activity_id = max(raw, key=lambda a: a["startTimeLocal"])["activityId"]
        data = client.download_activity(activity_id, Garmin.ActivityDownloadFormat.ORIGINAL)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"activity_{activity_id}_original.zip").write_bytes(data)
        print(f"Оригинал (FIT в zip) скачан, {len(data)} байт")


main()
