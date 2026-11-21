"""Шаг Н38, партия 1: миграция 0036, столбцы fatigue и irritability в wellbeing_log."""

import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_from_35(tmp_path: Path) -> sqlite3.Connection:
    """База версии 35 со строкой самочувствия."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v35.db")
    for number in range(1, 36):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO wellbeing_log (date, logged_at, score, text) "
        "VALUES ('2026-11-18', '2026-11-18 09:00:00', 2, 'озноб')"
    )
    old.commit()
    old.close()
    return open_db(tmp_path / "v35.db")


def insert(conn: sqlite3.Connection, column: str, value: int) -> None:
    conn.execute(
        f"INSERT INTO wellbeing_log (date, logged_at, score, {column}) "
        f"VALUES ('2026-11-19', '2026-11-19 20:00:00', 3, ?)",
        (value,),
    )


def test_schema_version_is_at_least_36(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 36


def test_wellbeing_log_has_new_columns(conn: sqlite3.Connection) -> None:
    assert {"fatigue", "irritability"} <= columns(conn, "wellbeing_log")


def test_old_base_keeps_rows_with_null_new_columns(tmp_path: Path) -> None:
    conn = migrate_from_35(tmp_path)
    try:
        assert schema_version(conn) >= 36
        [row] = conn.execute("SELECT text, fatigue, irritability FROM wellbeing_log").fetchall()
        assert (row["text"], row["fatigue"], row["irritability"]) == ("озноб", None, None)
    finally:
        conn.close()


@pytest.mark.parametrize("column", ["fatigue", "irritability"])
@pytest.mark.parametrize("value", [1, 5])
def test_values_1_and_5_are_accepted(conn: sqlite3.Connection, column: str, value: int) -> None:
    insert(conn, column, value)
    assert conn.execute(f"SELECT {column} FROM wellbeing_log").fetchone()[0] == value


@pytest.mark.parametrize("column", ["fatigue", "irritability"])
@pytest.mark.parametrize("value", [0, 6])
def test_values_0_and_6_are_rejected(conn: sqlite3.Connection, column: str, value: int) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert(conn, column, value)
