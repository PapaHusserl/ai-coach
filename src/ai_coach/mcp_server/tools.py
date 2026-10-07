"""Инструменты MCP: чтение агрегатов и запись черновиков. Отправки на часы и удаления нет.

Функции принимают соединение с базой; server.py оборачивает их в инструменты MCP.
Из ответов убран raw_json; списки ограничены по числу строк и размеру.
"""

import json
import sqlite3
from datetime import date, timedelta
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach import goals
from ai_coach.load import (
    THRESHOLD_SPORTS,
    daily_tss,
    find_deviations,
    load_series,
    resolve_thresholds,
)
from ai_coach.store.db import fetch_one
from ai_coach.store.garmin_data import (
    last_rest_hr,
    list_activities,
    list_daily_metrics,
    list_strength_sets,
)
from ai_coach.store.journal import (
    last_sync_log,
    list_food,
    list_food_pending,
    list_weights,
    list_wellbeing,
    update_food,
)
from ai_coach.store.plans import (
    add_planned_workout,
    get_planned_workout,
    list_plan_actual,
    list_planned_workouts,
    update_planned_workout,
)
from ai_coach.workouts import SPORTS, build_workout

MAX_ROWS = 60
MAX_CHARS = 20000
SNAPSHOT_ROWS = 20
SNAPSHOT_CHARS = 4000
MAX_DAYS = 92
MAX_NUTRITION = 10000
REST_HR_MAX_AGE_DAYS = 14
LOAD_WARMUP_DAYS = 120
WELLBEING_DAYS = 30
WEEKEND_ONLY_SPORT = "bike"
SATURDAY = 5
NOT_LISTS = ("date", "load_error", "last_sync", "thresholds", "warnings")
DATE_SERIES = ("load", "metrics", "activities", "plan_actual", "weights", "food_today", "wellbeing")


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    """Без raw_json; остальные *_json (spec тренировки, детали) — объектом."""
    result: dict[str, Any] = {}
    for key, value in row.items():
        if key == "raw_json":
            continue
        if key.endswith("_json") and isinstance(value, str):
            value = json.loads(value)
        result[key] = value
    return result


def _cap(
    rows: list[dict[str, Any]],
    max_rows: int = MAX_ROWS,
    max_chars: int = MAX_CHARS,
    newest: bool = False,
) -> dict[str, Any]:
    """{"rows": строки без raw_json, "truncated": что-то отрезано}. Строк не больше max_rows,
    символов не больше max_chars. Лишнее отрезается с конца; для рядов по датам
    (newest=True) — с начала: остаются самые новые строки."""
    kept = [_clean(r) for r in (rows[-max_rows:] if newest else rows[:max_rows])]
    while kept and len(json.dumps(kept, ensure_ascii=False, default=str)) > max_chars:
        kept.pop(0 if newest else -1)
    return {"rows": kept, "truncated": len(kept) < len(rows)}


def _day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"Дата должна быть YYYY-MM-DD, получено: {value!r}") from None


def _period(start: str, end: str) -> None:
    first, last = _day(start), _day(end)
    if last < first:
        raise ToolError("Конец периода раньше начала.")
    if (last - first).days >= MAX_DAYS:
        raise ToolError(f"Период не больше {MAX_DAYS} дней.")


def _shift(day: str, days: int) -> str:
    return (_day(day) + timedelta(days=days)).isoformat()


def daily_metrics(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    _period(start, end)
    return _cap(list_daily_metrics(conn, start, end), newest=True)


def activities(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    _period(start, end)
    return _cap(list_activities(conn, start, end), newest=True)


def strength_sets(conn: sqlite3.Connection, activity_id: int) -> dict[str, Any]:
    return _cap(list_strength_sets(conn, activity_id))


def goals_list(conn: sqlite3.Connection, status: str | None = None) -> dict[str, Any]:
    return _cap(goals.list_goals(conn, status))


def goals_on(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    _day(day)
    return _cap(goals.goals_on(conn, day))


def phases_list(conn: sqlite3.Connection, status: str | None = None) -> dict[str, Any]:
    return _cap(goals.list_phases(conn, status))


def plan(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    _period(start, end)
    return _cap(list_planned_workouts(conn, start, end))


def plan_actual(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    _period(start, end)
    return _cap(list_plan_actual(conn, start, end), newest=True)


def weights(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    _period(start, end)
    return _cap(list_weights(conn, start, end), newest=True)


def food(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    _period(start, end)
    return _cap(list_food(conn, start, end), newest=True)


def food_pending(conn: sqlite3.Connection) -> dict[str, Any]:
    """Записи еды без КБЖУ (за все дни), старые первыми."""
    return _cap(list_food_pending(conn))


def wellbeing(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    """Самочувствие по времени; основная оценка дня — последняя запись этой даты."""
    _period(start, end)
    return _cap(list_wellbeing(conn, start, end), newest=True)


def _day_deviations(
    conn: sqlite3.Connection, day: str, load_row: dict[str, Any] | None
) -> list[dict[str, Any]]:
    marks = list_wellbeing(conn, day, day)
    metrics = list_daily_metrics(conn, day, day)
    return find_deviations(marks[-1] if marks else None, metrics[0] if metrics else None, load_row)


def deviations(
    conn: sqlite3.Connection,
    date: str,  # noqa: F811 - имя параметра для MCP, затеняет импорт date
) -> dict[str, Any]:
    """Отклонения за день: самочувствие, readiness, HRV, сон, ATL - CTL (пороги — в
    load/deviations.py). Пустой rows — всё в норме. Нет нагрузки — ATL - CTL не проверен,
    причина — в load_error."""
    _day(date)
    try:
        load_row = load(conn, date, date)["rows"][-1]
    except ToolError as error:
        return {**_cap(_day_deviations(conn, date, None)), "load_error": str(error)}
    return _cap(_day_deviations(conn, date, load_row))


def _hr_params(
    conn: sqlite3.Connection, end: str
) -> tuple[float, dict[str, dict[str, Any]], list[str]]:
    """Пульс покоя (последний из сна в базе, не старше 14 дней), пороги по видам спорта и
    предупреждения о видах без порога. Нет пульса покоя или порог не больше него — ToolError."""
    found = last_rest_hr(conn, end)
    if found is None or (_day(end) - _day(found[0])).days > REST_HR_MAX_AGE_DAYS:
        raise ToolError(
            f"В базе нет свежего (не старше {REST_HR_MAX_AGE_DAYS} дней) пульса покоя из сна. "
            "Сделай coach sync."
        )
    rest_hr = found[1]
    thresholds = resolve_thresholds(conn, end)
    for sport, threshold in thresholds.items():
        if threshold["lthr"] <= rest_hr:
            raise ToolError(f"LTHR {threshold['lthr']} ({sport}) не больше пульса покоя {rest_hr}.")
    warnings = [f"нет порога для {sport}" for sport in THRESHOLD_SPORTS if sport not in thresholds]
    return rest_hr, thresholds, warnings


def load(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    """TSS, CTL, ATL по дням start..end; расчёт идёт с запасом назад, чтобы CTL/ATL прогрелись.
    Кроме rows и truncated отдаёт thresholds: {вид: {lthr, source, date}} и warnings — виды
    без порога (их активности считаются с TSS 0)."""
    _period(start, end)
    rest_hr, thresholds, warnings = _hr_params(conn, end)
    lthr_by_sport = {sport: t["lthr"] for sport, t in thresholds.items()}
    tss = daily_tss(conn, _shift(start, -LOAD_WARMUP_DAYS), end, rest_hr, lthr_by_sport)
    result = _cap([row for row in load_series(tss) if row["date"] >= start], newest=True)
    result["thresholds"] = thresholds
    result["warnings"] = warnings
    return result


def morning_snapshot(
    conn: sqlite3.Connection,
    date: str,  # noqa: F811 - имя параметра для MCP, затеняет импорт date
) -> dict[str, Any]:
    """Всё для утреннего разбора одним ответом: каждый список — до SNAPSHOT_ROWS/CHARS,
    весь ответ — до MAX_CHARS (самый длинный список укорачивается: ряды по датам с начала,
    остальные с конца)."""
    _day(date)

    def part(rows: list[dict[str, Any]], newest: bool = False) -> dict[str, Any]:
        return _cap(rows, SNAPSHOT_ROWS, SNAPSHOT_CHARS, newest)

    snapshot: dict[str, Any] = {"date": date}
    load_row: dict[str, Any] | None = None
    try:
        loaded = load(conn, _shift(date, -6), date)
        snapshot["load"] = part(loaded["rows"], True)
        load_row = loaded["rows"][-1] if loaded["rows"] else None
        snapshot["thresholds"] = loaded["thresholds"]
        snapshot["warnings"] = loaded["warnings"]
    except ToolError as e:
        snapshot["load"] = part([])
        snapshot["load_error"] = str(e)
    snapshot["metrics"] = part(list_daily_metrics(conn, _shift(date, -7), date), True)
    snapshot["activities"] = part(list_activities(conn, _shift(date, -7), date), True)
    snapshot["goals"] = part(goals.list_goals(conn, "active"))
    snapshot["phases_now"] = part(goals.phases_on(conn, date))
    snapshot["phases_proposed"] = part(goals.list_phases(conn, "proposed"))
    snapshot["plan"] = part(list_planned_workouts(conn, date, _shift(date, 6)))
    snapshot["plan_actual"] = part(list_plan_actual(conn, _shift(date, -7), date), True)
    snapshot["weights"] = part(list_weights(conn, _shift(date, -14), date), True)
    snapshot["food_today"] = part(list_food(conn, date, date), True)
    marks = list_wellbeing(conn, _shift(date, -(WELLBEING_DAYS - 1)), date)
    snapshot["wellbeing"] = _cap(marks, newest=True)
    snapshot["deviations"] = part(_day_deviations(conn, date, load_row))
    snapshot["last_sync"] = last_sync_log(conn)
    while len(json.dumps(snapshot, ensure_ascii=False, default=str)) > MAX_CHARS:
        sections: dict[str, dict[str, Any]] = {
            k: snapshot[k] for k in snapshot if k not in NOT_LISTS and snapshot[k]["rows"]
        }
        if not sections:
            raise ToolError("Снапшот не помещается в лимит даже без списков.")
        key = max(sections, key=lambda k: len(json.dumps(sections[k]["rows"], ensure_ascii=False)))
        sections[key]["rows"].pop(0 if key in DATE_SERIES else -1)
        sections[key]["truncated"] = True
    return snapshot


def create_draft_workout(
    conn: sqlite3.Connection, date: str, sport: str, name: str, spec: dict[str, Any]
) -> dict[str, Any]:
    """Черновик тренировки плана (status=draft). spec проверяется сборкой JSON Garmin
    (workouts.build_workout); name подставляется в spec."""
    _day(date)
    if sport not in SPORTS:
        raise ToolError(f"sport должен быть из {list(SPORTS)}, получено: {sport!r}")
    if sport == WEEKEND_ONLY_SPORT and _day(date).weekday() < SATURDAY:
        raise ToolError("Вело планируется только в субботу и воскресенье.")
    full_spec = {**spec, "name": name}
    try:
        build_workout(sport, full_spec)
    except (KeyError, TypeError, ValueError, IndexError) as e:
        raise ToolError(f"spec не подходит: {type(e).__name__}: {e}") from None
    row = {"date": date, "sport": sport, "name": name, "workout_json": full_spec}
    with conn:
        return {"draft_id": add_planned_workout(conn, row)}


def save_food_nutrition(
    conn: sqlite3.Connection,
    food_id: int,
    kcal: float,
    protein_g: float,
    fat_g: float,
    carbs_g: float,
) -> dict[str, Any]:
    """КБЖУ записи еды (оценка тренера). Только для записи без КБЖУ: посчитанные не меняет."""
    if not all(0 <= x <= MAX_NUTRITION for x in (kcal, protein_g, fat_g, carbs_g)):
        raise ToolError(f"КБЖУ записи: ккал и граммы от 0 до {MAX_NUTRITION}.")
    values = {"kcal": kcal, "protein_g": protein_g, "fat_g": fat_g, "carbs_g": carbs_g}
    with conn:
        saved = update_food(conn, food_id, values)
    if not saved:
        if fetch_one(conn, "SELECT id FROM food_log WHERE id = ?", (food_id,)) is None:
            raise ToolError(f"Записи еды {food_id} нет.")
        raise ToolError(f"У записи {food_id} КБЖУ уже посчитано.")
    return {"food_id": food_id}


def cancel_draft_workout(conn: sqlite3.Connection, workout_id: int) -> dict[str, Any]:
    """Отмена черновика (draft -> cancelled). Утверждённые и отправленные не трогает; в Garmin
    не ходит."""
    row = get_planned_workout(conn, workout_id)
    if row is None:
        raise ToolError(f"Тренировки {workout_id} нет.")
    if row["status"] != "draft":
        raise ToolError(f"Отменить можно только черновик, а {workout_id} — {row['status']}.")
    with conn:
        update_planned_workout(conn, workout_id, {"status": "cancelled"})
    return {"cancelled_id": workout_id}


def propose_phase(
    conn: sqlite3.Connection,
    name: str,
    description: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    goal_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Предложение фазы (status=proposed); принимает её пользователь, не MCP."""
    fields: dict[str, Any] = {
        "description": description,
        "start_date": start_date,
        "end_date": end_date,
        "goal_ids": goal_ids,
    }
    given = {key: value for key, value in fields.items() if value is not None}
    try:
        with conn:
            phase_id = goals.propose_phase(conn, name, **given)
    except (ValueError, LookupError) as e:
        raise ToolError(str(e)) from None
    return {"phase_id": phase_id}
