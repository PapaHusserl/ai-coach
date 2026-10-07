import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

NOW = "'2026-10-08 10:00:00'"


def test_schema_version_is_at_least_13(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 13


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def med(**fields: str) -> str:
    base = {
        "name": "'витамин D'",
        "kind": "'vitamin'",
        "dose": "25",
        "unit": "'mcg'",
        "schedule": "'daily'",
        "start": "'2026-10-01'",
        "end": "NULL",
    }
    base |= fields
    return (
        "INSERT INTO med_course (name, kind, dose, unit, schedule, start_date, end_date,"
        " created_at, updated_at) VALUES "
        f"({base['name']}, {base['kind']}, {base['dose']}, {base['unit']}, {base['schedule']},"
        f" {base['start']}, {base['end']}, {NOW}, {NOW})"
    )


def test_med_course_has_expected_columns(conn: sqlite3.Connection) -> None:
    expected = {
        "id",
        "name",
        "kind",
        "dose",
        "unit",
        "schedule",
        "time_note",
        "start_date",
        "end_date",
        "note",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected <= columns(conn, "med_course")


def test_new_med_is_alive_and_open_ended(conn: sqlite3.Connection) -> None:
    conn.execute(med())
    row = conn.execute("SELECT deleted_at, end_date FROM med_course").fetchone()
    assert row[:] == (None, None)


@pytest.mark.parametrize("kind", ["vitamin", "mineral", "electrolyte", "otc"])
def test_med_kind_is_allowed(conn: sqlite3.Connection, kind: str) -> None:
    conn.execute(med(kind=f"'{kind}'"))


@pytest.mark.parametrize("kind", ["prescription", "rx", "herb"])
def test_med_bad_kind_is_refused(conn: sqlite3.Connection, kind: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(med(kind=f"'{kind}'"))


@pytest.mark.parametrize("unit", ["mg", "mcg", "iu", "g", "ml", "pcs"])
def test_med_unit_is_allowed(conn: sqlite3.Connection, unit: str) -> None:
    conn.execute(med(unit=f"'{unit}'"))


def test_med_bad_unit_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(med(unit="'kg'"))


@pytest.mark.parametrize("dose", ["0", "-1"])
def test_med_dose_must_be_positive(conn: sqlite3.Connection, dose: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(med(dose=dose))


@pytest.mark.parametrize("schedule", ["daily", "training_day", "before", "after"])
def test_med_schedule_is_allowed(conn: sqlite3.Connection, schedule: str) -> None:
    conn.execute(med(schedule=f"'{schedule}'"))


def test_med_bad_schedule_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(med(schedule="'weekly'"))


def test_med_start_date_is_required(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(med(start="NULL"))


def test_med_end_before_start_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(med(end="'2026-09-30'"))


def test_med_end_equal_to_start_is_allowed(conn: sqlite3.Connection) -> None:
    conn.execute(med(end="'2026-10-01'"))


def test_med_name_is_unique_among_alive(conn: sqlite3.Connection) -> None:
    conn.execute(med())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(med())


def test_med_name_can_repeat_after_delete(conn: sqlite3.Connection) -> None:
    conn.execute(med())
    conn.execute("UPDATE med_course SET deleted_at = '2026-10-08 12:00:00'")
    conn.execute(med())


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v12.db")
    for number in range(1, 13):
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
        "INSERT INTO supplement (id, name, dose, unit, schedule, created_at, updated_at)"
        " VALUES (4, 'креатин', 5, 'g', 'daily', '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v12.db")
    try:
        assert schema_version(conn) >= 13
        assert conn.execute("SELECT id, text, kcal FROM food_log").fetchone()[:] == (7, "каша", 350)
        assert conn.execute("SELECT id, name FROM supplement").fetchone()[:] == (4, "креатин")
        assert conn.execute("SELECT COUNT(*) FROM med_course").fetchone()[0] == 0
    finally:
        conn.close()
