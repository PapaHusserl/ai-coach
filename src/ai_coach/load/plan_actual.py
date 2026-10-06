"""Сопоставление плана и факта: done / skipped / extra / different."""

import json
import sqlite3
from typing import Any

from ai_coach.store.garmin_data import list_activities, list_strength_sets
from ai_coach.store.plans import add_plan_actual, delete_plan_actual, list_planned_workouts

SPORT_TYPE_KEYS = {
    "run": ("running", "treadmill_running", "trail_running", "track_running", "virtual_run"),
    "bike": (
        "cycling",
        "indoor_cycling",
        "road_biking",
        "mountain_biking",
        "gravel_cycling",
        "virtual_ride",
    ),
    "swim": ("lap_swimming", "open_water_swimming", "swimming"),
    "strength": ("strength_training",),
}


def _same_type(planned: dict[str, Any], activity: dict[str, Any]) -> bool:
    return activity["type_key"] in SPORT_TYPE_KEYS.get(planned["sport"], ())


def _missing_exercises(
    conn: sqlite3.Connection, planned: dict[str, Any], activity: dict[str, Any]
) -> list[str]:
    """Упражнение i ↔ ACTIVE-подход с wktStepIndex = 3i + 1 (допущение, проверить на часах)."""
    done_steps = {
        s["wkt_step_index"]
        for s in list_strength_sets(conn, activity["activity_id"])
        if s["set_type"] == "ACTIVE"
    }
    exercises = json.loads(planned["workout_json"])["exercises"]
    return [e["exercise"] for i, e in enumerate(exercises) if 3 * i + 1 not in done_steps]


def _pair(
    conn: sqlite3.Connection, planned: dict[str, Any], activity: dict[str, Any]
) -> tuple[str, str | None]:
    """kind и details_json для пары план-активность одного типа."""
    if planned["sport"] == "strength":
        missing = _missing_exercises(conn, planned, activity)
        if missing:
            return "different", json.dumps({"missing_exercises": missing}, ensure_ascii=False)
    return "done", None


def _row(
    date: str,
    kind: str,
    planned_id: int | None,
    activity_id: int | None,
    details: str | None = None,
) -> dict[str, Any]:
    return {
        "date": date,
        "kind": kind,
        "planned_id": planned_id,
        "activity_id": activity_id,
        "details_json": details,
    }


def _rebuild_day(
    conn: sqlite3.Connection,
    date: str,
    planned_list: list[dict[str, Any]],
    activities: list[dict[str, Any]],
) -> None:
    free = list(activities)
    unmatched: list[dict[str, Any]] = []
    for planned in planned_list:
        found = next((a for a in free if _same_type(planned, a)), None)
        if found is None:
            unmatched.append(planned)
            continue
        free.remove(found)
        kind, details = _pair(conn, planned, found)
        add_plan_actual(conn, _row(date, kind, planned["id"], found["activity_id"], details))
    for planned in unmatched:
        if free:
            other = free.pop(0)
            add_plan_actual(conn, _row(date, "different", planned["id"], other["activity_id"]))
        else:
            add_plan_actual(conn, _row(date, "skipped", planned["id"], None))
    for activity in free:
        add_plan_actual(conn, _row(date, "extra", None, activity["activity_id"]))


def rebuild_plan_actual(conn: sqlite3.Connection, start: str, end: str) -> None:
    """Пересчёт plan_actual за период start..end включительно (без commit)."""
    delete_plan_actual(conn, start, end)
    planned_by_day: dict[str, list[dict[str, Any]]] = {}
    for planned in list_planned_workouts(conn, start, end):
        if planned["status"] == "pushed" and planned["sport"] in SPORT_TYPE_KEYS:
            planned_by_day.setdefault(planned["date"], []).append(planned)
    activities_by_day: dict[str, list[dict[str, Any]]] = {}
    for activity in list_activities(conn, start, end):
        activities_by_day.setdefault(activity["start_time_local"][:10], []).append(activity)
    for date in sorted(planned_by_day.keys() | activities_by_day.keys()):
        _rebuild_day(conn, date, planned_by_day.get(date, []), activities_by_day.get(date, []))
