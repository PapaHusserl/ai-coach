import sqlite3
from typing import Any

import pytest

from ai_coach.pantry.service import PantryEntry, expiring, stock
from ai_coach.pantry.service import record as save


def record(
    conn: sqlite3.Connection, op: str, item: str, qty: float, unit: str, now: str, **fields: Any
) -> str | None:
    return save(conn, PantryEntry(op, item, qty, unit, now, **fields))


T1 = "2026-10-01T10:00:00"
T2 = "2026-10-02T10:00:00"
T3 = "2026-10-03T10:00:00"
TODAY = "2026-10-07"


def row_of(conn: sqlite3.Connection, item: str) -> dict:
    return [r for r in stock(conn) if r["item"] == item][0]


def amounts(conn: sqlite3.Connection) -> dict[str, float]:
    return {r["item"]: r["qty"] for r in stock(conn)}


def expiring_items(conn: sqlite3.Connection, today: str = TODAY, days: int = 2) -> list[str]:
    return [r["item"] for r in expiring(conn, today, days)]


def test_add_with_expiry_shows_in_stock(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1000, "ml", T1, expires_on="2026-10-10", opened=True)
    row = row_of(conn, "молоко")
    assert row["expires_on"] == "2026-10-10"
    assert row["opened"]


def test_add_without_expiry_has_no_expires_on_and_is_closed(conn: sqlite3.Connection) -> None:
    record(conn, "add", "рис", 1000, "g", T1)
    row = row_of(conn, "рис")
    assert row["expires_on"] is None
    assert not row["opened"]


def test_add_with_bad_expiry_date_is_an_error_and_writes_nothing(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        record(conn, "add", "молоко", 1, "ml", T1, expires_on="завтра")
    assert conn.execute("SELECT count(*) FROM pantry_log").fetchone()[0] == 0


def test_open_changes_expiry_and_keeps_qty(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1000, "ml", T1, expires_on="2026-10-20")
    record(conn, "open", "молоко", 0, "ml", T2, expires_on="2026-10-09")
    row = row_of(conn, "молоко")
    assert row["qty"] == 1000
    assert row["expires_on"] == "2026-10-09"
    assert row["opened"]


def test_open_on_unknown_item_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        record(conn, "open", "молоко", 0, "ml", T1, expires_on="2026-10-09")


def test_spoil_reduces_stock(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1000, "ml", T1, expires_on="2026-10-05")
    record(conn, "spoil", "молоко", 400, "ml", T2)
    assert amounts(conn) == {"молоко": 600}


def test_spoil_everything_removes_item_from_stock(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1000, "ml", T1, expires_on="2026-10-05")
    record(conn, "spoil", "молоко", 1000, "ml", T2)
    assert amounts(conn) == {}


def test_spoil_is_written_to_log_as_op_spoil(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1000, "ml", T1, expires_on="2026-10-05")
    record(conn, "spoil", "молоко", 400, "ml", T2)
    ops = [r[0] for r in conn.execute("SELECT op FROM pantry_log ORDER BY id")]
    assert ops == ["add", "spoil"]


def test_spoil_unknown_item_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        record(conn, "spoil", "молоко", 100, "ml", T1)


def test_spoil_with_other_unit_is_an_error(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1000, "ml", T1)
    with pytest.raises(ValueError):
        record(conn, "spoil", "молоко", 1, "pcs", T2)


def test_expiring_includes_today(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1, "pcs", T1, expires_on="2026-10-07")
    assert expiring_items(conn) == ["молоко"]


def test_expiring_includes_today_plus_two_days(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1, "pcs", T1, expires_on="2026-10-09")
    assert expiring_items(conn) == ["молоко"]


def test_expiring_excludes_today_plus_three_days(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1, "pcs", T1, expires_on="2026-10-10")
    assert expiring_items(conn) == []


def test_expiring_includes_overdue(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1, "pcs", T1, expires_on="2026-10-06")
    assert expiring_items(conn) == ["молоко"]


def test_expiring_includes_long_overdue(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1, "pcs", T1, expires_on="2026-01-01")
    assert expiring_items(conn) == ["молоко"]


def test_expiring_days_parameter(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 1, "pcs", T1, expires_on="2026-10-10")
    assert expiring_items(conn, days=3) == ["молоко"]
    assert expiring_items(conn, days=0) == []


def test_item_without_expiry_is_never_expiring(conn: sqlite3.Connection) -> None:
    record(conn, "add", "рис", 1000, "g", T1)
    assert expiring_items(conn) == []


def test_expiring_row_has_item_qty_unit_and_expires_on(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 500, "ml", T1, expires_on="2026-10-08")
    row = expiring(conn, TODAY)[0]
    assert (row["item"], row["qty"], row["unit"], row["expires_on"]) == (
        "молоко",
        500,
        "ml",
        "2026-10-08",
    )


def test_spoiled_to_zero_item_is_not_expiring(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 500, "ml", T1, expires_on="2026-10-05")
    record(conn, "spoil", "молоко", 500, "ml", T2)
    assert expiring_items(conn) == []


def test_used_up_item_is_not_expiring(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 500, "ml", T1, expires_on="2026-10-08")
    record(conn, "use", "молоко", 500, "ml", T2)
    assert expiring_items(conn) == []


def test_stock_shows_nearest_expiry_of_several_batches(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 100, "ml", T1, expires_on="2026-10-08")
    record(conn, "add", "молоко", 100, "ml", T2, expires_on="2026-10-20")
    row = row_of(conn, "молоко")
    assert row["qty"] == 200
    assert row["expires_on"] == "2026-10-08"


def test_use_takes_from_earliest_batch_first(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 100, "ml", T1, expires_on="2026-10-08")
    record(conn, "add", "молоко", 100, "ml", T2, expires_on="2026-10-20")
    record(conn, "use", "молоко", 100, "ml", T3)
    row = row_of(conn, "молоко")
    assert row["qty"] == 100
    assert row["expires_on"] == "2026-10-20"


def test_spoil_takes_from_earliest_batch_first(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 100, "ml", T1, expires_on="2026-10-05")
    record(conn, "add", "молоко", 100, "ml", T2, expires_on="2026-10-20")
    record(conn, "spoil", "молоко", 100, "ml", T3)
    row = row_of(conn, "молоко")
    assert row["qty"] == 100
    assert row["expires_on"] == "2026-10-20"
    assert expiring_items(conn) == []


def test_partial_use_keeps_earliest_batch_expiry(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 100, "ml", T1, expires_on="2026-10-08")
    record(conn, "add", "молоко", 100, "ml", T2, expires_on="2026-10-20")
    record(conn, "use", "молоко", 50, "ml", T3)
    row = row_of(conn, "молоко")
    assert row["qty"] == 150
    assert row["expires_on"] == "2026-10-08"


def test_set_resets_batches(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 100, "ml", T1, expires_on="2026-10-05")
    record(conn, "set", "молоко", 300, "ml", T2, expires_on="2026-10-30")
    row = row_of(conn, "молоко")
    assert row["qty"] == 300
    assert row["expires_on"] == "2026-10-30"


def test_open_takes_first_closed_batch(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 500, "ml", T1, expires_on="2026-10-08", opened=True)
    record(conn, "add", "молоко", 500, "ml", T1, expires_on="2026-10-20")
    record(conn, "open", "молоко", 0, "ml", T2, expires_on="2026-10-12")
    row = row_of(conn, "молоко")
    assert row["qty"] == 1000
    assert row["expires_on"] == "2026-10-08"
    assert row["opened"]
    assert expiring_items(conn, TODAY, 0) == []
    assert expiring_items(conn, "2026-10-12", 0) == ["молоко"]


def test_open_without_closed_batch_is_an_error(conn: sqlite3.Connection) -> None:
    record(conn, "add", "молоко", 500, "ml", T1, expires_on="2026-10-08", opened=True)
    with pytest.raises(ValueError):
        record(conn, "open", "молоко", 0, "ml", T2, expires_on="2026-10-12")
    assert conn.execute("SELECT count(*) FROM pantry_log").fetchone()[0] == 1
