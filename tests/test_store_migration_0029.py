import sqlite3

import pytest

from ai_coach.store.db import schema_version

INSERT = "INSERT INTO done_log (event_id, date, done, logged_at) VALUES (1, '2026-11-08', ?, 'x')"


def test_schema_version_is_at_least_29(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 29


@pytest.mark.parametrize("table", ["focus_log", "wellbeing_log", "slip_log"])
def test_logs_have_event_id(conn: sqlite3.Connection, table: str) -> None:
    found = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    assert "event_id" in found


def test_done_log_has_expected_columns(conn: sqlite3.Connection) -> None:
    found = [r[1] for r in conn.execute("PRAGMA table_info(done_log)").fetchall()]
    assert found == ["id", "event_id", "date", "done", "logged_at"]


def test_done_log_has_date_index(conn: sqlite3.Connection) -> None:
    indexed = [
        r[2]
        for index in conn.execute("PRAGMA index_list(done_log)").fetchall()
        for r in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()
    ]
    assert "date" in indexed


def test_second_mark_for_same_event_and_day_is_rejected(conn: sqlite3.Connection) -> None:
    conn.execute(INSERT, (1,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT, (0,))


def test_same_event_on_another_day_is_accepted(conn: sqlite3.Connection) -> None:
    conn.execute(INSERT, (1,))
    conn.execute(INSERT.replace("2026-11-08", "2026-11-09"), (1,))
    assert conn.execute("SELECT COUNT(*) FROM done_log").fetchone()[0] == 2


@pytest.mark.parametrize("done", [None, 2, -1])
def test_done_out_of_range_is_rejected(conn: sqlite3.Connection, done: int | None) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT, (done,))
