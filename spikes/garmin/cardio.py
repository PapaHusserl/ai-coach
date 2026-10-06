"""Проверка 6. Бег / вело / плавание: по одной простой структурированной тренировке.

Запуск: ! uv run python spikes/garmin/cardio.py --kind run|bike|swim|all [--date ...] [--push]
"""

import argparse
from datetime import date, timedelta

import workouts
from common import load_client, upload_and_schedule

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--kind", choices=["run", "bike", "swim", "all"], required=True)
parser.add_argument("--date", default=(date.today() + timedelta(days=1)).isoformat())
parser.add_argument("--push", action="store_true")
args = parser.parse_args()
builders = {"run": workouts.running, "bike": workouts.cycling, "swim": workouts.swimming}
kinds = list(builders) if args.kind == "all" else [args.kind]
client = load_client()
for kind in kinds:
    upload_and_schedule(client, builders[kind](), args.date, args.push)
