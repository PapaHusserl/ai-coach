"""Продукты дома: остаток считается по журналу pantry_log."""

import sqlite3
from typing import Any

from ai_coach.store.pantry import add_entry, list_entries

UNITS = ("g", "ml", "pcs")
OPS = ("add", "use", "set")


def normalize(item: str) -> str:
    """Название: нижний регистр, без лишних пробелов."""
    return " ".join(item.lower().split())


def _unit_of(conn: sqlite3.Connection, item: str) -> str | None:
    entries = list_entries(conn, item)
    return entries[0]["unit"] if entries else None


def _stock_of(entries: list[dict[str, Any]]) -> float:
    left = 0.0
    for entry in entries:
        if entry["op"] == "set":
            left = entry["qty"]
        elif entry["op"] == "add":
            left += entry["qty"]
        else:
            left = max(0.0, left - entry["qty"])
    return left


def record(
    conn: sqlite3.Connection, op: str, item: str, qty: float, unit: str, now: str
) -> str | None:
    """Добавить запись (add / use / set). Ошибка — ValueError, ничего не записано. Если use
    больше остатка — остаток 0 и в ответе предупреждение."""
    name = normalize(item)
    if op not in OPS:
        raise ValueError(f"Операция должна быть из {list(OPS)}, получено: {op!r}")
    if not name:
        raise ValueError("Название продукта пустое.")
    if unit not in UNITS:
        raise ValueError(f"Единица должна быть из {list(UNITS)}, получено: {unit!r}")
    if qty < 0 or (qty == 0 and op != "set"):
        raise ValueError("Количество должно быть больше 0 (для set можно 0).")
    known = _unit_of(conn, name)
    if known is not None and known != unit:
        raise ValueError(f"У продукта {name!r} единица {known}, а не {unit}.")
    if op == "use" and known is None:
        raise ValueError(f"Продукта {name!r} нет дома.")
    warning = None
    if op == "use" and qty > _stock_of(list_entries(conn, name)):
        warning = f"{name}: списано больше остатка, остаток 0."
    add_entry(conn, {"item": name, "qty": qty, "unit": unit, "op": op, "logged_at": now})
    return warning


def stock(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Что есть дома (остаток больше 0): item, qty, unit, updated_at (время последней записи)."""
    by_item: dict[str, list[dict[str, Any]]] = {}
    for entry in list_entries(conn):
        by_item.setdefault(entry["item"], []).append(entry)
    rows: list[dict[str, Any]] = []
    for item, entries in sorted(by_item.items()):
        left = _stock_of(entries)
        if left > 0:
            rows.append(
                {
                    "item": item,
                    "qty": left,
                    "unit": entries[0]["unit"],
                    "updated_at": entries[-1]["logged_at"],
                }
            )
    return rows


def missing(conn: sqlite3.Connection, need: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Чего не хватает из need (item, qty, unit): item, qty (сколько докупить), unit."""
    have = {row["item"]: row for row in stock(conn)}
    result: list[dict[str, Any]] = []
    for want in need:
        name = normalize(want["item"])
        found = have.get(name)
        if found is not None and found["unit"] != want["unit"]:
            raise ValueError(f"У продукта {name!r} единица {found['unit']}, а не {want['unit']}.")
        short = want["qty"] - (found["qty"] if found else 0)
        if short > 0:
            result.append({"item": name, "qty": short, "unit": want["unit"]})
    return result


def shopping_list(conn: sqlite3.Connection, need: list[dict[str, Any]]) -> str:
    """Текст списка покупок: строки «- продукт qty unit» для недостающего."""
    lines = [f"- {row['item']} {row['qty']:g} {row['unit']}" for row in missing(conn, need)]
    return "\n".join(lines) if lines else "Всё есть, покупать нечего."
