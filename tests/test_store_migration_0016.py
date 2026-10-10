import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

NOW = "'2026-10-08 20:00:00'"


def test_schema_version_is_at_least_16(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 16


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def feeling(**fields: str) -> str:
    base = {"score": "3", "mood": "NULL", "stress": "NULL"}
    base |= fields
    return (
        "INSERT INTO wellbeing_log (date, logged_at, score, mood, stress) VALUES "
        f"('2026-10-08', {NOW}, {base['score']}, {base['mood']}, {base['stress']})"
    )


def test_wellbeing_log_has_mood_and_stress(conn: sqlite3.Connection) -> None:
    assert {"id", "date", "logged_at", "score", "text", "mood", "stress"} <= columns(
        conn, "wellbeing_log"
    )


def test_mood_and_stress_may_be_null(conn: sqlite3.Connection) -> None:
    conn.execute(feeling())
    row = conn.execute("SELECT mood, stress FROM wellbeing_log").fetchone()
    assert row[:] == (None, None)


@pytest.mark.parametrize("value", ["1", "5"])
def test_mood_limits_are_inclusive(conn: sqlite3.Connection, value: str) -> None:
    conn.execute(feeling(mood=value))


@pytest.mark.parametrize("value", ["0", "6", "-1"])
def test_bad_mood_is_refused(conn: sqlite3.Connection, value: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(feeling(mood=value))


@pytest.mark.parametrize("value", ["1", "5"])
def test_stress_limits_are_inclusive(conn: sqlite3.Connection, value: str) -> None:
    conn.execute(feeling(stress=value))


@pytest.mark.parametrize("value", ["0", "6", "-1"])
def test_bad_stress_is_refused(conn: sqlite3.Connection, value: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(feeling(stress=value))


def test_score_check_is_still_there(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(feeling(score="6"))


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v15.db")
    for number in range(1, 16):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO wellbeing_log (id, date, logged_at, score, text)"
        " VALUES (7, '2026-10-01', '2026-10-01 08:00:00', 4, 'бодро')"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v15.db")
    try:
        assert schema_version(conn) >= 16
        row = conn.execute("SELECT id, score, text, mood, stress FROM wellbeing_log").fetchone()
        assert row[:] == (7, 4, "бодро", None, None)
    finally:
        conn.close()
