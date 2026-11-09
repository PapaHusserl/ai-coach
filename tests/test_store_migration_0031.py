import sqlite3

from ai_coach.store.db import schema_version

COLUMNS = {
    "id",
    "event_id",
    "date",
    "position",
    "name",
    "items_json",
    "kcal",
    "protein_g",
    "fat_g",
    "carbs_g",
    "groups_json",
    "created_at",
}


def test_schema_version_is_at_least_31(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 31


def test_meal_offer_has_planned_columns(conn: sqlite3.Connection) -> None:
    names = {row["name"] for row in conn.execute("PRAGMA table_info(meal_offer)")}
    assert names >= COLUMNS


def test_meal_offer_starts_empty(conn: sqlite3.Connection) -> None:
    assert conn.execute("SELECT COUNT(*) FROM meal_offer").fetchone()[0] == 0
