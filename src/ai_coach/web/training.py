"""Тренировка в пульте: шаги плана и факт Garmin против плана. Только чтение."""

import json
import sqlite3
from datetime import date, timedelta
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.mcp_server import tools
from ai_coach.store.garmin_data import get_activity, list_activities
from ai_coach.store.plans import get_planned_workout, list_plan_actual, list_planned_workouts
from ai_coach.workouts.phone import exercise_title, player_payload

OK_PERCENT = 90  # факт от плана, начиная с которого длительность и дистанция «ок» (Р8)
SECONDS_IN_MINUTE = 60
METERS_IN_KM = 1000
ZONES = range(1, 6)
DAYS_IN_WEEK = 7
LOAD_DAYS = 14  # окно графика нагрузки (Р4)


def _spec(workout: dict[str, Any]) -> dict[str, Any]:
    spec = workout["workout_json"]
    return json.loads(spec) if isinstance(spec, str) else spec


def plan_steps(workout: dict[str, Any]) -> list[dict[str, Any]]:
    """Блоки плана разбором плеера (player_payload); workout - строка planned_workouts."""
    return player_payload(workout["sport"], _spec(workout), workout["date"])["b"]


def plan_view(workout: dict[str, Any]) -> dict[str, Any]:
    """План для окна: name, sport, duration_min (None без оценки), steps."""
    seconds = _spec(workout).get("estimated_duration_secs")
    return {
        "name": workout["name"],
        "sport": workout["sport"],
        "duration_min": None if seconds is None else _minutes(seconds),
        "steps": plan_steps(workout),
    }


def _missing_titles(spec: dict[str, Any], codes: list[str] | None) -> list[str] | None:
    """Коды Garmin пропущенных упражнений -> названия, как у плеера; чужой код остаётся как есть."""
    if codes is None:
        return None
    titles = {e["exercise"]: exercise_title(e) for e in spec.get("exercises", [])}
    return [titles.get(code, code) for code in codes]


def _zones(raw: dict[str, Any]) -> list[float] | None:
    seconds = [raw.get(f"hrTimeInZone_{n}") or 0 for n in ZONES]
    total = sum(seconds)
    return [s / total for s in seconds] if total > 0 else None


def _minutes(seconds: float) -> int:
    return round(seconds / SECONDS_IN_MINUTE)


def _clock(seconds: float) -> str:
    minutes, rest = divmod(round(seconds), SECONDS_IN_MINUTE)
    return f"{minutes}:{rest:02d}"


def _pace(pace: float) -> str:
    return f"{_clock(pace)} /км"


def _row(label: str, plan: str, fact: str, ok: bool) -> dict[str, Any]:
    return {"label": label, "plan": plan, "fact": fact, "mark": "ok" if ok else "warn"}


def _plan_vs_fact(
    spec: dict[str, Any], act: dict[str, Any], pace: float | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    steps = spec.get("steps", [])
    planned_s = spec.get("estimated_duration_secs")
    if planned_s and act["duration_s"] is not None:
        ok = act["duration_s"] * 100 >= planned_s * OK_PERCENT
        planned, done = _minutes(planned_s), _minutes(act["duration_s"])
        rows.append(_row("Длительность", f"{planned} мин", f"{done} мин", ok))
    meters = sum(s["meters"] for s in steps if "meters" in s)
    if meters and act["distance_m"]:
        ok = act["distance_m"] * 100 >= meters * OK_PERCENT
        rows.append(_row("Дистанция", _km(meters), _km(act["distance_m"]), ok))
    targets = [p for s in steps if "pace_sec_per_km" in s for p in s["pace_sec_per_km"]]
    if targets and pace is not None:
        plan = f"{_pace(max(targets))} - {_pace(min(targets))}"
        rows.append(_row("Темп", plan, _pace(pace), min(targets) <= pace <= max(targets)))
    return rows


def _km(meters: float) -> str:
    return f"{meters / METERS_IN_KM:.1f} км"


def fact(conn: sqlite3.Connection, workout_id: int, day: str) -> dict[str, Any] | None:
    """Факт тренировки за day из plan_actual (после coach sync); None - факта нет."""
    found = [r for r in list_plan_actual(conn, day, day) if r["planned_id"] == workout_id]
    if not found:
        return None
    actual = found[0]
    result: dict[str, Any] = {
        "kind": actual["kind"],
        "source": f"Garmin, синхронизация {actual['created_at'][:10]}",
        "rows": [],
        "missing": None,
    }
    numbers = ("duration_s", "distance_m", "avg_hr", "max_hr", "training_load", "calories")
    if actual["activity_id"] is None:
        return result | {k: None for k in (*numbers, "pace_s_km", "zones")}
    act = get_activity(conn, actual["activity_id"])
    assert act is not None  # внешний ключ plan_actual.activity_id
    distance = act["distance_m"]
    seconds = act["duration_s"]
    pace = (
        seconds / distance * METERS_IN_KM if seconds is not None and (distance or 0) > 0 else None
    )
    details: dict[str, Any] = json.loads(actual["details_json"] or "{}")
    workout = get_planned_workout(conn, workout_id)
    assert workout is not None  # внешний ключ plan_actual.planned_id
    spec = _spec(workout)
    return (
        result
        | {k: act[k] for k in numbers}
        | {
            "pace_s_km": pace,
            "zones": _zones(json.loads(act["raw_json"])),
            "rows": _plan_vs_fact(spec, act, pace),
            "missing": _missing_titles(spec, details.get("missing_exercises")),
        }
    )


def week(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Неделя Пн-Вс дня day: по дням план (все статусы) и факт (plan_actual и вне плана)."""
    given = date.fromisoformat(day)
    monday = given - timedelta(days=given.weekday())
    dates = [(monday + timedelta(days=n)).isoformat() for n in range(DAYS_IN_WEEK)]
    first, last = dates[0], dates[-1]
    days: dict[str, dict[str, Any]] = {d: {"date": d, "planned": [], "fact": []} for d in dates}
    workouts = list_planned_workouts(conn, first, last)
    for w in workouts:
        days[w["date"]]["planned"].append({k: w[k] for k in ("id", "name", "sport", "status")})
    activities = {a["activity_id"]: a for a in list_activities(conn, first, last)}
    plans = {w["id"]: w["name"] for w in workouts}
    seen: set[int | None] = set()
    for row in list_plan_actual(conn, first, last):
        name = plans.get(row["planned_id"]) or activities[row["activity_id"]]["name"]
        entry = {"kind": row["kind"], "name": name, "activity_id": row["activity_id"]}
        days[row["date"]]["fact"].append(entry | {"planned_id": row["planned_id"]})
        seen.add(row["activity_id"])
    for number, act in activities.items():
        if number not in seen:
            extra = {
                "kind": "extra",
                "name": act["name"],
                "activity_id": number,
                "planned_id": None,
            }
            days[act["start_time_local"][:10]]["fact"].append(extra)
    return {"days": list(days.values())}


def load(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Нагрузка CTL/ATL за 14 дней до day включительно; ToolError (нет пульса покоя) - текстом."""
    start = (date.fromisoformat(day) - timedelta(days=LOAD_DAYS - 1)).isoformat()
    try:
        rows = tools.load(conn, start, day)["rows"]
    except ToolError as error:
        return {"rows": None, "error": str(error)}
    return {"rows": rows, "error": None}
