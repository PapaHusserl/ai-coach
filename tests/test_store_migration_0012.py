import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

NOW = "'2026-10-07 10:00:00'"


def test_schema_version_is_at_least_12(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 12


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def protocol(phase: str = "before", sport: str = "NULL", **fields: str) -> str:
    base = {"name": "'гель'", "min": "0", "off": "30", "c": "30", "p": "0", "f": "0", "s": "0"}
    base |= fields
    return (
        "INSERT INTO nutrition_protocol (name, phase, sport, min_duration_min, offset_min,"
        " carbs_g, protein_g, fluid_ml, sodium_mg, created_at, updated_at) VALUES "
        f"({base['name']}, '{phase}', {sport}, {base['min']}, {base['off']}, {base['c']},"
        f" {base['p']}, {base['f']}, {base['s']}, {NOW}, {NOW})"
    )


def supplement(**fields: str) -> str:
    base = {"name": "'креатин'", "dose": "5", "unit": "'g'", "schedule": "'daily'"}
    base |= fields
    return (
        "INSERT INTO supplement (name, dose, unit, schedule, created_at, updated_at) VALUES "
        f"({base['name']}, {base['dose']}, {base['unit']}, {base['schedule']}, {NOW}, {NOW})"
    )


def test_protocol_has_expected_columns(conn: sqlite3.Connection) -> None:
    expected = {
        "id",
        "name",
        "phase",
        "sport",
        "min_duration_min",
        "offset_min",
        "carbs_g",
        "protein_g",
        "fluid_ml",
        "sodium_mg",
        "note",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected <= columns(conn, "nutrition_protocol")


def test_supplement_has_expected_columns(conn: sqlite3.Connection) -> None:
    expected = {
        "id",
        "name",
        "dose",
        "unit",
        "schedule",
        "time_note",
        "note",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected <= columns(conn, "supplement")


def test_new_protocol_is_alive(conn: sqlite3.Connection) -> None:
    conn.execute(protocol())
    row = conn.execute("SELECT deleted_at, sport FROM nutrition_protocol").fetchone()
    assert row[:] == (None, None)


@pytest.mark.parametrize("phase", ["before", "during", "after"])
def test_protocol_phase_is_allowed(conn: sqlite3.Connection, phase: str) -> None:
    conn.execute(protocol(phase=phase))


def test_protocol_bad_phase_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(protocol(phase="always"))


@pytest.mark.parametrize("sport", ["strength", "mobility", "run", "bike", "swim"])
def test_protocol_sport_is_allowed(conn: sqlite3.Connection, sport: str) -> None:
    conn.execute(protocol(sport=f"'{sport}'"))


def test_protocol_bad_sport_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(protocol(sport="'yoga'"))


@pytest.mark.parametrize("field", ["c", "p", "f", "s"])
def test_protocol_negative_amount_is_refused(conn: sqlite3.Connection, field: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(protocol(**{field: "-1"}))


def test_protocol_name_is_unique_among_alive(conn: sqlite3.Connection) -> None:
    conn.execute(protocol())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(protocol())


def test_protocol_name_can_repeat_after_delete(conn: sqlite3.Connection) -> None:
    conn.execute(protocol())
    conn.execute("UPDATE nutrition_protocol SET deleted_at = '2026-10-07 12:00:00'")
    conn.execute(protocol())


@pytest.mark.parametrize("unit", ["g", "mg", "ml", "pcs"])
def test_supplement_unit_is_allowed(conn: sqlite3.Connection, unit: str) -> None:
    conn.execute(supplement(unit=f"'{unit}'"))


def test_supplement_bad_unit_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(supplement(unit="'kg'"))


@pytest.mark.parametrize("dose", ["0", "-1"])
def test_supplement_dose_must_be_positive(conn: sqlite3.Connection, dose: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(supplement(dose=dose))


@pytest.mark.parametrize("schedule", ["daily", "training_day", "before", "after"])
def test_supplement_schedule_is_allowed(conn: sqlite3.Connection, schedule: str) -> None:
    conn.execute(supplement(schedule=f"'{schedule}'"))


def test_supplement_bad_schedule_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(supplement(schedule="'weekly'"))


def test_supplement_name_is_unique_among_alive(conn: sqlite3.Connection) -> None:
    conn.execute(supplement())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(supplement())


def test_supplement_name_can_repeat_after_delete(conn: sqlite3.Connection) -> None:
    conn.execute(supplement())
    conn.execute("UPDATE supplement SET deleted_at = '2026-10-07 12:00:00'")
    conn.execute(supplement())


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v11.db")
    for number in range(1, 12):
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
        "INSERT INTO recipe (id, name, kcal_100, protein_100, fat_100, carbs_100, created_at,"
        " updated_at) VALUES (3, 'плов', 150, 8, 5, 18, '2026-10-01 08:00:00',"
        " '2026-10-01 08:00:00')"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v11.db")
    try:
        assert schema_version(conn) >= 12
        assert conn.execute("SELECT id, text, kcal FROM food_log").fetchone()[:] == (7, "каша", 350)
        assert conn.execute("SELECT id, name FROM recipe").fetchone()[:] == (3, "плов")
        assert conn.execute("SELECT COUNT(*) FROM nutrition_protocol").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM supplement").fetchone()[0] == 0
    finally:
        conn.close()
