"""Проверка 5. Растяжка на часы. Тип спорта выбирается, чтобы найти принимаемый FR970.

Запуск в обычном терминале (спрашивает y/N):
  uv run python spikes/garmin/stretch.py --sport mobility [--date YYYY-MM-DD] [--push] [--named]
--sport: yoga | mobility | other | pilates. Пробуй по одному, смотри что видно на часах.
"""

import argparse
from datetime import date, timedelta

import workouts
from common import load_client, upload_and_schedule

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--sport", choices=list(workouts.SPORTS), required=True)
parser.add_argument("--date", default=(date.today() + timedelta(days=1)).isoformat())
parser.add_argument("--push", action="store_true")
parser.add_argument("--named", action="store_true", help="упражнения из каталога Garmin в шагах")
args = parser.parse_args()
workout = workouts.stretch(args.sport, named=args.named)
upload_and_schedule(load_client(), workout, args.date, args.push)
