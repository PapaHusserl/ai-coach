"""Шаг П7, партия 4: миграция 0037, таблицы weather_now и weather_days."""

import sqlite3
from importlib import resources
from pathlib import Path

from ai_coach.store.db import open_db, schema_version


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_from_36(tmp_path: Path) -> sqlite3.Connection:
    """База версии 36 со строкой самочувствия."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v36.db")
    for number in range(1, 37):
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
    return open_db(tmp_path / "v36.db")


def test_schema_version_is_at_least_37(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 37


def test_old_base_gets_both_tables(tmp_path: Path) -> None:
    conn = migrate_from_36(tmp_path)
    try:
        assert schema_version(conn) >= 37
        assert columns(conn, "weather_now")
        assert columns(conn, "weather_days")
    finally:
        conn.close()


def test_both_tables_have_lat_and_lon(conn: sqlite3.Connection) -> None:
    assert {"lat", "lon"} <= columns(conn, "weather_now")
    assert {"lat", "lon"} <= columns(conn, "weather_days")


def test_weather_now_has_place_source_and_utc_offset(conn: sqlite3.Connection) -> None:
    assert {"place_source", "utc_offset_seconds"} <= columns(conn, "weather_now")


def test_old_data_survives(tmp_path: Path) -> None:
    conn = migrate_from_36(tmp_path)
    try:
        [row] = conn.execute("SELECT text FROM wellbeing_log").fetchall()
        assert row["text"] == "озноб"
    finally:
        conn.close()


def test_repeated_open_changes_nothing(tmp_path: Path) -> None:
    migrate_from_36(tmp_path).close()
    conn = open_db(tmp_path / "v36.db")
    try:
        version = schema_version(conn)
        tables = columns(conn, "weather_now"), columns(conn, "weather_days")
        conn.close()
        conn = open_db(tmp_path / "v36.db")
        assert schema_version(conn) == version
        assert (columns(conn, "weather_now"), columns(conn, "weather_days")) == tables
        assert conn.execute("SELECT COUNT(*) FROM wellbeing_log").fetchone()[0] == 1
    finally:
        conn.close()
