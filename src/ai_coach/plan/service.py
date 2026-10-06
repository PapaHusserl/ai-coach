"""План: переходы статусов planned_workouts и отправка в Garmin.

В workout_json лежит spec тренировки (см. workouts.build_workout); JSON для Garmin
собирается при отправке. Commit делает вызывающий код.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from ai_coach.garmin import GarminError, garmin_errors
from ai_coach.store.plans import get_planned_workout, update_planned_workout
from ai_coach.workouts import build_workout


class PlanError(Exception):
    """Тренировку нельзя так менять или отправлять. Текст — для консоли."""


def _get(conn: sqlite3.Connection, workout_id: int) -> dict[str, Any]:
    row = get_planned_workout(conn, workout_id)
    if row is None:
        raise PlanError(f"Тренировки {workout_id} нет.")
    return row


def approve(conn: sqlite3.Connection, workout_id: int) -> None:
    """draft -> approved."""
    row = _get(conn, workout_id)
    if row["status"] != "draft":
        raise PlanError(
            f"Утвердить можно только черновик, а тренировка {workout_id} — {row['status']}."
        )
    update_planned_workout(conn, workout_id, {"status": "approved"})


def pushable(conn: sqlite3.Connection, workout_id: int) -> dict[str, Any]:
    """Строка тренировки, которую можно отправлять: approved или pushed (повторный push)."""
    row = _get(conn, workout_id)
    if row["status"] not in ("approved", "pushed"):
        raise PlanError(
            f"Отправлять можно утверждённую тренировку, а {workout_id} — {row['status']}."
        )
    return row


def garmin_json(row: dict[str, Any]) -> dict[str, Any]:
    return build_workout(row["sport"], json.loads(row["workout_json"]))


def has_old(row: dict[str, Any]) -> bool:
    """Есть ли в Garmin наша прежняя копия этой тренировки."""
    return row["garmin_workout_id"] is not None


def remove_old(client: Any, workout_id: int, schedule_id: int | None) -> None:
    """Снимает с календаря и удаляет прежнюю копию (id запомнены до отправки новой).
    При сбое сообщение называет, что осталось в Garmin."""
    try:
        if schedule_id is not None:
            with garmin_errors():
                client.unschedule_workout(schedule_id)
    except GarminError as e:
        raise GarminError(
            f"{e} Старая копия осталась в Garmin: workoutId={workout_id}, scheduleId={schedule_id}."
        ) from e
    try:
        with garmin_errors():
            client.delete_workout(workout_id)
    except GarminError as e:
        raise GarminError(
            f"{e} Старая копия снята с календаря, но шаблон workoutId={workout_id} не удалён."
        ) from e


def send(conn: sqlite3.Connection, client: Any, row: dict[str, Any]) -> None:
    """Загрузка тренировки и план на дату. В базу id и статус pushed пишутся только после
    успешного плана на дату; при сбое базу не трогаем, а в сообщении — id загруженного шаблона."""
    with garmin_errors():
        uploaded = client.upload_workout(garmin_json(row))
    workout_id = uploaded["workoutId"]
    try:
        with garmin_errors():
            scheduled = client.schedule_workout(workout_id, row["date"])
    except GarminError as e:
        raise GarminError(
            f"{e} Шаблон загружен в Garmin (workoutId={workout_id}), но не запланирован."
        ) from e
    values = {
        "status": "pushed",
        "garmin_workout_id": workout_id,
        "garmin_schedule_id": scheduled["workoutScheduleId"],
        "pushed_at": datetime.now().isoformat(timespec="seconds"),
    }
    update_planned_workout(conn, row["id"], values)
