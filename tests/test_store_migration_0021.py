import sqlite3

import pytest

from ai_coach.store.db import schema_version

NOW = "'2026-10-31 12:00:00'"


def insert(focus: int = 3, fatigue: int = 3, effort: int = 3) -> str:
    return (
        "INSERT INTO focus_log (date, logged_at, focus, fatigue, effort) VALUES "
        f"('2026-10-31', {NOW}, {focus}, {fatigue}, {effort})"
    )


def test_schema_version_is_at_least_21(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 21


def test_focus_log_has_expected_columns(conn: sqlite3.Connection) -> None:
    found = {r[1] for r in conn.execute("PRAGMA table_info(focus_log)").fetchall()}
    assert found == {"id", "date", "logged_at", "focus", "fatigue", "effort", "text"}


@pytest.mark.parametrize("column", ["focus", "fatigue", "effort"])
@pytest.mark.parametrize("value", [0, 6])
def test_score_out_of_range_is_rejected(conn: sqlite3.Connection, column: str, value: int) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert(**{column: value}))


@pytest.mark.parametrize("value", [1, 5])
def test_score_bounds_are_accepted(conn: sqlite3.Connection, value: int) -> None:
    conn.execute(insert(focus=value, fatigue=value, effort=value))
    assert conn.execute("SELECT COUNT(*) FROM focus_log").fetchone()[0] == 1


def test_text_may_be_null(conn: sqlite3.Connection) -> None:
    conn.execute(insert())
    assert conn.execute("SELECT text FROM focus_log").fetchone()[0] is None


def test_focus_log_has_date_index(conn: sqlite3.Connection) -> None:
    indexes = {r[1] for r in conn.execute("PRAGMA index_list(focus_log)").fetchall()}
    assert "focus_log_date" in indexes
