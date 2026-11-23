"""Шаг П7, партия 6: миграция 0038, таблица weather_hours (почасовой ряд, Р22)."""

import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

HOUR_COLUMNS = {
    "time",
    "temperature",
    "pressure",
    "pressure_surface",
    "humidity",
    "wind",
    "fetched_at",
    "lat",
    "lon",
    "place_source",
    "source",
}


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_from_37(tmp_path: Path) -> sqlite3.Connection:
    """База версии 37 со строками weather_now и weather_days."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v37.db")
    for number in range(1, 38):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO weather_now (observed_at, temperature, apparent, code, wind, pressure, "
        "fetched_at, lat, lon, place_source, utc_offset_seconds) "
        "VALUES ('2026-11-22T14:00', 3.7, 0.3, 2, 3.09, 1018.4, '2026-11-22T14:10:00', "
        "52.52, 13.41, 'macos', 3600)"
    )
    old.execute(
        "INSERT INTO weather_days (date, code, t_max, t_min, precip_prob, fetched_at, lat, lon) "
        "VALUES ('2026-11-22', 80, 5.6, 1.9, 88, '2026-11-22T14:10:00', 52.52, 13.41)"
    )
    old.commit()
    old.close()
    return open_db(tmp_path / "v37.db")


def insert_hour(conn: sqlite3.Connection, **values: object) -> None:
    row: dict[str, object] = {
        "time": "2026-11-22T14:00",
        "temperature": 3.7,
        "pressure": 1018.4,
        "pressure_surface": 1008.4,
        "humidity": 80,
        "wind": 3.0,
        "fetched_at": "2026-11-22T14:10:00",
        "lat": 52.52,
        "lon": 13.41,
        "place_source": "macos",
        "source": "forecast",
    }
    row.update(values)
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO weather_hours ({names}) VALUES ({marks})", list(row.values()))


def test_schema_version_is_at_least_38(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 38


def test_old_base_gets_weather_hours_with_all_columns(tmp_path: Path) -> None:
    conn = migrate_from_37(tmp_path)
    try:
        assert schema_version(conn) >= 38
        assert columns(conn, "weather_hours") == HOUR_COLUMNS
    finally:
        conn.close()


def test_old_weather_rows_survive(tmp_path: Path) -> None:
    conn = migrate_from_37(tmp_path)
    try:
        [now] = conn.execute("SELECT temperature FROM weather_now").fetchall()
        [day] = conn.execute("SELECT t_max FROM weather_days").fetchall()
        assert (now["temperature"], day["t_max"]) == (3.7, 5.6)
    finally:
        conn.close()


def test_repeated_open_changes_nothing(tmp_path: Path) -> None:
    migrate_from_37(tmp_path).close()
    conn = open_db(tmp_path / "v37.db")
    try:
        version = schema_version(conn)
        table = columns(conn, "weather_hours")
        assert table
        conn.close()
        conn = open_db(tmp_path / "v37.db")
        assert schema_version(conn) == version
        assert columns(conn, "weather_hours") == table
        assert conn.execute("SELECT COUNT(*) FROM weather_now").fetchone()[0] == 1
    finally:
        conn.close()


@pytest.mark.parametrize("column", ["pressure", "pressure_surface", "humidity", "wind"])
def test_these_columns_may_be_null(conn: sqlite3.Connection, column: str) -> None:
    insert_hour(conn, **{column: None})
    row = conn.execute(f"SELECT {column} FROM weather_hours").fetchone()
    assert row[0] is None


def test_time_is_the_key(conn: sqlite3.Connection) -> None:
    insert_hour(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_hour(conn)


def test_place_source_outside_macos_and_config_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_hour(conn, place_source="gps")
