"""Инструменты MCP: варианты блюд к пункту еды (отдельно от tools.py из-за размера).

Пишут варианты для окна еды веб-пульта; запись еды из варианта делает пользователь в пульте.
"""

import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.mcp_server.tools import MAX_NUTRITION, check_groups, parse_day
from ai_coach.store.agenda import get_event
from ai_coach.store.meal_offer import TOTALS, cancel_offers, replace_offers

MAX_OFFERS = 5
MAX_LINES = 12


def _check_offer(offer: dict[str, Any]) -> None:
    name = offer.get("name")
    if not (isinstance(name, str) and name.strip()):
        raise ToolError("У варианта нужно имя (name).")
    items = offer.get("items")
    if not items or len(items) > MAX_LINES:
        raise ToolError(f"В варианте от 1 до {MAX_LINES} строк состава (items).")
    for item in items:
        what = item.get("what")
        if not (isinstance(what, str) and what.strip()):
            raise ToolError("У строки состава нужно what.")
        if not isinstance(item.get("qty"), str):
            raise ToolError("У строки состава нужно qty текстом.")
        values = [item.get(key) for key in TOTALS]
        if not all(isinstance(v, int | float) and 0 <= v <= MAX_NUTRITION for v in values):
            raise ToolError(f"КБЖУ строки: ккал и граммы от 0 до {MAX_NUTRITION}.")
    check_groups(offer.get("groups", []))


def create_meal_offers(
    conn: sqlite3.Connection, event_id: int, date: str, offers: list[dict[str, Any]]
) -> dict[str, Any]:
    """Варианты блюд к пункту еды (meal) event_id за день date (YYYY-MM-DD); прежние варианты
    пункта за этот день заменяются. offers - от 1 до 5: {name, items, groups}; items - строки
    состава (до 12) {what, qty, kcal, protein_g, fat_g, carbs_g} на порцию, итоги варианта -
    сумма строк; groups - ключи групп продуктов (как в save_food_nutrition, нет - [])."""
    day = parse_day(date).isoformat()
    event = get_event(conn, event_id)
    if event is None or event["kind"] != "meal":
        raise ToolError(f"Пункта еды {event_id} нет.")
    if event["date"] != day:
        raise ToolError(f"Пункт еды {event_id} стоит на {event['date']}, а не на {day}.")
    if not 1 <= len(offers) <= MAX_OFFERS:
        raise ToolError(f"Вариантов от 1 до {MAX_OFFERS}.")
    for offer in offers:
        _check_offer(offer)
    clean = [{**o, "groups": o.get("groups", [])} for o in offers]
    with conn:
        count = replace_offers(conn, event_id, day, clean)
    return {"event_id": event_id, "date": day, "offers": count}


def cancel_meal_offers(conn: sqlite3.Connection, event_id: int, date: str) -> dict[str, Any]:
    """Снять варианты блюд пункта еды event_id за день date (YYYY-MM-DD); нет вариантов - не
    ошибка."""
    day = parse_day(date).isoformat()
    with conn:
        cancel_offers(conn, event_id, day)
    return {"event_id": event_id, "date": day}
