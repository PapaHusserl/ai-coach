"""Шаг П11, партия 1: миграция 0033, колонка coach_events.survey (старые строки не правятся)."""

import sqlite3
from importlib import resources
from pathlib import Path

from ai_coach.store.db import open_db, schema_version

INSERT = (
    "INSERT INTO coach_events (kind, title, date, start_at, end_at, created_at, {cols}) "
    "VALUES ('checkin', ?, '2026-11-14', '2026-11-14T21:00:00', '2026-11-14T21:15:00', "
    "'2026-11-13T09:00:00'{marks})"
)


def migrate_from_32(tmp_path: Path) -> sqlite3.Connection:
    """База версии 32 с чек-инами штатных напоминаний."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v32.db")
    for number in range(1, 33):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    for title in ("Чек-ин", "Фокус 1–5?", "Обзор недели", "WHO-5"):
        old.execute(
            "INSERT INTO coach_events (kind, title, date, start_at, end_at, created_at, repeat) "
            "VALUES ('checkin', ?, '2026-11-14', '2026-11-14T21:00:00', '2026-11-14T21:15:00', "
            "'2026-11-13T09:00:00', 'daily')",
            (title,),
        )
    old.commit()
    old.close()
    return open_db(tmp_path / "v32.db")


def test_schema_version_is_at_least_33(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 33


def test_coach_events_has_survey_column(conn: sqlite3.Connection) -> None:
    names = {row["name"] for row in conn.execute("PRAGMA table_info(coach_events)")}
    assert "survey" in names


def test_new_row_has_null_survey_by_default(conn: sqlite3.Connection) -> None:
    conn.execute(INSERT.format(cols="status", marks=", 'draft'"), ("x",))
    assert conn.execute("SELECT survey FROM coach_events").fetchone()[0] is None


def test_survey_value_is_stored(conn: sqlite3.Connection) -> None:
    conn.execute(INSERT.format(cols="survey", marks=", 'feel'"), ("x",))
    assert conn.execute("SELECT survey FROM coach_events").fetchone()[0] == "feel"


def test_migration_leaves_old_checkins_with_null_survey(tmp_path: Path) -> None:
    conn = migrate_from_32(tmp_path)
    try:
        assert schema_version(conn) >= 33
        rows = conn.execute("SELECT title, survey FROM coach_events ORDER BY id").fetchall()
        assert [r["title"] for r in rows] == ["Чек-ин", "Фокус 1–5?", "Обзор недели", "WHO-5"]
        assert [r["survey"] for r in rows] == [None] * 4
    finally:
        conn.close()
