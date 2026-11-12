"""Решения на будущее: часть дня по часам; пункты очереди на черновик и фазу (track, settle).
Commit делает вызывающий код."""

import sqlite3
from datetime import datetime, time

from ai_coach.store.decisions import add_decision, close_decision, open_by_ref
from ai_coach.store.journal import EVENING_CUTOFF
from ai_coach.workload.service import EVENING_FROM

MORNING_UNTIL = time(12, 0)


def day_part(moment: datetime) -> str:
    """Часть дня: morning до 12:00, day до EVENING_FROM, evening до EVENING_CUTOFF."""
    clock = moment.time()
    if clock < EVENING_CUTOFF or clock >= EVENING_FROM:
        return "evening"
    return "morning" if clock < MORNING_UNTIL else "day"


def _stamp() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def track(
    conn: sqlite3.Connection, kind: str, ref_id: int, text: str, target_date: str | None
) -> int:
    """Открытый пункт очереди на черновик тренировки (workout) или фазу (phase)."""
    values = {
        "kind": kind,
        "ref_id": ref_id,
        "text": text,
        "target_date": target_date,
        "created_at": _stamp(),
    }
    return add_decision(conn, values)


def settle(conn: sqlite3.Connection, kind: str, ref_id: int, status: str) -> bool:
    """Закрывает открытый пункт объекта (yes | no | dropped); открытого нет — False."""
    item = open_by_ref(conn, kind, ref_id)
    return item is not None and close_decision(conn, item["id"], status, _stamp())
