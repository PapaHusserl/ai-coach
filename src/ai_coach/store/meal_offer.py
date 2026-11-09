"""Варианты блюд к пункту еды (meal_offer): запись тренером, чтение пультом. Без commit."""

import json
import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert

TOTALS = ("kcal", "protein_g", "fat_g", "carbs_g")


def replace_offers(
    conn: sqlite3.Connection, event_id: int, day: str, offers: list[dict[str, Any]]
) -> int:
    """Заменяет варианты пункта event_id за день day: offers - name, items (строки состава),
    groups; итоги - сумма строк. Возвращает число записанных."""
    cancel_offers(conn, event_id, day)
    for position, offer in enumerate(offers, start=1):
        totals = {key: sum(item[key] for item in offer["items"]) for key in TOTALS}
        values = {
            "event_id": event_id,
            "date": day,
            "position": position,
            "name": offer["name"],
            "items_json": offer["items"],
            "groups_json": offer["groups"],
        }
        insert(conn, "meal_offer", values | totals)
    return len(offers)


def cancel_offers(conn: sqlite3.Connection, event_id: int, day: str) -> None:
    conn.execute("DELETE FROM meal_offer WHERE event_id = ? AND date = ?", (event_id, day))


def list_offers(conn: sqlite3.Connection, event_id: int, day: str) -> list[dict[str, Any]]:
    """Варианты пункта за день day по порядку; items и groups - списками."""
    sql = "SELECT * FROM meal_offer WHERE event_id = ? AND date = ? ORDER BY position, id"
    return [_row(r) for r in fetch_all(conn, sql, (event_id, day))]


def get_offer(conn: sqlite3.Connection, offer_id: int) -> dict[str, Any] | None:
    row = fetch_one(conn, "SELECT * FROM meal_offer WHERE id = ?", (offer_id,))
    return _row(row) if row else None


def _row(row: dict[str, Any]) -> dict[str, Any]:
    return row | {"items": json.loads(row["items_json"]), "groups": json.loads(row["groups_json"])}
