"""Шаг П7, партия 11: миграция 0040, таблица kp_index (Р37 = 2)."""

import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

KP_COLUMNS = {"time", "kp", "kind", "fetched_at"}


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_from_39(tmp_path: Path) -> sqlite3.Connection:
    """База версии 39 со строкой weather_hours."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v39.db")
    for number in range(1, 40):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO weather_hours (time, temperature, pressure, pressure_surface, humidity, "
        "wind, fetched_at, lat, lon, place_source, source) "
        "VALUES ('2026-11-22T14:00', 3.7, 1018.4, 1008.4, 80, 3.0, '2026-11-22T14:10:00', "
        "52.52, 13.41, 'macos', 'forecast')"
    )
    old.commit()
    old.close()
    return open_db(tmp_path / "v39.db")


def insert_kp(conn: sqlite3.Connection, **values: object) -> None:
    row: dict[str, object] = {
        "time": "2026-11-22T15:00:00",
        "kp": 2.0,
        "kind": "observed",
        "fetched_at": "2026-11-22T14:10:00",
    }
    row.update(values)
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO kp_index ({names}) VALUES ({marks})", list(row.values()))


def test_schema_version_is_at_least_40(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 40


def test_old_base_gets_kp_index_with_exact_columns(tmp_path: Path) -> None:
    conn = migrate_from_39(tmp_path)
    try:
        assert schema_version(conn) >= 40
        assert columns(conn, "kp_index") == KP_COLUMNS
    finally:
        conn.close()


def test_kp_index_has_no_place_columns(conn: sqlite3.Connection) -> None:
    found = columns(conn, "kp_index")
    assert found
    assert not found & {"lat", "lon", "place_source"}


def test_old_weather_tables_survive(tmp_path: Path) -> None:
    conn = migrate_from_39(tmp_path)
    try:
        [hour] = conn.execute("SELECT temperature FROM weather_hours").fetchall()
        assert hour["temperature"] == 3.7
        for table in ("weather_now", "weather_days", "weather_signals"):
            assert columns(conn, table)
    finally:
        conn.close()


def test_repeated_open_changes_nothing(tmp_path: Path) -> None:
    migrate_from_39(tmp_path).close()
    conn = open_db(tmp_path / "v39.db")
    try:
        version = schema_version(conn)
        conn.close()
        conn = open_db(tmp_path / "v39.db")
        assert schema_version(conn) == version
        assert columns(conn, "kp_index") == KP_COLUMNS
        assert conn.execute("SELECT COUNT(*) FROM weather_hours").fetchone()[0] == 1
    finally:
        conn.close()


def test_time_is_the_key(conn: sqlite3.Connection) -> None:
    insert_kp(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_kp(conn)


def test_other_time_is_allowed(conn: sqlite3.Connection) -> None:
    insert_kp(conn)
    insert_kp(conn, time="2026-11-22T18:00:00")
    assert conn.execute("SELECT COUNT(*) FROM kp_index").fetchone()[0] == 2


def test_kp_keeps_fraction(conn: sqlite3.Connection) -> None:
    insert_kp(conn, kp=0.67)
    assert conn.execute("SELECT kp FROM kp_index").fetchone()["kp"] == 0.67
