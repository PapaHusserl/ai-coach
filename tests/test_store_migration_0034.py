"""Шаг П12, партия 2: миграция 0034, таблицы forms и form_log (строки coach_events не правятся)."""

import sqlite3
from importlib import resources
from pathlib import Path

from ai_coach.store.db import open_db, schema_version


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_from_33(tmp_path: Path) -> sqlite3.Connection:
    """База версии 33 с чек-инами разных опросников."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v33.db")
    for number in range(1, 34):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    for title, survey in (("Чек-ин", "evening"), ("Самочувствие", "feel"), ("WHO-5", "who5")):
        old.execute(
            "INSERT INTO coach_events (kind, title, date, start_at, end_at, created_at, survey) "
            "VALUES ('checkin', ?, '2026-11-14', '2026-11-14T21:00:00', '2026-11-14T21:15:00', "
            "'2026-11-13T09:00:00', ?)",
            (title, survey),
        )
    old.commit()
    old.close()
    return open_db(tmp_path / "v33.db")


def test_schema_version_is_at_least_34(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 34


def test_forms_table_has_columns(conn: sqlite3.Connection) -> None:
    expected = {"name", "title", "fields_json", "created_at", "archived_at"}
    assert expected <= columns(conn, "forms")


def test_form_log_table_has_columns(conn: sqlite3.Connection) -> None:
    expected = {"date", "time", "event_id", "form", "values_json", "text", "wellbeing_id"}
    assert expected <= columns(conn, "form_log")


def test_migration_leaves_old_events_untouched(tmp_path: Path) -> None:
    conn = migrate_from_33(tmp_path)
    try:
        assert schema_version(conn) >= 34
        rows = conn.execute("SELECT title, survey FROM coach_events ORDER BY id").fetchall()
        assert [(r["title"], r["survey"]) for r in rows] == [
            ("Чек-ин", "evening"),
            ("Самочувствие", "feel"),
            ("WHO-5", "who5"),
        ]
    finally:
        conn.close()


def test_migration_creates_empty_form_tables(tmp_path: Path) -> None:
    conn = migrate_from_33(tmp_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM forms").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM form_log").fetchone()[0] == 0
    finally:
        conn.close()
