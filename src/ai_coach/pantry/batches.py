"""Партии продукта по журналу pantry_log (срок годности, FIFO)."""

from typing import Any


def sort_key(batch: dict[str, Any]) -> tuple[bool, str]:
    """Сначала партии с ближайшим сроком, без срока - в конце."""
    return (batch["expires_on"] is None, batch["expires_on"] or "")


def _consume(batches: list[dict[str, Any]], qty: float) -> None:
    """Списать qty с партий: сначала с ближайшим сроком."""
    while qty > 0 and batches:
        first = min(batches, key=sort_key)
        taken = min(qty, first["qty"])
        first["qty"] -= taken
        qty -= taken
        if first["qty"] <= 0:
            batches.remove(first)


def batches_of(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Партии продукта (qty, expires_on, opened) после всех записей. use и spoil уменьшают партию
    с ближайшим сроком (FIFO), open ставит новый срок этой же партии."""
    batches: list[dict[str, Any]] = []
    for entry in entries:
        batch: dict[str, Any] = {
            "qty": entry["qty"],
            "expires_on": entry.get("expires_on"),
            "opened": entry.get("opened") or 0,
        }
        if entry["op"] == "set":
            batches = [batch] if batch["qty"] > 0 else []
        elif entry["op"] == "add":
            batches.append(batch)
        elif entry["op"] == "open" and batches:
            min(batches, key=sort_key).update(expires_on=batch["expires_on"], opened=1)
        elif entry["op"] in ("use", "spoil"):
            _consume(batches, entry["qty"])
    return batches
