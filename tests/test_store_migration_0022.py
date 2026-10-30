import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

NEW = {"work_thoughts", "hindrance", "valuable", "flow"}


def insert(**fields: int) -> str:
    values = {"date": "'2026-10-31'", "logged_at": "'2026-10-31 20:00:00'", "score": 3} | fields
    return (
        f"INSERT INTO wellbeing_log ({', '.join(values)}) "
        f"VALUES ({', '.join(str(v) for v in values.values())})"
    )


def test_schema_version_is_at_least_22(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 22


def test_wellbeing_log_has_four_new_columns(conn: sqlite3.Connection) -> None:
    found = {r[1] for r in conn.execute("PRAGMA table_info(wellbeing_log)").fetchall()}
    assert found >= NEW


def test_new_columns_may_be_null(conn: sqlite3.Connection) -> None:
    conn.execute(insert())
    row = conn.execute("SELECT work_thoughts, hindrance, valuable, flow FROM wellbeing_log")
    assert row.fetchone()[:] == (None, None, None, None)


@pytest.mark.parametrize("column", ["work_thoughts", "hindrance", "valuable"])
@pytest.mark.parametrize("value", [1, 5])
def test_score_limits_are_inclusive(conn: sqlite3.Connection, column: str, value: int) -> None:
    conn.execute(insert(**{column: value}))


@pytest.mark.parametrize("column", ["work_thoughts", "hindrance", "valuable"])
@pytest.mark.parametrize("value", [0, 6, -1])
def test_bad_score_is_refused(conn: sqlite3.Connection, column: str, value: int) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert(**{column: value}))


@pytest.mark.parametrize("value", [0, 1])
def test_flow_accepts_zero_and_one(conn: sqlite3.Connection, value: int) -> None:
    conn.execute(insert(flow=value))


@pytest.mark.parametrize("value", [2, -1])
def test_flow_two_is_refused(conn: sqlite3.Connection, value: int) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert(flow=value))


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v21.db")
    for number in range(1, 22):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO wellbeing_log (id, date, logged_at, score, text, mood, stress)"
        " VALUES (7, '2026-10-01', '2026-10-01 20:00:00', 4, 'бодро', 3, 2)"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v21.db")
    try:
        assert schema_version(conn) >= 22
        row = conn.execute(
            "SELECT id, score, text, mood, stress, work_thoughts, hindrance, valuable, flow "
            "FROM wellbeing_log"
        ).fetchone()
        assert row[:] == (7, 4, "бодро", 3, 2, None, None, None, None)
    finally:
        conn.close()
