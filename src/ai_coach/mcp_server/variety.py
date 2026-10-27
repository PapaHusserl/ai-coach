"""Инструменты MCP: разнообразие питания и нормы нутриентов (отдельно от tools.py из-за размера)."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.mcp_server import tools
from ai_coach.mcp_server.review import MAX_WEEKS
from ai_coach.nutrition.norms import norms_table
from ai_coach.nutrition.variety import variety_week
from ai_coach.review import monday
from ai_coach.store.db import fetch_one
from ai_coach.store.journal import add_food_groups, list_food_without_groups, wellbeing_day


def food_variety(conn: sqlite3.Connection, weeks: int = 4) -> dict[str, Any]:
    """Разнообразие питания: последние weeks ISO-недель (Пн-Вс, от 1 до 12), от старой к новой,
    последняя - текущая неполная (partial). По неделе: week_start, week_end, partial,
    days_with_data, groups (ключ -> дней с группой), low (ниже порога), high (выше планки)."""
    if not 1 <= weeks <= MAX_WEEKS:
        raise ToolError(f"weeks от 1 до {MAX_WEEKS}, получено: {weeks}")
    today = date.fromisoformat(wellbeing_day(datetime.now()))
    first = monday(today) - timedelta(days=7 * (weeks - 1))
    rows: list[dict[str, Any]] = []
    for number in range(weeks):
        start = first + timedelta(days=7 * number)
        end = start + timedelta(days=6)
        rows.append(
            {
                "week_start": start.isoformat(),
                "week_end": end.isoformat(),
                "partial": end > today,
                **variety_week(conn, start),
            }
        )
    return tools.cap(rows)


def food_without_groups(conn: sqlite3.Connection, start: str, end: str) -> dict[str, Any]:
    """Записи еды с КБЖУ, но без групп продуктов, за период; старые первыми."""
    tools.period(start, end)
    return tools.cap(list_food_without_groups(conn, start, end))


def save_food_groups(conn: sqlite3.Connection, food_id: int, groups: list[str]) -> dict[str, Any]:
    """Группы продуктов записи, у которой КБЖУ уже есть, а групп нет. КБЖУ не трогает."""
    tools.check_groups(groups)
    if not groups:
        raise ToolError("Нечего записывать - пропусти запись.")
    row = fetch_one(conn, "SELECT deleted_at, kcal FROM food_log WHERE id = ?", (food_id,))
    if row is None:
        raise ToolError(f"Записи еды {food_id} нет.")
    if row["deleted_at"] is not None:
        raise ToolError(f"Запись еды {food_id} удалена.")
    if row["kcal"] is None:
        raise ToolError(f"У записи {food_id} нет КБЖУ: сначала save_food_nutrition.")
    with conn:
        saved = add_food_groups(conn, food_id, groups)
    if not saved:
        raise ToolError(f"Запись {food_id} уже размечена.")
    return {"food_id": food_id, "groups": list(dict.fromkeys(groups))}


def nutrient_norms(conn: sqlite3.Connection) -> dict[str, Any]:
    """Нормы нутриентов, мужчины: nutrient, norm (МР 2.3.1.0253-21), upper (верхний уровень
    КТС № 299 для суточной дозы БАД; null - не установлен), unit, note, food_typical (типичное
    потребление с едой), food_source, food_confidence, supplement_max (остаток на добавки);
    у витамина D ещё в МЕ."""
    return tools.cap(norms_table())
