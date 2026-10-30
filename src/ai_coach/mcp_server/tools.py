"""Инструменты MCP: чтение агрегатов и запись черновиков. Отправки на часы и удаления нет.

Функции принимают соединение с базой; server.py оборачивает их в инструменты MCP.
Из ответов убран raw_json; списки ограничены по числу строк и размеру.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Literal

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach import goals
from ai_coach.load import (
    THRESHOLD_SPORTS,
    daily_tss,
    find_deviations,
    load_series,
    main_wellbeing,
    resolve_thresholds,
)
from ai_coach.meds import public_meds
from ai_coach.nutrition.groups import FOOD_GROUPS
from ai_coach.pantry import stock
from ai_coach.profile import (
    current_profile,
    profile_history,
    profile_nutrition,
    remaining,
    resting_hr,
)
from ai_coach.sport_nutrition import day_nutrition, without_service
from ai_coach.store.db import fetch_one
from ai_coach.store.garmin_data import (
    last_rest_hr,
    list_activities,
    list_daily_metrics,
    list_strength_sets,
)
from ai_coach.store.intake import list_intake
from ai_coach.store.journal import (
    add_food_groups,
    list_focus,
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
from ai_coach.store.recipes import list_recipes
from ai_coach.store.sport_nutrition import list_protocols, list_supplements
from ai_coach.workouts import SPORTS, build_workout

MAX_ROWS = 60
MAX_CHARS = 20000
MAX_DAYS = 92
MAX_NUTRITION = 10000
REST_HR_MAX_AGE_DAYS = 14
LOAD_WARMUP_DAYS = 120
WEEKEND_ONLY_SPORT = "bike"
SATURDAY = 5


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


def cap(
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


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"Дата должна быть YYYY-MM-DD, получено: {value!r}") from None


def period(start: str, end: str) -> None:
    first, last = parse_day(start), parse_day(end)
    if last < first:
        raise ToolError("Конец периода раньше начала.")
    if (last - first).days >= MAX_DAYS:
        raise ToolError(f"Период не больше {MAX_DAYS} дней.")


def shift_day(day: str, days: int) -> str:
    return (parse_day(day) + timedelta(days=days)).isoformat()


def daily_metrics(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    period(start, end)
    return cap(list_daily_metrics(conn, start, end), newest=True)


def activities(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    period(start, end)
    return cap(list_activities(conn, start, end), newest=True)


def strength_sets(conn: sqlite3.Connection, activity_id: int) -> dict[str, Any]:
    return cap(list_strength_sets(conn, activity_id))


def goals_list(conn: sqlite3.Connection, status: str | None = None) -> dict[str, Any]:
    return cap(goals.list_goals(conn, status))


def goals_on(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    parse_day(day)
    return cap(goals.goals_on(conn, day))


def phases_list(conn: sqlite3.Connection, status: str | None = None) -> dict[str, Any]:
    return cap(goals.list_phases(conn, status))


def plan(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    period(start, end)
    return cap(list_planned_workouts(conn, start, end))


def plan_actual(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    period(start, end)
    return cap(list_plan_actual(conn, start, end), newest=True)


def weights(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    period(start, end)
    return cap(list_weights(conn, start, end), newest=True)


def food(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    period(start, end)
    return cap(list_food(conn, start, end), newest=True)


def food_pending(conn: sqlite3.Connection) -> dict[str, Any]:
    """Записи еды без КБЖУ (за все дни), старые первыми."""
    return cap(list_food_pending(conn))


def wellbeing(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    """Самочувствие по времени; основная оценка дня — последняя запись этой даты."""
    period(start, end)
    return cap(list_wellbeing(conn, start, end), newest=True)


def focus_log(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    """Дневные оценки (фокус, усталость, усилие 1-5) по времени."""
    period(start, end)
    return cap(list_focus(conn, start, end), newest=True)


def day_deviations(
    conn: sqlite3.Connection, day: str, load_row: dict[str, Any] | None
) -> list[dict[str, Any]]:
    marks = list_wellbeing(conn, day, day)
    metrics = list_daily_metrics(conn, day, day)
    return find_deviations(main_wellbeing(marks), metrics[0] if metrics else None, load_row)


def deviations(
    conn: sqlite3.Connection,
    date: str,  # noqa: F811 - имя параметра для MCP, затеняет импорт date
) -> dict[str, Any]:
    """Отклонения за день: самочувствие, readiness, HRV, сон, ATL - CTL (пороги — в
    load/deviations.py). Пустой rows — всё в норме. Нет нагрузки — ATL - CTL не проверен,
    причина — в load_error."""
    parse_day(date)
    try:
        load_row = load(conn, date, date)["rows"][-1]
    except ToolError as error:
        return {**cap(day_deviations(conn, date, None)), "load_error": str(error)}
    return cap(day_deviations(conn, date, load_row))


def profile(
    conn: sqlite3.Connection,
    date: str | None = None,  # noqa: F811 - имя параметра для MCP, затеняет импорт date
    history: bool = False,
) -> dict[str, Any]:
    """Профиль спортсмена на конец дня (по умолчанию сегодня): значения с источниками,
    missing (что не заполнено), no_goals, nutrition (КБЖУ-цель), nutrition_remaining
    (остаток дня: цель минус съеденное, минус — перебор; нет цели — None). history=True — ещё и все
    записи по ключам. Без raw_json."""
    day = parse_day(date).isoformat() if date else today().isoformat()
    current = current_profile(conn, day)
    target = profile_nutrition(conn, day, current)
    result = {
        "date": day,
        **current,
        "resting_hr": resting_hr(conn, day),
        "nutrition": target,
        "nutrition_remaining": remaining(target, list_food(conn, day, day)),
    }
    if history:
        result["history"] = profile_history(conn, day)
    return result


def pantry(conn: sqlite3.Connection) -> dict[str, Any]:
    """Продукты дома (остаток больше 0): item, qty, unit, updated_at, expires_on, opened."""
    return cap(stock(conn))


def recipes(conn: sqlite3.Connection) -> dict[str, Any]:
    """Рецепты (живые): id, name, КБЖУ на 100 г, yield_g, items (состав)."""
    skip = ("created_at", "updated_at", "deleted_at")
    return cap([{k: v for k, v in row.items() if k not in skip} for row in list_recipes(conn)])


def sport_nutrition(
    conn: sqlite3.Connection, kind: Literal["protocol", "supplement"]
) -> dict[str, Any]:
    """Протоколы спортивного питания (kind=protocol) или добавки (kind=supplement), живые."""
    found = list_protocols(conn) if kind == "protocol" else list_supplements(conn)
    return cap([without_service(row) for row in found])


def sport_nutrition_for(
    conn: sqlite3.Connection,
    date: str,  # noqa: F811 - имя параметра для MCP, затеняет импорт date
) -> dict[str, Any]:
    """Питание к тренировкам дня (без отменённых): по каждой before / during / after, water_only
    (короче 75 минут - во время только вода), duration_unknown (длительности нет - спросить
    пользователя). supplements: daily всегда, остальные - в день тренировки; taken - добавка
    сегодня уже принята."""
    parse_day(date)
    return day_nutrition(conn, date)


def supplement_log(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, Any]:
    """Приёмы добавок за период (включительно): id, item_id, name, date, taken_at, dose (None -
    по норме добавки), unit, note. Только чтение: приём отмечает пользователь."""
    period(date_from, date_to)
    return cap(list_intake(conn, date_from, date_to), newest=True)


def meds(
    conn: sqlite3.Connection,
    date: str | None = None,  # noqa: F811 - имя параметра для MCP, затеняет импорт date
) -> dict[str, Any]:
    """Курсы витаминов и безрецептурных средств: на дату (date) или все живые (без date)."""
    return cap(public_meds(conn, parse_day(date).isoformat() if date else None))


def now() -> datetime:
    return datetime.now()


def today() -> date:
    return date.today()


def _hr_params(
    conn: sqlite3.Connection, end: str
) -> tuple[float, dict[str, dict[str, Any]], list[str]]:
    """Пульс покоя (последний из сна в базе, не старше 14 дней), пороги по видам спорта и
    предупреждения о видах без порога. Нет пульса покоя или порог не больше него — ToolError."""
    found = last_rest_hr(conn, end)
    if found is None or (parse_day(end) - parse_day(found[0])).days > REST_HR_MAX_AGE_DAYS:
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
    period(start, end)
    rest_hr, thresholds, warnings = _hr_params(conn, end)
    lthr_by_sport = {sport: t["lthr"] for sport, t in thresholds.items()}
    tss = daily_tss(conn, shift_day(start, -LOAD_WARMUP_DAYS), end, rest_hr, lthr_by_sport)
    result = cap([row for row in load_series(tss) if row["date"] >= start], newest=True)
    result["thresholds"] = thresholds
    result["warnings"] = warnings
    return result


def create_draft_workout(
    conn: sqlite3.Connection, date: str, sport: str, name: str, spec: dict[str, Any]
) -> dict[str, Any]:
    """Черновик тренировки плана (status=draft). spec проверяется сборкой JSON Garmin
    (workouts.build_workout); name подставляется в spec."""
    parse_day(date)
    if sport not in SPORTS:
        raise ToolError(f"sport должен быть из {list(SPORTS)}, получено: {sport!r}")
    if sport == WEEKEND_ONLY_SPORT and parse_day(date).weekday() < SATURDAY:
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
    groups: list[str],
) -> dict[str, Any]:
    """КБЖУ записи еды (оценка тренера) и группы продуктов (обязательны; нет групп - []). Только
    для записи без КБЖУ: посчитанные не меняет."""
    if not all(0 <= x <= MAX_NUTRITION for x in (kcal, protein_g, fat_g, carbs_g)):
        raise ToolError(f"КБЖУ записи: ккал и граммы от 0 до {MAX_NUTRITION}.")
    check_groups(groups)
    values = {"kcal": kcal, "protein_g": protein_g, "fat_g": fat_g, "carbs_g": carbs_g}
    with conn:
        saved = update_food(conn, food_id, values)
        if saved:
            add_food_groups(conn, food_id, groups)
    if not saved:
        row = fetch_one(conn, "SELECT deleted_at FROM food_log WHERE id = ?", (food_id,))
        if row is None:
            raise ToolError(f"Записи еды {food_id} нет.")
        if row["deleted_at"] is not None:
            raise ToolError(f"Запись еды {food_id} удалена.")
        raise ToolError(f"У записи {food_id} КБЖУ уже посчитано.")
    return {"food_id": food_id}


def check_groups(groups: list[str]) -> None:
    """Неизвестный ключ группы продуктов - ToolError со списком допустимых."""
    unknown = [g for g in groups if g not in FOOD_GROUPS]
    if unknown:
        raise ToolError(f"Неизвестные группы {unknown}. Допустимые: {', '.join(FOOD_GROUPS)}.")


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
