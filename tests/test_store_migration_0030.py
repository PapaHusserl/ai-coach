import sqlite3

from ai_coach.store.db import schema_version
from ai_coach.store.journal import add_food, list_food, list_food_pending


def test_schema_version_is_at_least_30(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 30


def test_food_log_has_event_id(conn: sqlite3.Connection) -> None:
    found = {r[1] for r in conn.execute("PRAGMA table_info(food_log)").fetchall()}
    assert "event_id" in found


def test_food_from_cli_has_null_event_id(conn: sqlite3.Connection) -> None:
    add_food(conn, {"logged_at": "2026-11-08 09:00:00", "text": "каша"})
    [row] = list_food(conn, "2026-11-08", "2026-11-08")
    assert row["event_id"] is None
    assert [r["text"] for r in list_food_pending(conn)] == ["каша"]


def test_food_keeps_event_id(conn: sqlite3.Connection) -> None:
    add_food(conn, {"logged_at": "2026-11-08 09:00:00", "text": "каша", "event_id": 7})
    assert list_food(conn, "2026-11-08", "2026-11-08")[0]["event_id"] == 7
