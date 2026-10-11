import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

NOW = "'2026-10-11 20:00:00'"


def test_schema_version_is_at_least_17(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 17


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def practice(name: str = "дыхание 4-7-8", kind: str = "breathing", deleted: str = "NULL") -> str:
    return (
        "INSERT INTO practice (name, kind, created_at, updated_at, deleted_at) VALUES "
        f"('{name}', '{kind}', {NOW}, {NOW}, {deleted})"
    )


def habit(name: str = "вода", unit: str = "NULL", deleted: str = "NULL") -> str:
    return (
        "INSERT INTO habit (name, unit, created_at, updated_at, deleted_at) VALUES "
        f"('{name}', {unit}, {NOW}, {NOW}, {deleted})"
    )


def log(habit_id: int, day: str = "2026-10-11", done: str = "1", amount: str = "NULL") -> str:
    return (
        "INSERT INTO habit_log (date, habit_id, done, amount) VALUES "
        f"('{day}', {habit_id}, {done}, {amount})"
    )


def test_practice_columns(conn: sqlite3.Connection) -> None:
    need = {"id", "name", "kind", "minutes", "trigger", "steps", "deleted_at"}
    assert need <= columns(conn, "practice")


def test_habit_columns(conn: sqlite3.Connection) -> None:
    assert {"id", "name", "unit", "deleted_at"} <= columns(conn, "habit")


def test_habit_log_columns(conn: sqlite3.Connection) -> None:
    assert {"date", "habit_id", "done", "amount"} <= columns(conn, "habit_log")


@pytest.mark.parametrize("kind", ["breathing", "pause", "walk", "sleep"])
def test_practice_kinds_are_accepted(conn: sqlite3.Connection, kind: str) -> None:
    conn.execute(practice(kind=kind))


def test_practice_unknown_kind_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(practice(kind="yoga"))


def test_practice_optional_fields_may_be_null(conn: sqlite3.Connection) -> None:
    conn.execute(practice())
    row = conn.execute('SELECT minutes, "trigger", steps FROM practice').fetchone()
    assert row[:] == (None, None, None)


def test_practice_name_is_unique_among_alive(conn: sqlite3.Connection) -> None:
    conn.execute(practice("прогулка", "walk"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(practice("прогулка", "walk"))


def test_practice_name_can_repeat_after_delete(conn: sqlite3.Connection) -> None:
    conn.execute(practice("прогулка", "walk", deleted=NOW))
    conn.execute(practice("прогулка", "walk"))


def test_habit_name_is_unique_among_alive(conn: sqlite3.Connection) -> None:
    conn.execute(habit("вода"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(habit("вода"))


def test_habit_name_can_repeat_after_delete(conn: sqlite3.Connection) -> None:
    conn.execute(habit("вода", deleted=NOW))
    conn.execute(habit("вода"))


def test_habit_unit_may_be_null(conn: sqlite3.Connection) -> None:
    conn.execute(habit("зарядка"))
    assert conn.execute("SELECT unit FROM habit").fetchone()[0] is None


@pytest.mark.parametrize("done", ["0", "1"])
def test_habit_log_done_values(conn: sqlite3.Connection, done: str) -> None:
    conn.execute(habit())
    conn.execute(log(1, done=done))


@pytest.mark.parametrize("done", ["2", "-1"])
def test_habit_log_bad_done_is_refused(conn: sqlite3.Connection, done: str) -> None:
    conn.execute(habit())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(log(1, done=done))


def test_habit_log_amount_may_be_null_or_number(conn: sqlite3.Connection) -> None:
    conn.execute(habit())
    conn.execute(log(1, "2026-10-10"))
    conn.execute(log(1, "2026-10-11", amount="2.5"))
    rows = conn.execute("SELECT amount FROM habit_log ORDER BY date").fetchall()
    assert [r[0] for r in rows] == [None, 2.5]


def test_habit_log_one_row_per_day_and_habit(conn: sqlite3.Connection) -> None:
    conn.execute(habit())
    conn.execute(log(1))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(log(1))


def test_habit_log_same_day_for_other_habit_is_fine(conn: sqlite3.Connection) -> None:
    conn.execute(habit("вода"))
    conn.execute(habit("зарядка"))
    conn.execute(log(1))
    conn.execute(log(2))


def test_habit_log_needs_existing_habit(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(log(99))


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v16.db")
    for number in range(1, 17):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO wellbeing_log (id, date, logged_at, score, text, mood, stress)"
        " VALUES (7, '2026-10-01', '2026-10-01 08:00:00', 4, 'бодро', 3, 2)"
    )
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v16.db")
    try:
        assert schema_version(conn) >= 17
        row = conn.execute("SELECT id, score, text, mood, stress FROM wellbeing_log").fetchone()
        assert row[:] == (7, 4, "бодро", 3, 2)
        assert conn.execute("SELECT COUNT(*) FROM habit").fetchone()[0] == 0
    finally:
        conn.close()
