"""MCP-сервер (stdio) для Claude Code: читает агрегаты, пишет только черновики."""

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
    "Записать можно только черновики: create_draft_workout, cancel_draft_workout (только draft) "
    "и propose_phase. "
    "Отправки на часы нет: утверждает и отправляет пользователь командами coach approve/push."
)

# имя инструмента -> (функция из tools.py, описание для Claude)
TOOLS: dict[str, tuple[Callable[..., Any], str]] = {
    "get_morning_snapshot": (
        tools.morning_snapshot,
        "Утренний разбор одним вызовом: метрики, активности, нагрузка, цели, фазы, план, "
        "план/факт, вес, еда за день. date — YYYY-MM-DD (сегодня).",
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
        "TSS, CTL, ATL по дням плюс thresholds: {вид: {lthr, source, date}} (пульс покоя и "
        "пороги по видам берутся из базы, их кладёт coach sync; source: garmin_lt, "
        "garmin_zones, derived — посчитан по бегу или по max HR).",
    ),
    "get_weights": (tools.weights, "Замеры веса."),
    "get_food": (tools.food, "Записи еды (текст и КБЖУ, если посчитаны)."),
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
