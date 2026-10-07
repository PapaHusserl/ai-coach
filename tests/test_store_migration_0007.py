import sqlite3
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version


def add(conn: sqlite3.Connection, key: str, value: str, source: str, at: str) -> None:
    conn.execute(
        "INSERT INTO profile_log (key, value, source, logged_at) VALUES (?, ?, ?, ?)",
        (key, value, source, at),
    )


def test_schema_version_is_at_least_7(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 7


def test_profile_log_has_expected_columns(conn: sqlite3.Connection) -> None:
    columns = {r[1] for r in conn.execute("PRAGMA table_info(profile_log)").fetchall()}
    assert {"id", "key", "value", "source", "logged_at", "raw_json"} <= columns


def test_profile_log_is_empty_on_new_database(conn: sqlite3.Connection) -> None:
    assert conn.execute("SELECT count(*) FROM profile_log").fetchone()[0] == 0


def test_raw_json_is_optional(conn: sqlite3.Connection) -> None:
    add(conn, "sex", "m", "manual", "2026-10-07T10:00:00")
    assert conn.execute("SELECT raw_json FROM profile_log").fetchone()[0] is None


@pytest.mark.parametrize("source", ["manual", "garmin"])
def test_known_sources_are_accepted(conn: sqlite3.Connection, source: str) -> None:
    add(conn, "sex", "m", source, "2026-10-07T10:00:00")


def test_unknown_source_is_rejected_by_database(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, "sex", "m", "web", "2026-10-07T10:00:00")


@pytest.mark.parametrize("column", ["key", "value", "logged_at"])
def test_required_columns_are_not_null(conn: sqlite3.Connection, column: str) -> None:
    values = {"key": "sex", "value": "m", "source": "manual", "logged_at": "x"}
    values[column] = None  # type: ignore[assignment]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO profile_log (key, value, source, logged_at) VALUES (?, ?, ?, ?)",
            tuple(values.values()),
        )


def test_log_only_grows_for_the_same_key(conn: sqlite3.Connection) -> None:
    add(conn, "height_cm", "180", "manual", "2026-10-01T10:00:00")
    add(conn, "height_cm", "181", "manual", "2026-10-02T10:00:00")
    assert conn.execute("SELECT count(*) FROM profile_log").fetchone()[0] == 2


def test_index_on_key_and_logged_at_exists(conn: sqlite3.Connection) -> None:
    for index in conn.execute("PRAGMA index_list(profile_log)").fetchall():
        columns = [r[2] for r in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()]
        if columns == ["key", "logged_at"]:
            return
    pytest.fail("нет индекса (key, logged_at)")


def test_reopening_database_changes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "coach.db"
    first = open_db(path)
    add(first, "sex", "m", "manual", "2026-10-07T10:00:00")
    first.commit()
    version = schema_version(first)
    first.close()
    second = open_db(path)
    try:
        assert schema_version(second) == version
        assert [tuple(r) for r in second.execute("SELECT key, value FROM profile_log")] == [
            ("sex", "m")
        ]
    finally:
        second.close()
