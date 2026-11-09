"""Еда в пульте: остаток дня и запись текстом в food_log (без commit)."""

import sqlite3
from typing import Any

from ai_coach.profile.nutrition import remaining
from ai_coach.store.journal import add_food, add_food_groups, list_food
from ai_coach.store.meal_offer import get_offer, list_offers
from ai_coach.web.errors import MarkError


def meal_view(conn: sqlite3.Connection, day: str, target: dict[str, Any]) -> dict[str, Any]:
    """Остаток дня day: {"remaining": {...} | None}; target - цель дня (profile_nutrition).
    Считается раз на день, записи пункта кладёт в meal day._items из marks."""
    return {"remaining": remaining(target, list_food(conn, day, day))}


def offers_view(conn: sqlite3.Connection, event_id: int, day: str) -> list[dict[str, Any]]:
    """Варианты блюд пункта за день day для окна: id, name, items, итоги КБЖУ."""
    keys = ("id", "name", "items", "kcal", "protein_g", "fat_g", "carbs_g")
    return [{k: o[k] for k in keys} for o in list_offers(conn, event_id, day)]


def _offer_entry(conn: sqlite3.Connection, offer_id: Any, base: dict[str, Any]) -> int:
    """Запись варианта: КБЖУ и группы сразу, /coach-food её не считает."""
    valid = type(offer_id) is int and offer_id > 0
    offer = get_offer(conn, offer_id) if valid else None
    if offer is None or offer["event_id"] != base["event_id"] or offer["date"] != base["date"]:
        raise MarkError("Такого варианта у пункта нет.")
    lines = ", ".join(f"{i['what']} {i['qty']}" for i in offer["items"])
    values = {k: offer[k] for k in ("kcal", "protein_g", "fat_g", "carbs_g")}
    text = f"{offer['name']}: {lines}" if lines else offer["name"]
    food_id = add_food(
        conn,
        {"event_id": base["event_id"], "logged_at": base["logged_at"], "text": text} | values,
    )
    add_food_groups(conn, food_id, offer["groups"])
    return food_id


def save_food(conn: sqlite3.Connection, payload: dict[str, Any], base: dict[str, Any]) -> int:
    """Запись еды пункта: text (КБЖУ пусты до /coach-food) или offer_id (вариант тренера, КБЖУ
    и группы сразу), ровно одно. base: event_id, date, logged_at."""
    if "offer_id" in payload:
        if payload.get("text") is not None:
            raise MarkError("Нужен либо текст, либо вариант.")
        return _offer_entry(conn, payload["offer_id"], base)
    value = payload.get("text")
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise MarkError("Текст не может быть пустым.")
    return add_food(
        conn, {"event_id": base["event_id"], "logged_at": base["logged_at"], "text": text}
    )
