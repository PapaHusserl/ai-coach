"""Подбор спортивного питания к тренировке: протоколы до/во время/после и добавки.
Ничего не пишет в базу."""

import json
import sqlite3
from typing import Any

from ai_coach.store.plans import list_planned_workouts
from ai_coach.store.sport_nutrition import list_protocols, list_supplements

DURING_FROM_MIN = 75
PHASES = ("before", "during", "after")
SERVICE_FIELDS = ("created_at", "updated_at", "deleted_at")
NAME_CUT = 40
MAX_FLAGS = 10
AMOUNTS = ("carbs_g", "protein_g", "fluid_ml")


def workout_duration_min(workout: dict[str, Any]) -> int:
    """Длительность тренировки плана в минутах из estimated_duration_secs;
    0 - неизвестна или меньше минуты."""
    raw = workout["workout_json"]
    spec: dict[str, Any] = json.loads(raw) if isinstance(raw, str) else raw or {}
    return round(spec.get("estimated_duration_secs") or 0) // 60


def supplements_for_day(conn: sqlite3.Connection, training: bool) -> list[dict[str, Any]]:
    """Добавки дня: daily всегда, остальные - только в день тренировки."""
    return [s for s in list_supplements(conn) if training or s["schedule"] == "daily"]


def phase_protocols(
    protocols: list[dict[str, Any]], phase: str, sport: str, minutes: int | None
) -> list[dict[str, Any]]:
    """Протоколы фазы, подходящие по длительности (minutes None - без фильтра);
    для вида спорта - частные, иначе общие."""
    fit = [p for p in protocols if p["phase"] == phase]
    if minutes is not None:
        fit = [p for p in fit if p["min_duration_min"] <= minutes]
    own = [p for p in fit if p["sport"] == sport]
    return own or [p for p in fit if p["sport"] is None]


def protocols_for(conn: sqlite3.Connection, workout: dict[str, Any]) -> dict[str, Any]:
    """before / during / after - протоколы, supplements - добавки дня тренировки.
    water_only - короче 75 минут: во время только вода (during пуст);
    duration_unknown - длительности нет, агент спрашивает у пользователя."""
    minutes = workout_duration_min(workout)
    unknown = minutes == 0
    water_only = not unknown and minutes < DURING_FROM_MIN
    protocols = list_protocols(conn)
    result: dict[str, Any] = {
        phase: phase_protocols(protocols, phase, workout["sport"], None if unknown else minutes)
        for phase in PHASES
    }
    if water_only:
        result["during"] = []
    result["supplements"] = supplements_for_day(conn, True)
    result["water_only"] = water_only
    result["duration_unknown"] = unknown
    return result


def without_service(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in SERVICE_FIELDS}


def day_nutrition(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Питание дня: workouts (тренировки без отменённых, у каждой before / during / after и
    флаги) и supplements (daily всегда, остальные - если есть тренировка)."""
    plan = list_planned_workouts(conn, day, day)
    workouts: list[dict[str, Any]] = []
    for workout in (w for w in plan if w["status"] != "cancelled"):
        picked = protocols_for(conn, workout)
        item = {k: workout[k] for k in ("id", "sport", "name")}
        item |= {phase: [without_service(p) for p in picked[phase]] for phase in PHASES}
        item |= {k: picked[k] for k in ("water_only", "duration_unknown")}
        workouts.append(item)
    supplements = supplements_for_day(conn, bool(workouts))
    return {
        "date": day,
        "workouts": workouts,
        "supplements": [without_service(s) for s in supplements],
    }


def compact_nutrition(found: dict[str, Any]) -> dict[str, Any] | None:
    """Питание дня коротко для сводки: rows - имя, фаза, г/мл (без заметок), workouts - флаги,
    supplements - одна строка. Нет тренировок и добавок - None."""
    if not found["workouts"] and not found["supplements"]:
        return None
    rows = [
        {"workout_id": w["id"], "name": p["name"], "phase": phase}
        | {k: p[k] for k in AMOUNTS if p[k]}
        for w in found["workouts"]
        for phase in PHASES
        for p in w[phase]
    ]
    flags = [
        {k: w[k] for k in ("id", "sport", "water_only", "duration_unknown")}
        | {"name": w["name"][:NAME_CUT]}
        for w in found["workouts"][:MAX_FLAGS]
    ]
    line = "; ".join(f"{s['name']} {s['dose']:g} {s['unit']}" for s in found["supplements"])
    return {"rows": rows, "workouts": flags, "supplements": line}
