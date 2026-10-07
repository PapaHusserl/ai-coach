"""Профиль спортсмена из Garmin (get_user_profile) -> profile_log."""

import sqlite3
from datetime import date
from typing import Any, cast

from garminconnect import (  # pyright: ignore[reportMissingTypeStubs]
    Garmin,
    GarminConnectNotFoundError,
)

from ai_coach.garmin import GarminError, garmin_errors
from ai_coach.profile.service import check_value, set_value
from ai_coach.store.profile import list_profile_entries

GENDERS = {"MALE": "m", "FEMALE": "f"}
WEEK_DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
WEEK_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def read_user_profile(client: Garmin, today: date) -> tuple[list[tuple[str, str, Any]], list[str]]:
    """Профиль из get_user_profile(): ((ключ, значение, сырой фрагмент), замечания).
    Пишем то, что пришло и прошло проверку; чего нет или что вне диапазона — в замечаниях.
    Пустой ответ — GarminError."""
    with garmin_errors():
        try:
            answer = client.get_user_profile()
        except GarminConnectNotFoundError:
            answer = None
    user = answer.get("userData") if isinstance(answer, dict) else None
    data = cast(dict[str, Any], user) if isinstance(user, dict) else {}
    if not data:
        raise GarminError("ответ Garmin пуст")
    weight = data.get("weight")
    found = {
        "sex": (GENDERS.get(str(data.get("gender"))), {"gender": data.get("gender")}),
        "birth_date": (data.get("birthDate"), {"birthDate": data.get("birthDate")}),
        "height_cm": (data.get("height"), {"height": data.get("height")}),
        "weight": (weight / 1000 if weight else None, {"weight": weight}),
    }
    days = [d for d in WEEK_DAYS if d in (data.get("availableTrainingDays") or [])]
    if days:
        names = ", ".join(WEEK_NAMES[WEEK_DAYS.index(d)] for d in days)
        found["schedule"] = (names, {"availableTrainingDays": days})
    entries: list[tuple[str, str, Any]] = []
    absent = [key for key, (value, _) in found.items() if not value]
    out_of_range: list[str] = []
    for key, (value, raw) in found.items():
        if not value:
            continue
        try:
            check_value(key, str(value), today)
        except ValueError:
            out_of_range.append(key)
            continue
        entries.append((key, str(value), raw))
    notes: list[str] = []
    if absent:
        notes.append(f"профиль неполный, нет: {', '.join(absent)}")
    if out_of_range:
        notes.append(f"профиль: {', '.join(out_of_range)} вне диапазона")
    return entries, notes


def write_profile(
    conn: sqlite3.Connection, entries: list[tuple[str, str, Any]], now: str
) -> list[str]:
    """Пишет профиль из Garmin в profile_log; возвращает ключи, которые изменились.
    Расписание не пишется, если у ключа есть ручная запись."""
    manual = {row["key"] for row in list_profile_entries(conn) if row["source"] == "manual"}
    return [
        key
        for key, value, raw in entries
        if key not in manual or key != "schedule"
        if set_value(conn, key, value, "garmin", now, raw)
    ]
