"""Решения на будущее: часть дня по часам; пункты очереди на черновик и фазу (track, settle).
Commit делает вызывающий код."""

import sqlite3
from datetime import datetime, time
from typing import Any

from ai_coach.store.decisions import (
    add_decision,
    close_decision,
    open_by_ref,
    open_decisions,
    to_check_decisions,
)
from ai_coach.store.journal import EVENING_CUTOFF
from ai_coach.workload.service import EVENING_FROM

MORNING_UNTIL = time(12, 0)


def day_part(moment: datetime) -> str:
    """Часть дня: morning до 12:00, day до EVENING_FROM, evening до EVENING_CUTOFF."""
    clock = moment.time()
    if clock < EVENING_CUTOFF or clock >= EVENING_FROM:
        return "evening"
    return "morning" if clock < MORNING_UNTIL else "day"


PENDING_FIELDS = ("id", "kind", "ref_id", "text", "target_date", "created_at")
CHECK_FIELDS = ("id", "text", "target_date", "decided_at")
PARTS = ("morning", "day", "evening")


def pending(conn: sqlite3.Connection, day: str) -> dict[str, list[dict[str, Any]]]:
    """pending - открытые пункты (ближайший день, без даты в конце); to_check - слова,
    принятые «да», срок которых прошёл, а исполнение не отмечено."""
    return {
        "pending": [{k: row[k] for k in PENDING_FIELDS} for row in open_decisions(conn)],
        "to_check": [{k: row[k] for k in CHECK_FIELDS} for row in to_check_decisions(conn, day)],
    }


def decision_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Счётчики по части дня решения (decided_at): yes, no, dropped, kept, missed. Строки -
    с decided_at и result (тренировки - уже из плана/факта); открытые пропускаются."""
    keys = ("yes", "no", "dropped", "kept", "missed")
    stats = {part: {key: 0 for key in keys} for part in PARTS}
    for row in rows:
        if row["decided_at"] is None:
            continue
        counts = stats[day_part(datetime.fromisoformat(row["decided_at"]))]
        counts[row["status"]] += 1
        if row["result"] is not None:
            counts[row["result"]] += 1
    return stats


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
