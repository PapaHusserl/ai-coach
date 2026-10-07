import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version


def test_schema_version_is_at_least_10(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 10


@pytest.mark.parametrize("table", ["weight_log", "food_log"])
def test_table_has_deleted_at(conn: sqlite3.Connection, table: str) -> None:
    columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    assert "deleted_at" in columns


@pytest.mark.parametrize("table", ["weight_log", "food_log"])
def test_deleted_at_is_nullable_text(conn: sqlite3.Connection, table: str) -> None:
    info = {r[1]: r for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    assert info["deleted_at"][2].upper() == "TEXT"
    assert info["deleted_at"][3] == 0


def test_new_rows_are_alive(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO weight_log (measured_at, weight_kg) VALUES ('2026-10-07 07:00:00', 80)"
    )
    conn.execute("INSERT INTO food_log (logged_at, text) VALUES ('2026-10-07 08:00:00', 'каша')")
    assert conn.execute("SELECT deleted_at FROM weight_log").fetchone()[0] is None
    assert conn.execute("SELECT deleted_at FROM food_log").fetchone()[0] is None


def test_migration_keeps_old_rows_and_ids(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v9.db")
    for number in range(1, 10):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO weight_log (id, measured_at, weight_kg)"
        " VALUES (4, '2026-10-01 07:00:00', 81.5)"
    )
    old.execute(
        "INSERT INTO food_log (id, logged_at, text, kcal, protein_g, fat_g, carbs_g)"
        " VALUES (7, '2026-10-01 08:00:00', 'каша', 350, 12, 6, 60)"
    )
    old.execute(
        "INSERT INTO food_log (id, logged_at, text) VALUES (9, '2026-10-01 13:00:00', 'суп')"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v9.db")
    try:
        weights = conn.execute(
            "SELECT id, measured_at, weight_kg, deleted_at FROM weight_log"
        ).fetchall()
        assert [tuple(r) for r in weights] == [(4, "2026-10-01 07:00:00", 81.5, None)]
        food = conn.execute(
            "SELECT id, logged_at, text, kcal, protein_g, fat_g, carbs_g, deleted_at"
            " FROM food_log ORDER BY id"
        ).fetchall()
        assert [tuple(r) for r in food] == [
            (7, "2026-10-01 08:00:00", "каша", 350, 12, 6, 60, None),
            (9, "2026-10-01 13:00:00", "суп", None, None, None, None, None),
        ]
    finally:
        conn.close()
