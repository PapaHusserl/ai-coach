import sqlite3

from ai_coach.store.db import schema_version
from ai_coach.store.journal import add_food, list_food


def test_schema_version_is_at_least_42(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 42


def test_food_log_has_offer_id(conn: sqlite3.Connection) -> None:
    found = {r[1] for r in conn.execute("PRAGMA table_info(food_log)").fetchall()}
    assert "offer_id" in found


def test_food_without_offer_has_null_offer_id(conn: sqlite3.Connection) -> None:
    add_food(conn, {"logged_at": "2026-11-08 09:00:00", "text": "каша"})
    assert list_food(conn, "2026-11-08", "2026-11-08")[0]["offer_id"] is None
