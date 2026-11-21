"""Шаг Н49, партия 2: миграция 0035, таблица covid_marks."""

import sqlite3
from importlib import resources
from pathlib import Path

from ai_coach.store.db import open_db, schema_version


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_from_34(tmp_path: Path) -> sqlite3.Connection:
    """База версии 34 со строкой самочувствия."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v34.db")
    for number in range(1, 35):
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
    return open_db(tmp_path / "v34.db")


def test_schema_version_is_at_least_35(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 35


def test_covid_marks_table_has_columns(conn: sqlite3.Connection) -> None:
    assert {"date", "marked_at"} <= columns(conn, "covid_marks")


def test_old_base_opens_and_keeps_data(tmp_path: Path) -> None:
    conn = migrate_from_34(tmp_path)
    try:
        assert schema_version(conn) >= 35
        rows = conn.execute("SELECT text FROM wellbeing_log").fetchall()
        assert [r["text"] for r in rows] == ["озноб"]
        assert conn.execute("SELECT COUNT(*) AS n FROM covid_marks").fetchone()["n"] == 0
    finally:
        conn.close()
