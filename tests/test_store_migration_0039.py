"""Шаг П7, партия 8: миграция 0039, таблица weather_signals (Р36 = 2)."""

import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

SIGNAL_COLUMNS = {"date", "kind", "value", "limit_value", "extreme_at", "created_at"}


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_from_38(tmp_path: Path) -> sqlite3.Connection:
    """База версии 38 со строкой weather_hours."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v38.db")
    for number in range(1, 39):
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
    return open_db(tmp_path / "v38.db")


def insert_signal(conn: sqlite3.Connection, **values: object) -> None:
    row: dict[str, object] = {
        "date": "2026-11-22",
        "kind": "pressure_drop",
        "value": 7.0,
        "limit_value": 5,
        "extreme_at": "2026-11-22T19:00",
        "created_at": "2026-11-22T07:20:00",
    }
    row.update(values)
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO weather_signals ({names}) VALUES ({marks})", list(row.values()))


def test_schema_version_is_at_least_39(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 39


def test_old_base_gets_weather_signals_with_all_columns(tmp_path: Path) -> None:
    conn = migrate_from_38(tmp_path)
    try:
        assert schema_version(conn) >= 39
        assert columns(conn, "weather_signals") == SIGNAL_COLUMNS
    finally:
        conn.close()


def test_old_hours_survive(tmp_path: Path) -> None:
    conn = migrate_from_38(tmp_path)
    try:
        [hour] = conn.execute("SELECT temperature FROM weather_hours").fetchall()
        assert hour["temperature"] == 3.7
    finally:
        conn.close()


def test_repeated_open_changes_nothing(tmp_path: Path) -> None:
    migrate_from_38(tmp_path).close()
    conn = open_db(tmp_path / "v38.db")
    try:
        version = schema_version(conn)
        assert columns(conn, "weather_signals") == SIGNAL_COLUMNS
        conn.close()
        conn = open_db(tmp_path / "v38.db")
        assert schema_version(conn) == version
        assert conn.execute("SELECT COUNT(*) FROM weather_hours").fetchone()[0] == 1
    finally:
        conn.close()


def test_date_and_kind_together_are_the_key(conn: sqlite3.Connection) -> None:
    insert_signal(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_signal(conn)


def test_same_day_other_kind_and_other_day_same_kind_are_allowed(conn: sqlite3.Connection) -> None:
    insert_signal(conn)
    insert_signal(conn, kind="temperature_rise")
    insert_signal(conn, date="2026-11-23")
    assert conn.execute("SELECT COUNT(*) FROM weather_signals").fetchone()[0] == 3


def test_extreme_at_keeps_full_local_time(conn: sqlite3.Connection) -> None:
    insert_signal(conn, extreme_at="2026-11-23T03:00")
    row = conn.execute("SELECT extreme_at FROM weather_signals").fetchone()
    assert row["extreme_at"] == "2026-11-23T03:00"
