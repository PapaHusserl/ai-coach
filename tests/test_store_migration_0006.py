import sqlite3

import pytest

from ai_coach.store.db import schema_version


def add(conn: sqlite3.Connection, day: str, score: int, text: str | None, at: str) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, text, logged_at) VALUES (?, ?, ?, ?)",
        (day, score, text, at),
    )


def test_schema_version_is_at_least_6(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 6


def test_wellbeing_log_has_expected_columns(conn: sqlite3.Connection) -> None:
    columns = {r[1] for r in conn.execute("PRAGMA table_info(wellbeing_log)").fetchall()}
    assert {"id", "date", "score", "text", "logged_at"} <= columns


def test_text_is_optional(conn: sqlite3.Connection) -> None:
    add(conn, "2026-10-07", 4, None, "2026-10-07 08:00:00")
    assert conn.execute("SELECT text FROM wellbeing_log").fetchone()[0] is None


def test_several_scores_in_a_day_are_allowed(conn: sqlite3.Connection) -> None:
    add(conn, "2026-10-07", 4, "норм", "2026-10-07 08:00:00")
    add(conn, "2026-10-07", 2, "заболела голова", "2026-10-07 18:00:00")
    assert conn.execute("SELECT count(*) FROM wellbeing_log").fetchone()[0] == 2


@pytest.mark.parametrize("score", [1, 5])
def test_score_limits_are_inclusive(conn: sqlite3.Connection, score: int) -> None:
    add(conn, "2026-10-07", score, None, "2026-10-07 08:00:00")


@pytest.mark.parametrize("score", [0, 6, -1])
def test_score_outside_1_5_is_rejected_by_database(conn: sqlite3.Connection, score: int) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, "2026-10-07", score, None, "2026-10-07 08:00:00")


def test_score_is_required(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO wellbeing_log (date, logged_at) VALUES ('2026-10-07', 'x')")
