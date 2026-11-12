"""Решения на будущее: часть дня по часам. Ничего не пишет в базу."""

from datetime import datetime, time

from ai_coach.store.journal import EVENING_CUTOFF
from ai_coach.workload.service import EVENING_FROM

MORNING_UNTIL = time(12, 0)


def day_part(moment: datetime) -> str:
    """Часть дня: morning до 12:00, day до EVENING_FROM, evening до EVENING_CUTOFF."""
    clock = moment.time()
    if clock < EVENING_CUTOFF or clock >= EVENING_FROM:
        return "evening"
    return "morning" if clock < MORNING_UNTIL else "day"
