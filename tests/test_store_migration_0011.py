import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version


def test_schema_version_is_at_least_11(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 11


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_recipe_has_expected_columns(conn: sqlite3.Connection) -> None:
    expected = {
        "id",
        "name",
        "kcal_100",
        "protein_100",
        "fat_100",
        "carbs_100",
        "yield_g",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected <= columns(conn, "recipe")


def test_recipe_ingredient_has_expected_columns(conn: sqlite3.Connection) -> None:
    assert {"recipe_id", "product", "qty", "unit"} <= columns(conn, "recipe_ingredient")


@pytest.mark.parametrize("column", ["yield_g", "deleted_at"])
def test_recipe_column_is_nullable(conn: sqlite3.Connection, column: str) -> None:
    info = {r[1]: r for r in conn.execute("PRAGMA table_info(recipe)").fetchall()}
    assert info[column][3] == 0


def test_new_recipe_is_alive(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO recipe (name, kcal_100, protein_100, fat_100, carbs_100, created_at,"
        " updated_at) VALUES ('борщ', 60, 3, 2, 8, '2026-10-07 10:00:00', '2026-10-07 10:00:00')"
    )
    assert conn.execute("SELECT deleted_at, yield_g FROM recipe").fetchone()[:] == (None, None)


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v10.db")
    for number in range(1, 11):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO food_log (id, logged_at, text, kcal)"
        " VALUES (7, '2026-10-01 08:00:00', 'каша', 350)"
    )
    old.execute(
        "INSERT INTO weight_log (id, measured_at, weight_kg)"
        " VALUES (4, '2026-10-01 07:00:00', 81.5)"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v10.db")
    try:
        assert schema_version(conn) >= 11
        assert conn.execute("SELECT id, text, kcal FROM food_log").fetchone()[:] == (7, "каша", 350)
        assert conn.execute("SELECT id, weight_kg FROM weight_log").fetchone()[:] == (4, 81.5)
        assert conn.execute("SELECT COUNT(*) FROM recipe").fetchone()[0] == 0
    finally:
        conn.close()
