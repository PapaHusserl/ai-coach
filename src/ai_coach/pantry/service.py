"""Продукты дома: остаток считается по журналу pantry_log."""

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ai_coach.pantry.batches import batches_of, sort_key
from ai_coach.store.pantry import add_entry, list_entries

UNITS = ("g", "ml", "pcs")
OPS = ("add", "use", "set", "open", "spoil")


def normalize(item: str) -> str:
    """Название: нижний регистр, без лишних пробелов."""
    return " ".join(item.lower().split())


def _unit_of(conn: sqlite3.Connection, item: str) -> str | None:
    entries = list_entries(conn, item)
    return entries[0]["unit"] if entries else None


def _stock_of(entries: list[dict[str, Any]]) -> float:
    return sum(batch["qty"] for batch in batches_of(entries))


@dataclass
class PantryEntry:
    """Запись журнала. op: add/use/set/open/spoil; now - время записи; expires_on - срок годности
    YYYY-MM-DD (у add, set, open); opened - упаковка открыта. open: qty 0, срок обязателен."""

    op: str
    item: str
    qty: float
    unit: str
    now: str
    expires_on: str | None = None
    opened: bool = False


def record(conn: sqlite3.Connection, entry: PantryEntry) -> str | None:
    """Добавить запись. Ошибка - ValueError, ничего не записано. Если use или spoil больше
    остатка - остаток 0 и в ответе предупреждение."""
    op, item, qty, unit, now = entry.op, entry.item, entry.qty, entry.unit, entry.now
    expires_on = entry.expires_on
    name = normalize(item)
    if op not in OPS:
        raise ValueError(f"Операция должна быть из {list(OPS)}, получено: {op!r}")
    if not name:
        raise ValueError("Название продукта пустое.")
    if unit not in UNITS:
        raise ValueError(f"Единица должна быть из {list(UNITS)}, получено: {unit!r}")
    if qty < 0 or (qty == 0 and op not in ("set", "open")):
        raise ValueError("Количество должно быть больше 0 (для set можно 0).")
    if expires_on is not None:
        try:
            date.fromisoformat(expires_on)
        except ValueError:
            raise ValueError(f"Срок должен быть YYYY-MM-DD, получено: {expires_on!r}") from None
    if op == "open" and expires_on is None:
        raise ValueError("Для open нужен срок годности.")
    known = _unit_of(conn, name)
    if known is not None and known != unit:
        raise ValueError(f"У продукта {name!r} единица {known}, а не {unit}.")
    if op in ("use", "spoil", "open") and known is None:
        raise ValueError(f"Продукта {name!r} нет дома.")
    if op == "open" and _stock_of(list_entries(conn, name)) <= 0:
        raise ValueError(f"Продукта {name!r} нет дома.")
    warning = None
    if op in ("use", "spoil") and qty > _stock_of(list_entries(conn, name)):
        warning = f"{name}: списано больше остатка, остаток 0."
    values = {"item": name, "qty": qty, "unit": unit, "op": op, "logged_at": now}
    if expires_on is not None:
        values["expires_on"] = expires_on
    if entry.opened or op == "open":
        values["opened"] = 1
    add_entry(conn, values)
    return warning


def _stockbatches_of(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """По продукту с остатком больше 0: item, unit, updated_at, batches (партии)."""
    by_item: dict[str, list[dict[str, Any]]] = {}
    for entry in list_entries(conn):
        by_item.setdefault(entry["item"], []).append(entry)
    result: list[dict[str, Any]] = []
    for item, entries in sorted(by_item.items()):
        batches = batches_of(entries)
        if sum(batch["qty"] for batch in batches) > 0:
            result.append(
                {
                    "item": item,
                    "unit": entries[0]["unit"],
                    "updated_at": entries[-1]["logged_at"],
                    "batches": batches,
                }
            )
    return result


def stock(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Что есть дома (остаток больше 0): item, qty, unit, updated_at (время последней записи),
    expires_on (ближайший срок или None), opened (0/1 - открыта ближайшая партия)."""
    rows: list[dict[str, Any]] = []
    for found in _stockbatches_of(conn):
        first = min(found["batches"], key=sort_key)
        rows.append(
            {
                "item": found["item"],
                "qty": sum(batch["qty"] for batch in found["batches"]),
                "unit": found["unit"],
                "updated_at": found["updated_at"],
                "expires_on": first["expires_on"],
                "opened": first["opened"],
            }
        )
    return rows


def _latebatches_of(conn: sqlite3.Connection, limit: str, before: bool) -> list[dict[str, Any]]:
    """Партии со сроком <= limit (или < limit при before): item, qty, unit, expires_on, opened."""
    rows: list[dict[str, Any]] = []
    for found in _stockbatches_of(conn):
        late = [
            b
            for b in found["batches"]
            if b["expires_on"] is not None
            and (b["expires_on"] < limit if before else b["expires_on"] <= limit)
        ]
        if late:
            first = min(late, key=sort_key)
            rows.append(
                {
                    "item": found["item"],
                    "qty": sum(b["qty"] for b in late),
                    "unit": found["unit"],
                    "expires_on": first["expires_on"],
                    "opened": first["opened"],
                }
            )
    return rows


def expiring(conn: sqlite3.Connection, today: str, days: int = 2) -> list[dict[str, Any]]:
    """Что истекает в пределах days дней (включая сегодня) и что просрочено: item, qty (только
    такие партии), unit, expires_on (ближайший), opened, expired (срок раньше today)."""
    limit = (date.fromisoformat(today) + timedelta(days=days)).isoformat()
    rows = _latebatches_of(conn, limit, False)
    for row in rows:
        row["expired"] = row["expires_on"] < today
    return sorted(rows, key=lambda row: (row["expires_on"], row["item"]))


def spoil(
    conn: sqlite3.Connection,
    item: str,
    qty: float | None,
    unit: str | None,
    now: str,
    today: str,
) -> tuple[float, str, str | None]:
    """Списать порчей. Без qty - весь просроченный остаток (срок раньше today). Возвращает
    (сколько, единица, предупреждение). Нечего списывать - ValueError."""
    name = normalize(item)
    if qty is not None and unit is not None:
        warning = record(conn, PantryEntry("spoil", name, qty, unit, now))
        return qty, unit, warning
    found = [row for row in _latebatches_of(conn, today, True) if row["item"] == name]
    if not found:
        raise ValueError(f"У продукта {name!r} нет просроченного остатка.")
    warning = record(conn, PantryEntry("spoil", name, found[0]["qty"], found[0]["unit"], now))
    return found[0]["qty"], found[0]["unit"], warning


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
