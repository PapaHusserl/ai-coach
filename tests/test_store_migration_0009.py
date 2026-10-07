import sqlite3

import pytest

from ai_coach.store.db import schema_version


def add(conn: sqlite3.Connection, op: str, expires_on: str | None = None) -> None:
    conn.execute(
        "INSERT INTO pantry_log (item, qty, unit, op, logged_at, expires_on, opened)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("молоко", 1, "ml", op, "2026-10-07T10:00:00", expires_on, 0),
    )


def test_schema_version_is_at_least_9(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 9


def test_pantry_log_has_expires_on_and_opened(conn: sqlite3.Connection) -> None:
    columns = {r[1] for r in conn.execute("PRAGMA table_info(pantry_log)").fetchall()}
    assert {"expires_on", "opened"} <= columns


@pytest.mark.parametrize("op", ["add", "use", "set", "spoil", "open"])
def test_known_ops_are_accepted(conn: sqlite3.Connection, op: str) -> None:
    add(conn, op)


def test_unknown_op_is_rejected_by_database(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, "throw")


def test_expires_on_may_be_null_and_is_stored(conn: sqlite3.Connection) -> None:
    add(conn, "add", None)
    add(conn, "add", "2026-10-10")
    values = [r[0] for r in conn.execute("SELECT expires_on FROM pantry_log ORDER BY id")]
    assert values == [None, "2026-10-10"]


def test_old_columns_are_kept(conn: sqlite3.Connection) -> None:
    columns = {r[1] for r in conn.execute("PRAGMA table_info(pantry_log)").fetchall()}
    assert {"id", "item", "qty", "unit", "op", "logged_at", "note"} <= columns
