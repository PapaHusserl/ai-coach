import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version


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


def test_migration_keeps_old_rows_ids_and_index(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v8.db")
    for number in range(1, 9):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"000{number}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO pantry_log (id, item, qty, unit, op, logged_at, note)"
        " VALUES (5, 'рис', 500, 'g', 'add', '2026-10-01T10:00:00', 'заметка')"
    )
    old.execute(
        "INSERT INTO pantry_log (id, item, qty, unit, op, logged_at)"
        " VALUES (9, 'рис', 100, 'g', 'use', '2026-10-02T10:00:00')"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v8.db")
    try:
        rows = conn.execute(
            "SELECT id, item, qty, unit, op, logged_at, note, expires_on, opened"
            " FROM pantry_log ORDER BY id"
        ).fetchall()
        assert [tuple(r) for r in rows] == [
            (5, "рис", 500, "g", "add", "2026-10-01T10:00:00", "заметка", None, None),
            (9, "рис", 100, "g", "use", "2026-10-02T10:00:00", None, None, None),
        ]
        names = {r[1] for r in conn.execute("PRAGMA index_list(pantry_log)").fetchall()}
        assert "pantry_log_item" in names
    finally:
        conn.close()
