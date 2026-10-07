import sqlite3
from typing import Any

from mcp_fakes import call, call_text, rows

from ai_coach.mcp_server.tools import MAX_CHARS
from ai_coach.pantry.service import PantryEntry
from ai_coach.pantry.service import record as save


def record(
    conn: sqlite3.Connection, op: str, item: str, qty: float, unit: str, now: str, **fields: Any
) -> str | None:
    return save(conn, PantryEntry(op, item, qty, unit, now, **fields))


DAY = "2026-10-07"
NOW = "2026-10-05T10:00:00"
SNAPSHOT_EXPIRING_ROWS = 10


def expiring(conn: sqlite3.Connection) -> dict:
    return call(conn, "get_morning_snapshot", date=DAY)["pantry_expiring"]


def test_get_pantry_has_expires_on_and_opened(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1000, "ml", NOW, expires_on="2026-10-12", opened=True)
    row = rows(conn, "get_pantry")[0]
    assert row["expires_on"] == "2026-10-12"
    assert row["opened"]


def test_get_pantry_item_without_expiry(conn: sqlite3.Connection) -> None:
    record(conn, "add", "рис", 1000, "g", NOW)
    row = rows(conn, "get_pantry")[0]
    assert row["expires_on"] is None
    assert not row["opened"]


def test_get_pantry_after_open_shows_new_expiry_and_same_qty(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1000, "ml", NOW, expires_on="2026-10-30")
    record(conn, "open", "молоко", 0, "ml", NOW, expires_on="2026-10-09")
    row = rows(conn, "get_pantry")[0]
    assert (row["qty"], row["expires_on"]) == (1000, "2026-10-09")


def test_snapshot_pantry_expiring_is_empty_without_data(conn: sqlite3.Connection) -> None:
    assert expiring(conn)["rows"] == []


def test_snapshot_pantry_expiring_has_expiring_and_overdue(conn: sqlite3.Connection) -> None:
    record(conn, "add", "вчера", 1, "pcs", NOW, expires_on="2026-10-06")
    record(conn, "add", "сегодня", 1, "pcs", NOW, expires_on="2026-10-07")
    record(conn, "add", "плюс два", 1, "pcs", NOW, expires_on="2026-10-09")
    record(conn, "add", "плюс три", 1, "pcs", NOW, expires_on="2026-10-10")
    record(conn, "add", "без срока", 1, "pcs", NOW)
    items = {r["item"] for r in expiring(conn)["rows"]}
    assert items == {"вчера", "сегодня", "плюс два"}


def test_snapshot_pantry_expiring_row_has_item_and_expires_on(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 500, "ml", NOW, expires_on="2026-10-08")
    row = expiring(conn)["rows"][0]
    assert (row["item"], row["expires_on"]) == ("молоко", "2026-10-08")


def test_snapshot_pantry_expiring_skips_spoiled_item(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 500, "ml", NOW, expires_on="2026-10-05")
    record(conn, "spoil", "молоко", 500, "ml", NOW)
    assert expiring(conn)["rows"] == []


def test_snapshot_pantry_expiring_has_at_most_10_rows(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_EXPIRING_ROWS + 10):
        record(conn, "add", f"продукт {number}", 1, "g", NOW, expires_on="2026-10-06")
    result = expiring(conn)
    assert len(result["rows"]) <= SNAPSHOT_EXPIRING_ROWS
    assert result["truncated"] is True


def test_snapshot_pantry_expiring_does_not_break_char_limit(conn: sqlite3.Connection) -> None:
    for number in range(100):
        record(conn, "add", f"продукт {number} " + "я" * 200, 1, "g", NOW, expires_on="2026-10-06")
    assert len(call_text(conn, "get_morning_snapshot", date=DAY)) <= MAX_CHARS


def test_snapshot_pantry_still_has_only_item_qty_unit(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 500, "ml", NOW, expires_on="2026-10-08", opened=True)
    pantry = call(conn, "get_morning_snapshot", date=DAY)["pantry"]
    assert pantry["rows"] == [{"item": "молоко", "qty": 500, "unit": "ml"}]
