import sqlite3

import pytest

from ai_coach.store.db import schema_version

INSERT = (
    "INSERT INTO slip_log (date, logged_at, text) VALUES ('2026-10-07', '2026-10-07 12:00:00', ?)"
)


def test_schema_version_is_at_least_27(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 27


def test_slip_log_has_expected_columns(conn: sqlite3.Connection) -> None:
    found = [r[1] for r in conn.execute("PRAGMA table_info(slip_log)").fetchall()]
    assert found == ["id", "date", "logged_at", "text", "event_id"]


def test_slip_log_has_date_index(conn: sqlite3.Connection) -> None:
    indexed = [
        r[2]
        for index in conn.execute("PRAGMA index_list(slip_log)").fetchall()
        for r in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()
    ]
    assert "date" in indexed


def test_text_is_stored(conn: sqlite3.Connection) -> None:
    conn.execute(INSERT, ("бесит",))
    assert conn.execute("SELECT text FROM slip_log").fetchone()[0] == "бесит"


@pytest.mark.parametrize("text", [None, "", "   "])
def test_empty_text_is_rejected(conn: sqlite3.Connection, text: str | None) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT, (text,))
