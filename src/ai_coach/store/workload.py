"""Нагрузка вне тренировок: calendar_events (окно заменяется) и day_counters (upsert)."""

import json
import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, upsert

CALENDAR_SOURCE = "apple_calendar"
COUNTER_KINDS = (
    "todo_open",
    "todo_closed",
    "grooming_done",
    "grooming_pending",
)


def _dumped(value: Any) -> str | None:
    """raw_json как в базе: объект -> JSON-строка."""
    return (
        json.dumps(value, ensure_ascii=False)
        if value is not None and not isinstance(value, str)
        else value
    )


def _same(old: dict[str, Any], new: dict[str, Any]) -> bool:
    """Запись не изменилась (метка synced_at не в счёт)."""
    return all(old[k] == v for k, v in new.items() if k != "synced_at")


def replace_calendar_window(
    conn: sqlite3.Connection, date_from: str, date_to: str, events: list[dict[str, Any]]
) -> None:
    """Заменяет события с date от date_from до date_to включительно: пришедшие пишутся, исчезнувшие
    удаляются, остальные дни не трогаются. events: uid, date, start_at, end_at, all_day, calendar,
    category, synced_at; не обязательно source (по умолчанию apple_calendar), title, status,
    my_status, raw_json. Неизменённая запись остаётся как была (id и synced_at те же)."""
    sql = "SELECT * FROM calendar_events WHERE date BETWEEN ? AND ?"
    old = {
        (r["source"], r["uid"], r["start_at"]): r
        for r in fetch_all(conn, sql, (date_from, date_to))
    }
    kept: set[tuple[str, str, str]] = set()
    for event in events:
        values = {"source": CALENDAR_SOURCE, **event}
        values["all_day"] = int(values["all_day"])
        values["raw_json"] = _dumped(values.get("raw_json"))
        key = (values["source"], values["uid"], values["start_at"])
        kept.add(key)
        if key in old and _same(old[key], values):
            continue
        upsert(conn, "calendar_events", ["source", "uid", "start_at"], values)
    for key, row in old.items():
        if key not in kept:
            conn.execute("DELETE FROM calendar_events WHERE id = ?", (row["id"],))


def list_calendar_events(
    conn: sqlite3.Connection, date_from: str, date_to: str
) -> list[dict[str, Any]]:
    """События с датой начала date_from..date_to включительно, по времени начала."""
    sql = (
        "SELECT * FROM calendar_events WHERE date BETWEEN ? AND ? "
        "ORDER BY start_at, end_at, uid, source"
    )
    return fetch_all(conn, sql, (date_from, date_to))


def upsert_counter(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ - (date, kind). values: date, kind (из COUNTER_KINDS), value, source, synced_at;
    raw_json необязателен. Не изменившийся счётчик не перезаписывается (synced_at остаётся)."""
    if values["kind"] not in COUNTER_KINDS:
        raise ValueError(
            f"kind счётчика должен быть из {list(COUNTER_KINDS)}, получено: {values['kind']!r}"
        )
    values = {**values, "raw_json": _dumped(values.get("raw_json"))}
    sql = "SELECT * FROM day_counters WHERE date = ? AND kind = ?"
    old = fetch_all(conn, sql, (values["date"], values["kind"]))
    if old and _same(old[0], values):
        return
    upsert(conn, "day_counters", ["date", "kind"], values)


def list_counters(
    conn: sqlite3.Connection, date_from: str, date_to: str, kind: str | None = None
) -> list[dict[str, Any]]:
    """Счётчики с датой date_from..date_to включительно (kind - только этот признак), по дате."""
    if kind is None:
        sql = "SELECT * FROM day_counters WHERE date BETWEEN ? AND ? ORDER BY date, kind"
        return fetch_all(conn, sql, (date_from, date_to))
    sql = "SELECT * FROM day_counters WHERE date BETWEEN ? AND ? AND kind = ? ORDER BY date"
    return fetch_all(conn, sql, (date_from, date_to, kind))
