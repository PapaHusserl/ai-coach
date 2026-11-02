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


_REST_HR_SQL = (
    "COALESCE(json_extract(raw_json, '$.sleep.restingHeartRate'), "
    "(SELECT json_extract(value, '$.value') FROM json_each(raw_json, '$.hrv.metrics') "
    "WHERE json_extract(value, '$.type') = 'HR'))"
)


def _hrv_limit_sql(key: str) -> str:
    """Граница коридора из метрики HRV импорта (json_each по $.hrv.metrics)."""
    return (
        f"(SELECT json_extract(value, '$.{key}') FROM json_each(raw_json, '$.hrv.metrics') "
        "WHERE json_extract(value, '$.type') = 'HRV')"
    )


def list_sleep_nights(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Ночи start..end включительно, по возрастанию даты, без raw_json: date, sleep_seconds,
    sleep_end (подъём, местное 'YYYY-MM-DD HH:MM:SS'; None у импорта) и nap_seconds (дневной сон:
    napTimeSeconds у API или сумма napList[].napTimeSec у импорта; None - не записан)."""
    sql = (
        "SELECT date, sleep_seconds, "
        "datetime(json_extract(raw_json, '$.sleep.dailySleepDTO.sleepEndTimestampLocal') / 1000, "
        "'unixepoch') AS sleep_end, "
        "COALESCE(json_extract(raw_json, '$.sleep.dailySleepDTO.napTimeSeconds'), "
        "(SELECT SUM(json_extract(value, '$.napTimeSec')) "
        "FROM json_each(raw_json, '$.sleep.napList'))) AS nap_seconds "
        "FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date"
    )
    return fetch_all(conn, sql, (start, end))


def list_stress_points(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Замеры стресса дней start..end включительно, по времени, без raw_json: date, ts_ms (epoch
    GMT, мс) и level (0-100; отрицательный - нет замера). Дни без стресса не возвращаются."""
    sql = (
        "SELECT date, json_extract(value, '$[0]') AS ts_ms, json_extract(value, '$[1]') AS level "
        "FROM daily_metrics, json_each(raw_json, '$.stress.stressValuesArray') "
        "WHERE date BETWEEN ? AND ? ORDER BY ts_ms"
    )
    return fetch_all(conn, sql, (start, end))


def list_recovery_days(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Дни start..end включительно, по возрастанию даты, без raw_json: date, hrv (HRV за ночь) и
    rhr (пульс покоя: restingHeartRate сна у API или метрика HR у импорта; None - нет)."""
    sql = (
        f"SELECT date, hrv_last_night AS hrv, {_REST_HR_SQL} AS rhr "
        "FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date"
    )
    return fetch_all(conn, sql, (start, end))


def list_hrv_corridor(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Дни start..end включительно, по возрастанию даты, без raw_json: date, hrv (HRV за ночь),
    low и high (коридор HRV Garmin как в JSON: balancedLow/balancedUpper у API, метрика HRV
    baselineLowerLimit/baselineUpperLimit у импорта), source ('api' - есть
    $.hrv.hrvSummary, иначе 'import'). Дни без HRV в обоих источниках не возвращаются."""
    api = "json_extract(raw_json, '$.hrv.hrvSummary.baseline"
    imp_low = _hrv_limit_sql("baselineLowerLimit")
    imp_high = _hrv_limit_sql("baselineUpperLimit")
    sql = (
        "SELECT date, hrv, low, high, source FROM ("
        "SELECT date, hrv_last_night AS hrv, "
        f"COALESCE({api}.balancedLow'), {imp_low}) AS low, "
        f"COALESCE({api}.balancedUpper'), {imp_high}) AS high, "
        "CASE WHEN json_extract(raw_json, '$.hrv.hrvSummary') IS NOT NULL "
        "THEN 'api' ELSE 'import' END AS source "
        "FROM daily_metrics WHERE date BETWEEN ? AND ?) WHERE hrv IS NOT NULL ORDER BY date"
    )
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
    """Ключ — (sport, calendar_date, source). values: sport, calendar_date, source, raw_json;
    lthr и max_hr необязательны."""
    upsert(conn, "thresholds", ["sport", "calendar_date", "source"], values)


def last_threshold(conn: sqlite3.Connection, sport: str, end: str) -> dict[str, Any] | None:
    """Самая свежая запись с пороговым пульсом вида спорта на дату end включительно;
    при равной дате зоны (garmin_zones) выигрывают у lactate (garmin_lt)."""
    sql = (
        "SELECT * FROM thresholds WHERE sport = ? AND calendar_date <= ? AND lthr IS NOT NULL "
        "ORDER BY calendar_date DESC, source DESC LIMIT 1"
    )
    return fetch_one(conn, sql, (sport, end))


def last_zones_threshold(conn: sqlite3.Connection, sport: str) -> dict[str, Any] | None:
    """Самая свежая запись вида спорта из зон Garmin."""
    sql = (
        "SELECT * FROM thresholds WHERE sport = ? AND source = 'garmin_zones' "
        "ORDER BY calendar_date DESC LIMIT 1"
    )
    return fetch_one(conn, sql, (sport,))


def last_zones_max_hr(conn: sqlite3.Connection, sport: str, end: str) -> int | None:
    """Максимальный пульс вида спорта из последних зон Garmin на дату end включительно."""
    sql = (
        "SELECT max_hr FROM thresholds WHERE sport = ? AND calendar_date <= ? "
        "AND max_hr IS NOT NULL ORDER BY calendar_date DESC LIMIT 1"
    )
    row = fetch_one(conn, sql, (sport, end))
    return row["max_hr"] if row else None


def max_hr(
    conn: sqlite3.Connection, start: str, end: str, type_keys: tuple[str, ...]
) -> int | None:
    """Максимальный пульс по активностям данных typeKey с датой start..end включительно."""
    marks = ", ".join("?" for _ in type_keys)
    sql = (
        "SELECT MAX(max_hr) AS max_hr FROM activities "
        f"WHERE substr(start_time_local, 1, 10) BETWEEN ? AND ? AND type_key IN ({marks})"
    )
    row = fetch_one(conn, sql, (start, end, *type_keys))
    return row["max_hr"] if row else None


def last_rest_hr(conn: sqlite3.Connection, end: str) -> tuple[str, int] | None:
    """(дата, пульс покоя) из raw_json за последний день до end включительно, где он есть:
    restingHeartRate сна у API или метрика HR у импорта."""
    sql = (
        f"SELECT date, {_REST_HR_SQL} AS rest_hr "
        "FROM daily_metrics WHERE date <= ? AND rest_hr IS NOT NULL ORDER BY date DESC LIMIT 1"
    )
    row = fetch_one(conn, sql, (end,))
    return (row["date"], row["rest_hr"]) if row else None
