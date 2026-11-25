"""Списание из кладовой по составу варианта блюда («Съел вариант» в пульте)."""

import re
import sqlite3
from typing import Any

from ai_coach.pantry.service import PantryEntry, normalize, record
from ai_coach.store.pantry import list_entries

QTY = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(г|мл|шт)\s*$")
UNITS = {"г": "g", "мл": "ml", "шт": "pcs"}


def parse_qty(text: str) -> tuple[float, str] | None:
    """«150 г» -> (150.0, "g"); «мл» -> ml, «шт» -> pcs; иначе и при количестве 0 - None."""
    found = QTY.match(text)
    if found is None:
        return None
    amount = float(found[1].replace(",", "."))
    return (amount, UNITS[found[2]]) if amount > 0 else None


def use_offer(
    conn: sqlite3.Connection, items: list[dict[str, Any]], food_id: int, now: str
) -> dict[str, list[str]]:
    """Списать строки состава (what, qty), что есть в кладовой под тем же именем и единицей; запись
    use с note «food:<id>». Ответ: used и skipped - «<what> <qty>» как в варианте, warnings."""
    used: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    for item in items:
        line = f"{item['what']} {item['qty']}"
        name = normalize(item["what"])
        amount = parse_qty(item["qty"])
        entries = list_entries(conn, name)
        if amount is None or not entries or entries[0]["unit"] != amount[1]:
            skipped.append(line)
            continue
        entry = PantryEntry("use", name, amount[0], amount[1], now, note=f"food:{food_id}")
        warning = record(conn, entry)
        used.append(line)
        if warning:
            warnings.append(warning)
    return {"used": used, "skipped": skipped, "warnings": warnings}
