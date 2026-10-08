"""MCP-сервер (stdio) для Claude Code: читает агрегаты, пишет черновики и КБЖУ еды."""

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ai_coach.mcp_server import tools
from ai_coach.mcp_server.tools import MAX_CHARS, MAX_ROWS
from ai_coach.store.db import open_db

INSTRUCTIONS = (
    "Данные тренера: агрегаты из базы ai-coach (без сырых ответов Garmin). Даты YYYY-MM-DD. "
    f"Списки — не больше {MAX_ROWS} строк и {MAX_CHARS} символов: ответ {{rows, truncated}}, "
    "truncated=true — что-то отрезано (у рядов по датам остаются самые новые строки). "
    "Записать можно только черновики (create_draft_workout, cancel_draft_workout — только draft, "
    "propose_phase) и КБЖУ записи еды, у которой его ещё нет (save_food_nutrition). "
    "Отправки на часы нет: утверждает и отправляет пользователь командами coach approve/push."
)

# имя инструмента -> (функция из tools.py, описание для Claude)
TOOLS: dict[str, tuple[Callable[..., Any], str]] = {
    "get_morning_snapshot": (
        tools.morning_snapshot,
        "Утренний разбор одним вызовом: метрики, активности, нагрузка, цели, фазы, план, "
        "план/факт, вес, еда за день, продукты дома (до 30 строк), "
        "recipes (имена и КБЖУ на 100 г, до 30), "
        "meal_plan_today (рацион на сегодня уже предложен), "
        "самочувствие за 30 дней (все записи, до 60), отклонения, "
        "sport_nutrition_today (питание к тренировкам дня и добавки с пометкой принято; "
        "нет - не отдаётся), "
        "meds_today (курсы на сегодня; "
        "training_day/before/after - только в день тренировки; нет - не отдаётся). "
        "date — YYYY-MM-DD (сегодня).",
    ),
    "get_daily_metrics": (
        tools.daily_metrics,
        "Сон, HRV, Body Battery, стресс, readiness по дням.",
    ),
    "get_activities": (tools.activities, "Активности за период."),
    "get_strength_sets": (tools.strength_sets, "Подходы силовой активности."),
    "get_goals": (tools.goals_list, "Цели; status: active / done / cancelled, без него — все."),
    "get_goals_on": (tools.goals_on, "Какие цели были на конец дня."),
    "get_phases": (
        tools.phases_list,
        "Фазы; status: proposed / accepted / rejected, без него — все.",
    ),
    "get_plan": (
        tools.plan,
        "Запланированные тренировки (черновики, утверждённые, отправленные).",
    ),
    "get_plan_actual": (
        tools.plan_actual,
        "Сопоставление плана и факта: done / skipped / extra / different.",
    ),
    "get_load": (
        tools.load,
        "TSS, CTL, ATL по дням плюс thresholds: {вид: {lthr, source, date}} и warnings "
        "(виды без порога, их TSS 0) (пульс покоя и "
        "пороги по видам берутся из базы, их кладёт coach sync; source: garmin_lt, "
        "garmin_zones, derived — посчитан по бегу или по max HR).",
    ),
    "get_weights": (tools.weights, "Замеры веса."),
    "get_food": (tools.food, "Записи еды (текст и КБЖУ, если посчитаны)."),
    "get_wellbeing": (
        tools.wellbeing,
        "Самочувствие (оценка 1-5, текст) по времени; основная оценка дня - последняя запись. "
        "Пишет пользователь командой coach feel.",
    ),
    "get_deviations": (
        tools.deviations,
        "Отклонения за день (плохое самочувствие, readiness, HRV, сон, ATL - CTL); пустой "
        "список - всё в норме, пересчёт плана не нужен. date - YYYY-MM-DD.",
    ),
    "get_profile": (
        tools.profile,
        "Профиль спортсмена на дату (по умолчанию сегодня): пол, возраст, рост, вес, уровень "
        "активности, травмы, инвентарь, расписание, цель по весу и т.д. с источниками (manual / "
        "garmin), age, weight_kg, resting_hr, missing (что не заполнено; goals - нет целей), "
        "nutrition (BMR, TDEE, kcal_target, белки/жиры/углеводы, допущения). "
        "history=true - ещё и все записи по ключам. "
        "Пишет пользователь командой coach profile set.",
    ),
    "get_pantry": (
        tools.pantry,
        "Продукты дома (остаток больше 0): item, qty, unit (g/ml/pcs), updated_at, "
        "expires_on (ближайший срок годности или null), opened (0/1). "
        "Меняет пользователь командами coach pantry.",
    ),
    "get_recipes": (
        tools.recipes,
        "Справочник рецептов: id, name, kcal_100, protein_100, fat_100, carbs_100 (на 100 г "
        "готового), yield_g (вес готового или null), items (product, qty, unit). "
        "Меняет пользователь командами coach recipe.",
    ),
    "get_sport_nutrition": (
        tools.sport_nutrition,
        "Протоколы спортивного питания (kind=protocol: name, phase before/during/after, sport или "
        "null, min_duration_min, offset_min, carbs_g, protein_g, fluid_ml, sodium_mg - для "
        "during в час, note) или добавки (kind=supplement: name, dose, unit, schedule, time_note, "
        "note). Меняет пользователь командами coach protocol / coach supplement.",
    ),
    "get_sport_nutrition_for": (
        tools.sport_nutrition_for,
        "Питание к тренировкам дня (без отменённых): по каждой before / during / after, "
        "water_only (короче 75 минут - во время только вода), duration_unknown (длительности "
        "нет - спроси пользователя); supplements: daily всегда, остальные в день тренировки, "
        "taken - добавка за этот день уже принята. date - YYYY-MM-DD.",
    ),
    "get_supplement_log": (
        tools.supplement_log,
        "Журнал приёма добавок за период (date_from, date_to - YYYY-MM-DD, до 92 дней): id, "
        "item_id, name, date, taken_at, dose (null - по норме добавки), unit, note. "
        "Отмечает пользователь командами coach supplement take / untake.",
    ),
    "get_meds": (
        tools.meds,
        "Курсы витаминов, минералов, электролитов и безрецептурных средств: name, kind "
        "(vitamin/mineral/electrolyte/otc), dose, unit, schedule, time_note, start_date, "
        "end_date (null - бессрочно), note. date - YYYY-MM-DD: только курсы этого дня "
        "(training_day/before/after - только если в этот день есть тренировка); без date - "
        "все живые курсы, в т.ч. закончившиеся. "
        "Меняет пользователь командами coach med.",
    ),
    "get_food_pending": (
        tools.food_pending,
        "Записи еды без КБЖУ за все дни (для /coach-food).",
    ),
    "save_food_nutrition": (
        tools.save_food_nutrition,
        "Записать КБЖУ (kcal, protein_g, fat_g, carbs_g — на всю порцию записи) для записи "
        "еды без КБЖУ по food_id; посчитанные не меняет.",
    ),
    "create_draft_workout": (
        tools.create_draft_workout,
        "Записать тренировку плана черновиком (draft). sport: strength / mobility / run / "
        "bike / swim; spec — как для сборки тренировки Garmin (упражнения или шаги).",
    ),
    "cancel_draft_workout": (
        tools.cancel_draft_workout,
        "Отменить черновик тренировки по id (только draft; утверждённые и отправленные нельзя).",
    ),
    "propose_phase": (tools.propose_phase, "Предложить фазу (proposed); принимает пользователь."),
}


def bind(func: Callable[..., Any], db_path: str | Path | None) -> Callable[..., Any]:
    """Инструмент без параметра conn: базу открывает на один вызов (путь: аргумент,
    $AI_COACH_DB). MCP строит схему аргументов по сигнатуре, а у tool она (*args, **kwargs),
    поэтому __signature__ копируется из func без первого параметра conn."""

    def tool(*args: Any, **kwargs: Any) -> Any:
        conn = open_db(db_path)
        try:
            return func(conn, *args, **kwargs)
        finally:
            conn.close()

    signature = inspect.signature(func)
    tool.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=list(signature.parameters.values())[1:]
    )
    return tool


def build_server(db_path: str | Path | None = None) -> MCPServer:
    server = MCPServer("ai-coach", instructions=INSTRUCTIONS)
    for name, (func, description) in TOOLS.items():
        server.add_tool(bind(func, db_path), name=name, description=description)
    return server


def main() -> None:
    build_server().run("stdio")
