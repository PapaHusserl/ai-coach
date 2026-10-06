"""Импорт FIT-файла активности в базу (без сети)."""

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import fitdecode  # pyright: ignore[reportMissingTypeStubs]

from ai_coach.store.garmin_data import get_activity, upsert_activity, upsert_strength_set
from ai_coach.store.journal import add_sync_log
from ai_coach.sync.jsonutil import dump

WANTED = ("session", "sport", "activity", "set")


class FitImportError(Exception):
    """Понятная пользователю ошибка импорта."""


def read_messages(path: Path) -> dict[str, list[dict[str, Any]]]:
    messages: dict[str, list[dict[str, Any]]] = {}
    try:
        with fitdecode.FitReader(str(path)) as reader:
            frame: Any
            for frame in reader:
                if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name in WANTED:
                    fields: dict[str, Any] = {f.name: f.value for f in frame.fields}
                    messages.setdefault(str(frame.name), []).append(fields)
    except fitdecode.FitError as e:
        raise FitImportError(f"{path.name} не читается как FIT: {e}") from e
    return messages


def activity_id_from_name(path: Path) -> int:
    """Скачанный с Garmin файл называется <activityId>_ACTIVITY.fit."""
    match = re.match(r"(\d+)_", path.name)
    if match is None:
        raise FitImportError(
            f"Не могу взять id активности из имени файла {path.name}: "
            "ожидается <id>_ACTIVITY.fit, иначе укажи --id"
        )
    return int(match.group(1))


def activity_row(activity_id: int, messages: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    session = messages["session"][0]
    sport = messages.get("sport", [{}])[0]
    start = session.get("start_time")
    if start is None:
        raise FitImportError("В FIT нет времени старта активности (session.start_time)")
    local = start
    activity = messages.get("activity", [{}])[0]
    if activity.get("local_timestamp") and activity.get("timestamp"):
        # local_timestamp в FIT — местное время, закодированное как UTC
        local = start + (activity["local_timestamp"] - activity["timestamp"])
    sub_sport = session.get("sub_sport")
    return {
        "activity_id": activity_id,
        "start_time_local": local.strftime("%Y-%m-%d %H:%M:%S"),
        "start_time_gmt": start.strftime("%Y-%m-%d %H:%M:%S"),
        "type_key": sub_sport if sub_sport not in (None, "generic") else session.get("sport"),
        "name": sport.get("name"),
        "duration_s": session.get("total_timer_time"),
        "distance_m": session.get("total_distance"),
        "calories": session.get("total_calories"),
        "avg_hr": session.get("avg_heart_rate"),
        "max_hr": session.get("max_heart_rate"),
        "training_load": session.get("training_load_peak"),
        "raw_json": dump(session),
    }


def set_row(activity_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    start = fields.get("start_time")
    return {
        "activity_id": activity_id,
        "set_index": fields["message_index"],
        "wkt_step_index": fields.get("wkt_step_index"),
        "reps": fields.get("repetitions"),
        # в FIT вес уже в кг
        "weight": fields.get("weight"),
        "duration_s": fields.get("duration"),
        "set_type": fields.get("set_type"),
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%S") if start else None,
        "raw_json": dump(fields),
    }


def import_fit(conn: sqlite3.Connection, path: Path, activity_id: int | None = None) -> str:
    """Читает FIT, пишет активность и подходы одной транзакцией, возвращает итог."""
    started = datetime.now().isoformat(timespec="seconds")
    if activity_id is None:
        activity_id = activity_id_from_name(path)
    messages = read_messages(path)
    if "session" not in messages:
        raise FitImportError(f"В {path.name} нет данных активности (session)")
    if get_activity(conn, activity_id) is not None:
        # активность из sync (с именем и raw_json из API) не затираем
        return f"активность {activity_id} уже в базе, пропущено"
    sets = [set_row(activity_id, s) for s in messages.get("set", [])]
    with conn:
        upsert_activity(conn, activity_row(activity_id, messages))
        for row in sets:
            upsert_strength_set(conn, row)
        message = f"активность {activity_id}, подходов {len(sets)}"
        add_sync_log(
            conn,
            {
                "started_at": started,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "kind": "import",
                "status": "ok",
                "message": message,
            },
        )
    return message
