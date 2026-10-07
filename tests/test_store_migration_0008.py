import sqlite3
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version


def add(conn: sqlite3.Connection, item: str, qty: float, unit: str, op: str, at: str) -> None:
    conn.execute(
        "INSERT INTO pantry_log (item, qty, unit, op, logged_at) VALUES (?, ?, ?, ?, ?)",
        (item, qty, unit, op, at),
    )


def test_schema_version_is_at_least_8(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 8


def test_pantry_log_has_expected_columns(conn: sqlite3.Connection) -> None:
    columns = {r[1] for r in conn.execute("PRAGMA table_info(pantry_log)").fetchall()}
    assert {"id", "item", "qty", "unit", "op", "logged_at", "note"} <= columns


def test_pantry_log_is_empty_on_new_database(conn: sqlite3.Connection) -> None:
    assert conn.execute("SELECT count(*) FROM pantry_log").fetchone()[0] == 0


def test_migration_applies_on_top_of_version_7(tmp_path: Path) -> None:
    conn = open_db(tmp_path / "coach.db")
    try:
        assert conn.execute("SELECT count(*) FROM profile_log").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM pantry_log").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize("unit", ["g", "ml", "pcs"])
def test_known_units_are_accepted(conn: sqlite3.Connection, unit: str) -> None:
    add(conn, "курица", 1, unit, "add", "2026-10-07T10:00:00")


def test_unknown_unit_is_rejected_by_database(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, "курица", 1, "kg", "add", "2026-10-07T10:00:00")


@pytest.mark.parametrize("op", ["add", "use", "set"])
def test_known_ops_are_accepted(conn: sqlite3.Connection, op: str) -> None:
    add(conn, "курица", 1, "g", op, "2026-10-07T10:00:00")


def test_unknown_op_is_rejected_by_database(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, "курица", 1, "g", "delete", "2026-10-07T10:00:00")


def test_note_is_optional(conn: sqlite3.Connection) -> None:
    add(conn, "курица", 1, "g", "add", "2026-10-07T10:00:00")
    assert conn.execute("SELECT note FROM pantry_log").fetchone()[0] is None


@pytest.mark.parametrize("column", ["item", "qty", "logged_at"])
def test_required_columns_are_not_null(conn: sqlite3.Connection, column: str) -> None:
    values = {"item": "курица", "qty": 1, "logged_at": "x"}
    values[column] = None  # type: ignore[assignment]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO pantry_log (item, qty, unit, op, logged_at) VALUES (?, ?, 'g', 'add', ?)",
            tuple(values.values()),
        )


def test_log_only_grows_for_the_same_item(conn: sqlite3.Connection) -> None:
    add(conn, "курица", 500, "g", "add", "2026-10-01T10:00:00")
    add(conn, "курица", 200, "g", "use", "2026-10-02T10:00:00")
    assert conn.execute("SELECT count(*) FROM pantry_log").fetchone()[0] == 2


def test_index_on_item_and_logged_at_exists(conn: sqlite3.Connection) -> None:
    for index in conn.execute("PRAGMA index_list(pantry_log)").fetchall():
        columns = [r[2] for r in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()]
        if columns == ["item", "logged_at"]:
            return
    pytest.fail("нет индекса (item, logged_at)")


def test_reopening_database_changes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "coach.db"
    first = open_db(path)
    add(first, "курица", 500, "g", "add", "2026-10-07T10:00:00")
    first.commit()
    version = schema_version(first)
    first.close()
    second = open_db(path)
    try:
        assert schema_version(second) == version
        assert [tuple(r) for r in second.execute("SELECT item, qty FROM pantry_log")] == [
            ("курица", 500)
        ]
    finally:
        second.close()
