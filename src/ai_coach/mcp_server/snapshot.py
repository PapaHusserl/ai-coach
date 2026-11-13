"""Инструмент MCP: утренняя сводка одним ответом (отдельно от tools.py из-за размера)."""

import json
import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach import goals
from ai_coach.agenda import agenda_rows
from ai_coach.decisions import day_part, pending
from ai_coach.load import illness_report, overload_report, sleep_report, who5_report
from ai_coach.load.overload import overloaded
from ai_coach.mcp_server import tools
from ai_coach.meds import short_meds
from ai_coach.pantry import expiring, stock
from ai_coach.profile import current_profile, profile_nutrition, remaining
from ai_coach.review import review_due
from ai_coach.sport_nutrition import compact_nutrition, day_nutrition
from ai_coach.store.garmin_data import list_activities, list_daily_metrics
from ai_coach.store.habits import habits_on
from ai_coach.store.journal import (
    evening_done,
    last_sync_log,
    list_food,
    list_weights,
    list_wellbeing,
    sync_runs_on,
    wellbeing_day,
)
from ai_coach.store.meds import list_meds
from ai_coach.store.pantry import has_meal_plan
from ai_coach.store.plans import list_plan_actual, list_planned_workouts
from ai_coach.store.recipes import list_recipes
from ai_coach.store.sport_nutrition import list_protocols, list_supplements
from ai_coach.workload import workload_series
from ai_coach.workload.claude import CLAUDE_COUNTERS

SNAPSHOT_ROWS = 20
SNAPSHOT_CHARS = 4000
SNAPSHOT_MAX_CHARS = 32768
SNAPSHOT_GOALS = 10
SNAPSHOT_PANTRY = 30
SNAPSHOT_EXPIRING = 10
SNAPSHOT_RECIPES = 30
SNAPSHOT_NUTRITION_ROWS = 10
SNAPSHOT_MEDS = 10
SNAPSHOT_HABITS = 10
SNAPSHOT_DECISIONS = 10
WELLBEING_DAYS = 7
WORKLOAD_AHEAD_DAYS = 7
AGENDA_BACK_DAYS = 1
AGENDA_AHEAD_DAYS = 7
WELLBEING_FIELDS = ("date", "logged_at", "score", "mood", "stress", "text")
AGENDA_FIELDS = ("id", "kind", "title", "start_at", "end_at", "status", "repeat", "workout_id")
WORKLOAD_CHARS = 5000
WORKLOAD_SKIP = CLAUDE_COUNTERS
CLAUDE_KEYS = {
    "prompts": "claude_prompts",
    "evening": "claude_prompts_evening",
    "decisions": "claude_decisions",
    "repos": "claude_repos",
    "switches": "claude_switches",
}
AHEAD_SKIP = CLAUDE_COUNTERS + (
    "todo_open",
    "todo_closed",
    "grooming_done",
    "grooming_pending",
    "screen_work_hours",
    "screen_hobby_hours",
    "screen_browser_hours",
    "screen_evening_hours",
    "screen_challenge_hours",
    "screen_hindrance_hours",
    "challenge_hours",
    "hindrance_hours",
)
NOT_LISTS = (
    "date",
    "load_error",
    "last_sync",
    "thresholds",
    "warnings",
    "profile",
    "meal_plan_today",
    "first_run_today",
    "evening_done_today",
    "week_review_due",
    "overload",
    "sleep",
    "illness",
    "who5",
    "catalog",
    "day_part",
)
DATE_SERIES = (
    "load",
    "metrics",
    "activities",
    "plan_actual",
    "weights",
    "food_today",
    "wellbeing",
    "workload",
    "claude",
)


def _snapshot_nutrition(conn: sqlite3.Connection, day: str) -> dict[str, Any] | None:
    """Питание дня для сводки, компактно (без заметок). Нет тренировок и добавок - None."""
    found = compact_nutrition(day_nutrition(conn, day))
    if found is None:
        return None
    result = tools.cap(found["rows"], SNAPSHOT_NUTRITION_ROWS, SNAPSHOT_CHARS)
    return result | {"workouts": found["workouts"], "supplements": found["supplements"]}


def _snapshot_meds(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Курсы на день для сводки, компактно (без заметок): {"meds_today": ...}; нет курсов - {}."""
    short = short_meds(conn, day)
    return {"meds_today": tools.cap(short, SNAPSHOT_MEDS, SNAPSHOT_CHARS)} if short else {}


def _snapshot_habits(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Привычки на день для сводки: {"habits_today": ...} (done None - не отмечена)."""
    names = ("name", "unit", "done", "amount")
    short = [{k: row[k] for k in names} for row in habits_on(conn, day)]
    return {"habits_today": tools.cap(short, SNAPSHOT_HABITS, SNAPSHOT_CHARS)}


def _snapshot_profile(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Профиль для сводки: только текущие значения (без источников и истории), missing,
    nutrition, nutrition_remaining и активные цели."""
    current = current_profile(conn, day)
    target = profile_nutrition(conn, day, current)
    found = sorted(goals.list_goals(conn, "active"), key=lambda g: (-g["priority"], g["id"]))
    active = [
        {k: g[k] for k in ("id", "title", "kind", "target", "target_date", "priority")}
        for g in found[:SNAPSHOT_GOALS]
    ]
    return {
        "values": {key: entry["value"] for key, entry in current["values"].items()},
        "missing": current["missing"],
        "nutrition": target,
        "nutrition_remaining": remaining(target, list_food(conn, day, day)),
        "goals": active,
        "goals_truncated": len(found) > SNAPSHOT_GOALS,
    }


def morning_snapshot(
    conn: sqlite3.Connection,
    date: str,
) -> dict[str, Any]:
    """Всё для утреннего разбора одним ответом: каждый список — до SNAPSHOT_ROWS/CHARS,
    весь ответ — до SNAPSHOT_MAX_CHARS (самый длинный список укорачивается: ряды по датам с начала,
    остальные с конца)."""
    tools.parse_day(date)

    def part(rows: list[dict[str, Any]], newest: bool = False) -> dict[str, Any]:
        return tools.cap(rows, SNAPSHOT_ROWS, SNAPSHOT_CHARS, newest)

    snapshot: dict[str, Any] = {"date": date}
    load_row: dict[str, Any] | None = None
    tss: dict[str, float] = {}
    try:
        loaded = tools.load(conn, tools.shift_day(date, -6), date)
        snapshot["load"] = part(loaded["rows"], True)
        load_row = loaded["rows"][-1] if loaded["rows"] else None
        tss = {r["date"]: r["tss"] for r in loaded["rows"]}
        snapshot["thresholds"] = loaded["thresholds"]
        snapshot["warnings"] = loaded["warnings"]
    except ToolError as e:
        snapshot["load"] = part([])
        snapshot["load_error"] = str(e)
    snapshot["metrics"] = part(list_daily_metrics(conn, tools.shift_day(date, -7), date), True)
    snapshot["activities"] = part(list_activities(conn, tools.shift_day(date, -7), date), True)
    snapshot["goals"] = part(goals.list_goals(conn, "active"))
    snapshot["phases_now"] = part(goals.phases_on(conn, date))
    snapshot["phases_proposed"] = part(goals.list_phases(conn, "proposed"))
    snapshot["plan"] = part(list_planned_workouts(conn, date, tools.shift_day(date, 6)))
    snapshot["plan_actual"] = part(list_plan_actual(conn, tools.shift_day(date, -7), date), True)
    snapshot["weights"] = part(list_weights(conn, tools.shift_day(date, -14), date), True)
    snapshot["food_today"] = part(list_food(conn, date, date), True)
    marks = list_wellbeing(conn, tools.shift_day(date, -(WELLBEING_DAYS - 1)), date)
    snapshot["wellbeing"] = tools.cap(
        [{k: r[k] for k in WELLBEING_FIELDS} for r in marks], newest=True
    )
    snapshot["deviations"] = part(tools.day_deviations(conn, date, load_row))
    week = workload_series(conn, tools.shift_day(date, -6), date)
    snapshot["workload"] = tools.cap(
        [{k: v for k, v in r.items() if k not in WORKLOAD_SKIP} for r in week],
        SNAPSHOT_ROWS,
        WORKLOAD_CHARS,
        True,
    )
    snapshot["claude"] = part(
        [
            {"date": r["date"]} | {short: r[kind] for short, kind in CLAUDE_KEYS.items()}
            for r in week
        ],
        True,
    )
    ahead = workload_series(
        conn, tools.shift_day(date, 1), tools.shift_day(date, WORKLOAD_AHEAD_DAYS)
    )
    snapshot["workload_ahead"] = part(
        [
            {**{k: v for k, v in r.items() if k not in AHEAD_SKIP}, "overloaded": overloaded(r)}
            for r in ahead
        ]
    )
    found_agenda = agenda_rows(
        conn, tools.shift_day(date, -AGENDA_BACK_DAYS), tools.shift_day(date, AGENDA_AHEAD_DAYS)
    )
    snapshot["agenda"] = part([{k: row[k] for k in AGENDA_FIELDS} for row in found_agenda])
    snapshot["overload"] = overload_report(conn, date, tss)
    snapshot["sleep"] = sleep_report(conn, date, tools.now())
    found_illness = illness_report(conn, date, tss, snapshot["sleep"])
    snapshot["illness"] = {k: v for k, v in found_illness.items() if k != "days"}
    is_today = date == tools.today().isoformat()
    evening_day = wellbeing_day(tools.now()) if is_today else date
    snapshot["day_part"] = day_part(tools.now()) if is_today else None
    queue = pending(conn, date)
    for key, name in (("pending", "decisions_pending"), ("to_check", "decisions_to_check")):
        snapshot[name] = tools.cap(queue[key], SNAPSHOT_DECISIONS, SNAPSHOT_CHARS)
    snapshot["evening_done_today"] = evening_done(conn, evening_day)
    snapshot["week_review_due"] = review_due(conn, evening_day)
    snapshot["who5"] = who5_report(conn, evening_day)
    snapshot["last_sync"] = last_sync_log(conn)
    snapshot["profile"] = _snapshot_profile(conn, date)
    short = [{k: row[k] for k in ("item", "qty", "unit")} for row in stock(conn)]
    snapshot["pantry"] = tools.cap(short, SNAPSHOT_PANTRY, SNAPSHOT_CHARS)
    snapshot["pantry_expiring"] = tools.cap(expiring(conn, date), SNAPSHOT_EXPIRING, SNAPSHOT_CHARS)
    names = ("name", "kcal_100", "protein_100", "fat_100", "carbs_100")
    short_recipes = [{k: row[k] for k in names} for row in list_recipes(conn)]
    snapshot["recipes"] = tools.cap(short_recipes, SNAPSHOT_RECIPES, SNAPSHOT_CHARS)
    snapshot["meal_plan_today"] = has_meal_plan(conn, date)
    snapshot["first_run_today"] = sync_runs_on(conn, date) <= 1
    nutrition = _snapshot_nutrition(conn, date)
    if nutrition is not None:
        snapshot["sport_nutrition_today"] = nutrition
    snapshot |= _snapshot_meds(conn, date)
    snapshot |= _snapshot_habits(conn, evening_day)
    snapshot["catalog"] = {
        "protocols": len(list_protocols(conn)),
        "supplements": len(list_supplements(conn)),
        "meds": len(list_meds(conn)),
    }
    while len(json.dumps(snapshot, ensure_ascii=False, default=str)) > SNAPSHOT_MAX_CHARS:
        sections: dict[str, dict[str, Any]] = {
            k: snapshot[k] for k in snapshot if k not in NOT_LISTS and snapshot[k]["rows"]
        }
        if not sections:
            raise ToolError("Снапшот не помещается в лимит даже без списков.")
        key = max(sections, key=lambda k: len(json.dumps(sections[k]["rows"], ensure_ascii=False)))
        sections[key]["rows"].pop(0 if key in DATE_SERIES else -1)
        sections[key]["truncated"] = True
    return snapshot
