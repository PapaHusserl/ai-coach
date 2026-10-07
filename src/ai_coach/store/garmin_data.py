"""Данные из Garmin: daily_metrics, activities, strength_sets. Upsert по естественному ключу."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, upsert


def upsert_daily_metrics(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ — date. values: колонки daily_metrics, raw_json обязателен (объект или строка)."""
    upsert(conn, "daily_metrics", ["date"], values)


def get_daily_metrics(conn: sqlite3.Connection, date: str) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM daily_metrics WHERE date = ?", (date,))


def list_daily_metrics(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Дни start..end включительно, по возрастанию даты."""
    sql = "SELECT * FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date"
    return fetch_all(conn, sql, (start, end))


def upsert_activity(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ — activity_id. raw_json обязателен."""
    upsert(conn, "activities", ["activity_id"], values)


def get_activity(conn: sqlite3.Connection, activity_id: int) -> dict[str, Any] | None:
    return fetch_one(conn, "SELECT * FROM activities WHERE activity_id = ?", (activity_id,))


def list_activities(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Активности с датой старта (local) start..end включительно, по времени старта."""
    sql = (
        "SELECT * FROM activities WHERE substr(start_time_local, 1, 10) BETWEEN ? AND ? "
        "ORDER BY start_time_local"
    )
    return fetch_all(conn, sql, (start, end))


def upsert_strength_set(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ — (activity_id, set_index). Активность должна уже быть в activities."""
    upsert(conn, "strength_sets", ["activity_id", "set_index"], values)


def list_strength_sets(conn: sqlite3.Connection, activity_id: int) -> list[dict[str, Any]]:
    sql = "SELECT * FROM strength_sets WHERE activity_id = ? ORDER BY set_index"
    return fetch_all(conn, sql, (activity_id,))


def upsert_threshold(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """Ключ — calendar_date. values: calendar_date, lthr, raw_json."""
    upsert(conn, "thresholds", ["calendar_date"], values)


def last_threshold(conn: sqlite3.Connection, end: str) -> dict[str, Any] | None:
    """Самая свежая запись порогового пульса на дату end включительно."""
    sql = "SELECT * FROM thresholds WHERE calendar_date <= ? ORDER BY calendar_date DESC LIMIT 1"
    return fetch_one(conn, sql, (end,))


def last_rest_hr(conn: sqlite3.Connection, end: str) -> int | None:
    """Пульс покоя из ответа сна (raw_json) за последний день до end включительно, где он есть."""
    sql = (
        "SELECT json_extract(raw_json, '$.sleep.restingHeartRate') AS rest_hr FROM daily_metrics "
        "WHERE date <= ? AND rest_hr IS NOT NULL ORDER BY date DESC LIMIT 1"
    )
    row = fetch_one(conn, sql, (end,))
    return row["rest_hr"] if row else None
