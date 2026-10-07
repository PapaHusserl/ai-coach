"""Синхронизация Garmin -> база: метрики за день, активности, подходы силовой.

Сначала всё читается из Garmin, потом всё пишется одной транзакцией: ошибка при чтении
(429, токены) оставляет базу нетронутой.
"""

import sqlite3
import time
from datetime import date, datetime, timedelta
from typing import Any, cast

from garminconnect import (  # pyright: ignore[reportMissingTypeStubs]
    Garmin,
    GarminConnectNotFoundError,
)

from ai_coach.garmin import GarminError, garmin_errors
from ai_coach.store.garmin_data import (
    upsert_activity,
    upsert_daily_metrics,
    upsert_strength_set,
    upsert_threshold,
)
from ai_coach.store.journal import add_sync_log
from ai_coach.sync.jsonutil import dump

STRENGTH = "strength_training"


def log(conn: sqlite3.Connection, started: str, status: str, message: str) -> None:
    values = {
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "sync",
        "status": status,
        "message": message,
    }
    add_sync_log(conn, values)


def fetch_day(fetch: Any, day: Any, pause: float) -> Any:
    """Один запрос за день. Дня без данных (404) нет — это пропуск, не ошибка."""
    try:
        result = fetch(day)
    except GarminConnectNotFoundError:
        result = None
    time.sleep(pause)
    return result


def obj(value: Any) -> dict[str, Any]:
    """Словарь из ответа Garmin; пусто или не словарь — пустой словарь."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def objs(value: Any) -> list[dict[str, Any]]:
    """Список словарей из ответа Garmin; пусто или не список — пустой список."""
    if not isinstance(value, list):
        return []
    return [cast(dict[str, Any], v) for v in cast(list[Any], value) if isinstance(v, dict)]


def first(value: Any) -> dict[str, Any]:
    """Body Battery и readiness приходят списком; берём последний элемент."""
    if isinstance(value, list):
        return obj(value[-1]) if value else {}
    return obj(value)


def day_metrics(day: str, raw: dict[str, Any]) -> dict[str, Any]:
    sleep = obj(obj(raw["sleep"]).get("dailySleepDTO"))
    hrv = obj(obj(raw["hrv"]).get("hrvSummary"))
    battery = first(raw["body_battery"])
    stress = obj(raw["stress"])
    readiness = first(raw["training_readiness"])
    return {
        "date": day,
        "sleep_seconds": sleep.get("sleepTimeSeconds"),
        "sleep_score": obj(obj(sleep.get("sleepScores")).get("overall")).get("value"),
        "hrv_last_night": hrv.get("lastNightAvg"),
        "hrv_weekly_avg": hrv.get("weeklyAvg"),
        "hrv_status": hrv.get("status"),
        "body_battery_charged": battery.get("charged"),
        "body_battery_drained": battery.get("drained"),
        "stress_avg": stress.get("avgStressLevel"),
        "readiness_score": readiness.get("score"),
        "readiness_level": readiness.get("level"),
        "raw_json": dump(raw),
    }


def read_metrics(client: Garmin, days: list[str], pause: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in days:
        raw = {
            "sleep": fetch_day(client.get_sleep_data, day, pause),
            "hrv": fetch_day(client.get_hrv_data, day, pause),
            "stress": fetch_day(client.get_stress_data, day, pause),
            "body_battery": fetch_day(client.get_body_battery, day, pause),
            "training_readiness": fetch_day(client.get_training_readiness, day, pause),
        }
        if any(raw.values()):
            rows.append(day_metrics(day, raw))
    return rows


def activity_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "activity_id": raw["activityId"],
        "start_time_local": raw["startTimeLocal"],
        "start_time_gmt": raw.get("startTimeGMT"),
        "type_key": obj(raw.get("activityType")).get("typeKey") or "unknown",
        "name": raw.get("activityName"),
        "duration_s": raw.get("duration"),
        "distance_m": raw.get("distance"),
        "calories": raw.get("calories"),
        "avg_hr": raw.get("averageHR"),
        "max_hr": raw.get("maxHR"),
        "training_load": raw.get("activityTrainingLoad"),
        "workout_id": raw.get("workoutId"),
        "raw_json": dump(raw),
    }


def set_row(activity_id: int, raw: dict[str, Any]) -> dict[str, Any]:
    exercise = (objs(raw.get("exercises")) or [{}])[0]
    weight = raw.get("weight")
    return {
        "activity_id": activity_id,
        "set_index": raw["messageIndex"],
        "wkt_step_index": raw.get("wktStepIndex"),
        "exercise_category": exercise.get("category"),
        "exercise_name": exercise.get("name"),
        "reps": raw.get("repetitionCount"),
        # Garmin API отдаёт вес в граммах, в базе — кг
        "weight": None if weight is None else weight / 1000,
        "duration_s": raw.get("duration"),
        "set_type": raw.get("setType"),
        "start_time": raw.get("startTime"),
        "raw_json": dump(raw),
    }


def read_activities(
    client: Garmin, start: str, end: str, pause: float
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Список пар (строка активности, строки подходов)."""
    result: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    listed = client.get_activities_by_date(start, end)
    time.sleep(pause)
    for raw in objs(listed):
        sets: list[dict[str, Any]] = []
        if obj(raw.get("activityType")).get("typeKey") == STRENGTH:
            data = fetch_day(client.get_activity_exercise_sets, raw["activityId"], pause)
            sets = [set_row(raw["activityId"], s) for s in objs(obj(data).get("exerciseSets"))]
        result.append((activity_row(raw), sets))
    return result


def read_threshold(client: Garmin, today: date) -> dict[str, Any] | None:
    """Пороговый пульс бега (LTHR) из Garmin; нет данных — None.
    Библиотека при пустом ответе падает с TypeError (перебор None) — это тоже «нет данных»."""
    try:
        data = obj(client.get_lactate_threshold(latest=True))
    except (GarminConnectNotFoundError, TypeError):
        return None
    found = obj(data.get("speed_and_heart_rate"))
    if not found.get("heartRate"):
        return None
    return {
        "calendar_date": str(found.get("calendarDate") or today.isoformat())[:10],
        "lthr": found["heartRate"],
        "raw_json": dump(data),
    }


def sync(
    conn: sqlite3.Connection,
    client: Garmin,
    days: int,
    today: date | None = None,
    pause: float = 0,
) -> str:
    """Тянет `days` последних дней (включая today), пишет в базу, возвращает итог.

    Ошибка Garmin (401, 429): база не меняется, в sync_log пишется строка error."""
    started = datetime.now().isoformat(timespec="seconds")
    today = today or date.today()
    day_list = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    try:
        with garmin_errors():
            metrics = read_metrics(client, day_list, pause)
            activities = read_activities(client, day_list[-1], day_list[0], pause)
            threshold = read_threshold(client, today)
    except GarminError as e:
        with conn:
            log(conn, started, "error", str(e))
        raise
    message = f"дней с метриками {len(metrics)}, активностей {len(activities)}"
    with conn:
        for row in metrics:
            upsert_daily_metrics(conn, row)
        for activity, sets in activities:
            upsert_activity(conn, activity)
            for row in sets:
                upsert_strength_set(conn, row)
        if threshold:
            upsert_threshold(conn, threshold)
        log(conn, started, "ok", message)
    return message
