import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

NOW = "'2026-10-08 10:00:00'"


def test_schema_version_is_at_least_14(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 14


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def intake(**fields: str) -> str:
    base = {
        "kind": "'supplement'",
        "item": "1",
        "date": "'2026-10-08'",
        "taken": NOW,
        "dose": "NULL",
    }
    base |= fields
    return (
        "INSERT INTO intake_log (kind, item_id, date, taken_at, dose) VALUES "
        f"({base['kind']}, {base['item']}, {base['date']}, {base['taken']}, {base['dose']})"
    )


def test_intake_log_has_expected_columns(conn: sqlite3.Connection) -> None:
    expected = {"id", "kind", "item_id", "date", "taken_at", "dose", "note", "deleted_at"}
    assert expected <= columns(conn, "intake_log")


def test_new_intake_is_alive_and_has_default_dose(conn: sqlite3.Connection) -> None:
    conn.execute(intake())
    row = conn.execute("SELECT deleted_at, dose, note FROM intake_log").fetchone()
    assert row[:] == (None, None, None)


def test_intake_kind_supplement_is_allowed(conn: sqlite3.Connection) -> None:
    conn.execute(intake(kind="'supplement'"))


@pytest.mark.parametrize("kind", ["med", "protocol", ""])
def test_intake_bad_kind_is_refused(conn: sqlite3.Connection, kind: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(intake(kind=f"'{kind}'"))


@pytest.mark.parametrize("dose", ["0", "-1"])
def test_intake_dose_must_be_positive(conn: sqlite3.Connection, dose: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(intake(dose=dose))


def test_intake_positive_dose_is_allowed(conn: sqlite3.Connection) -> None:
    conn.execute(intake(dose="2.5"))


def test_intake_same_item_and_day_can_repeat(conn: sqlite3.Connection) -> None:
    conn.execute(intake())
    conn.execute(intake())
    assert conn.execute("SELECT COUNT(*) FROM intake_log").fetchone()[0] == 2


def test_intake_log_has_index_on_date(conn: sqlite3.Connection) -> None:
    found = []
    for index in conn.execute("PRAGMA index_list(intake_log)").fetchall():
        found += [r[2] for r in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()]
    assert "date" in found


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v13.db")
    for number in range(1, 14):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO supplement (id, name, dose, unit, schedule, created_at, updated_at)"
        " VALUES (4, 'креатин', 5, 'g', 'daily', '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
    )
    old.execute(
        "INSERT INTO med_course (id, name, kind, dose, unit, schedule, start_date,"
        " created_at, updated_at) VALUES (2, 'витамин D', 'vitamin', 25, 'mcg', 'daily',"
        " '2026-10-01', '2026-10-01 08:00:00', '2026-10-01 08:00:00')"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v13.db")
    try:
        assert schema_version(conn) >= 14
        assert conn.execute("SELECT id, name FROM supplement").fetchone()[:] == (4, "креатин")
        assert conn.execute("SELECT id, name FROM med_course").fetchone()[:] == (2, "витамин D")
        assert conn.execute("SELECT COUNT(*) FROM intake_log").fetchone()[0] == 0
    finally:
        conn.close()
