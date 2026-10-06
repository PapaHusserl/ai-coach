"""Проверка 4. Силовая на часы: загрузка, планирование на дату, (опц.) push.

Запуск: ! uv run python spikes/garmin/strength.py [--date YYYY-MM-DD] [--push]
Каждое действие на Garmin - после y/N. Название с префиксом SPIKE.
"""

import argparse
from datetime import date, timedelta

import workouts
from common import load_client, upload_and_schedule

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--date", default=(date.today() + timedelta(days=1)).isoformat())
parser.add_argument("--push", action="store_true")
args = parser.parse_args()
upload_and_schedule(load_client(), workouts.strength(), args.date, args.push)
