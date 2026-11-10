"""Вкладка «Еда»: вид кладовой с едой дня и запись из пульта (шаг П4, партия 4)."""

import sqlite3
from datetime import date, datetime
from typing import Any

from ai_coach.pantry.service import PantryEntry, expiring, record, spoil, stock
from ai_coach.profile.service import current_profile, profile_nutrition
from ai_coach.store.journal import list_food
from ai_coach.web.errors import MarkError
from ai_coach.web.food import meal_view

PULT_OPS = ("add", "use", "set", "spoil")
SOON_DAYS = 2
FOOD_KEYS = ("id", "text", "kcal", "logged_at")


def pantry_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """Остатки с флагами expired/soon на день просмотра, остаток КБЖУ и еда дня (now не нужен)."""
    iso = day.isoformat()
    late = {row["item"]: row for row in expiring(conn, iso, SOON_DAYS)}
    rows: list[dict[str, Any]] = []
    for row in stock(conn):
        found = late.get(row["item"])
        rows.append(
            {k: row[k] for k in ("item", "qty", "unit", "expires_on", "opened")}
            | {
                "expired": bool(found and found["expired"]),
                "soon": bool(found and not found["expired"]),
            }
        )
    target = profile_nutrition(conn, iso, current_profile(conn, iso))
    food = [{k: r[k] for k in FOOD_KEYS} for r in list_food(conn, iso, iso)]
    return {"rows": rows, "remaining": meal_view(conn, iso, target)["remaining"], "food": food}


def _qty(payload: dict[str, Any], required: bool) -> float | None:
    raw = payload.get("qty")
    if raw is None and not required:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise MarkError("qty: нужно число.")
    return raw


def save_pantry(conn: sqlite3.Connection, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    """add, use, set, spoil (spoil без qty - весь просроченный); ответ {warning}."""
    op, item = payload.get("op"), payload.get("item")
    if op not in PULT_OPS:
        raise MarkError("op: add, use, set или spoil.")
    if not isinstance(item, str):
        raise MarkError("item: нужно название.")
    qty = _qty(payload, op != "spoil")
    unit = payload.get("unit")
    moment = now.isoformat(sep=" ", timespec="seconds")
    try:
        if op == "spoil":
            warning = spoil(conn, item, qty, unit, moment, now.date().isoformat())[2]
        else:
            until = payload.get("until")
            if until is not None and not isinstance(until, str):
                raise MarkError("until: нужна дата YYYY-MM-DD.")
            entry = PantryEntry(
                op, item, float(qty or 0), unit if isinstance(unit, str) else "", moment, until
            )
            warning = record(conn, entry)
    except ValueError as error:
        raise MarkError(str(error)) from None
    return {"warning": warning}
