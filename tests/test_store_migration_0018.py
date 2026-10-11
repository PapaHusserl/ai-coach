import sqlite3

import pytest

from ai_coach.store.db import schema_version

DONE = "'2026-10-12 09:00:00'"


def test_schema_version_is_at_least_18(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 18


def columns(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {r[1]: r for r in conn.execute("PRAGMA table_info(review_log)").fetchall()}


def test_review_log_columns(conn: sqlite3.Connection) -> None:
    assert {"week_start", "done_at", "note"} <= set(columns(conn))


def test_week_start_is_primary_key(conn: sqlite3.Connection) -> None:
    assert columns(conn)["week_start"]["pk"] == 1


def test_done_at_is_required(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO review_log (week_start) VALUES ('2026-10-05')")


def test_note_may_be_null(conn: sqlite3.Connection) -> None:
    conn.execute(f"INSERT INTO review_log (week_start, done_at) VALUES ('2026-10-05', {DONE})")
    assert conn.execute("SELECT note FROM review_log").fetchone()[0] is None


def test_week_start_is_unique(conn: sqlite3.Connection) -> None:
    sql = f"INSERT INTO review_log (week_start, done_at) VALUES ('2026-10-05', {DONE})"
    conn.execute(sql)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)
