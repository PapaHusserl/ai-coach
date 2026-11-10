"""Шапка пульта: показатели дня, последний вес, состояние синка; запись веса (шаг П4, партия 3)."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach.store.garmin_data import get_daily_metrics, list_recovery_days
from ai_coach.store.journal import (
    MAX_WEIGHT_KG,
    MIN_WEIGHT_KG,
    add_weight,
    last_sync_log,
    list_weights,
)
from ai_coach.web import syncer
from ai_coach.web.errors import MarkError

WEIGHT_DAYS = 30
SECONDS_IN_HOUR = 3600


def _metrics(conn: sqlite3.Connection, day: str) -> dict[str, Any] | None:
    row = get_daily_metrics(conn, day)
    if row is None:
        return None
    seconds = row["sleep_seconds"]
    [recovery] = list_recovery_days(conn, day, day)
    return {
        "readiness": row["readiness_score"],
        "sleep_h": None if seconds is None else round(seconds / SECONDS_IN_HOUR, 1),
        "hrv": row["hrv_last_night"],
        "rhr": recovery["rhr"],
    }


def _weight(conn: sqlite3.Connection, day: date) -> dict[str, Any] | None:
    start = (day - timedelta(days=WEIGHT_DAYS)).isoformat()
    rows = list_weights(conn, start, day.isoformat())
    if not rows:
        return None
    return {"kg": rows[-1]["weight_kg"], "measured_at": rows[-1]["measured_at"]}


def header_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """weight (последняя за 30 дней до day), sync (последняя запись sync_log), metrics дня."""
    last = last_sync_log(conn)
    thread = syncer.status()
    failed = last["message"] if last and last["status"] != "ok" else None
    sync = {
        "finished_at": last["finished_at"] if last else None,
        "status": last["status"] if last else None,
        "running": thread["running"],
        "error": thread["error"] or failed,
    }
    return {"weight": _weight(conn, day), "sync": sync, "metrics": _metrics(conn, day.isoformat())}


def sync_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """GET /api/sync: состояние потока и последняя запись sync_log (day, now не нужны)."""
    last = last_sync_log(conn)
    keys = ("started_at", "finished_at", "status", "message")
    return syncer.status() | {"last": {k: last[k] for k in keys} if last else None}


def save_weight(conn: sqlite3.Connection, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Вес из пульта: kg - число или строка с запятой; measured_at - сейчас (Р3 = 1)."""
    raw = payload.get("kg")
    try:
        if isinstance(raw, bool) or raw is None:
            raise ValueError
        kg = float(str(raw).replace(",", "."))
    except ValueError:
        raise MarkError(f"Вес должен быть числом, получено: {raw!r}") from None
    if not MIN_WEIGHT_KG <= kg <= MAX_WEIGHT_KG:
        raise MarkError(f"Вес должен быть от {MIN_WEIGHT_KG} до {MAX_WEIGHT_KG} кг.")
    moment = now.isoformat(sep=" ", timespec="seconds")
    return {"id": add_weight(conn, {"measured_at": moment, "weight_kg": kg})}
