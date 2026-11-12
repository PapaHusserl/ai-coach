"""Шаг Н29, партия 2: миграция 0032, таблица decision_log (схема, перенос открытого)."""

import sqlite3
from datetime import date, timedelta
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

INSERT = "INSERT INTO decision_log (text, kind, ref_id, created_at, status) VALUES (?, ?, ?, ?, ?)"
STAMP = "2026-11-12 09:00:00"
WORKOUT_JSON = '{"name": "x", "steps": []}'


def add(
    conn: sqlite3.Connection,
    text: str = "решить",
    kind: str = "text",
    ref_id: int | None = None,
    status: str = "open",
) -> None:
    conn.execute(INSERT, (text, kind, ref_id, STAMP, status))


def test_schema_version_is_at_least_32(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 32


def test_decision_log_has_columns(conn: sqlite3.Connection) -> None:
    names = {row["name"] for row in conn.execute("PRAGMA table_info(decision_log)")}
    expected = {"id", "text", "kind", "ref_id", "target_date", "created_at", "status"}
    assert names >= expected | {"decided_at", "result", "result_at"}


def test_new_row_is_open_text_by_default(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO decision_log (text, created_at) VALUES ('x', ?)", (STAMP,))
    row = conn.execute("SELECT kind, status, ref_id, result FROM decision_log").fetchone()
    assert tuple(row) == ("text", "open", None, None)


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_is_rejected(conn: sqlite3.Connection, text: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, text)


def test_status_outside_list_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, status="maybe")


def test_kind_outside_list_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, kind="goal", ref_id=1)


@pytest.mark.parametrize("status", ["open", "no", "dropped"])
def test_result_without_yes_is_rejected(conn: sqlite3.Connection, status: str) -> None:
    add(conn, status=status)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE decision_log SET result = 'kept'")


def test_result_with_yes_is_accepted(conn: sqlite3.Connection) -> None:
    add(conn, status="yes")
    conn.execute("UPDATE decision_log SET result = 'missed'")
    assert conn.execute("SELECT result FROM decision_log").fetchone()[0] == "missed"


def test_result_outside_list_is_rejected(conn: sqlite3.Connection) -> None:
    add(conn, status="yes")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE decision_log SET result = 'later'")


def test_text_kind_with_ref_id_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, kind="text", ref_id=1)


@pytest.mark.parametrize("kind", ["workout", "phase"])
def test_object_kind_without_ref_id_is_rejected(conn: sqlite3.Connection, kind: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, kind=kind, ref_id=None)


def test_second_item_for_same_object_is_rejected(conn: sqlite3.Connection) -> None:
    add(conn, kind="workout", ref_id=5)
    with pytest.raises(sqlite3.IntegrityError):
        add(conn, kind="workout", ref_id=5)


def test_same_ref_id_in_other_kind_is_accepted(conn: sqlite3.Connection) -> None:
    add(conn, kind="workout", ref_id=5)
    add(conn, kind="phase", ref_id=5)
    assert conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == 2


def test_two_text_items_without_ref_id_are_accepted(conn: sqlite3.Connection) -> None:
    add(conn, "первое")
    add(conn, "второе")
    assert conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == 2


def migrate_from_31(tmp_path: Path) -> sqlite3.Connection:
    """База версии 31 с данными: два черновика, тренировка approved, две фазы, слова в slip_log."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v31.db")
    for number in range(1, 32):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    sql = (
        "INSERT INTO planned_workouts (id, date, sport, name, status, workout_json, created_at) "
        "VALUES (?, ?, 'run', ?, ?, ?, ?)"
    )
    old.execute(sql, (1, tomorrow, "Завтра", "draft", WORKOUT_JSON, "2026-11-10 08:00:00"))
    old.execute(sql, (2, yesterday, "Вчера", "draft", WORKOUT_JSON, "2026-11-09 08:00:00"))
    old.execute(sql, (3, tomorrow, "Утверждена", "approved", WORKOUT_JSON, "2026-11-08 08:00:00"))
    phase = "INSERT INTO phases (id, name, start_date, status, created_at) VALUES (?, ?, ?, ?, ?)"
    old.execute(phase, (1, "База", "2026-11-16", "proposed", "2026-11-11 10:00:00"))
    old.execute(phase, (2, "Принятая", "2026-11-01", "accepted", "2026-10-30 10:00:00"))
    old.commit()
    old.close()
    return open_db(tmp_path / "v31.db")


def test_migration_moves_only_open_objects(tmp_path: Path) -> None:
    conn = migrate_from_31(tmp_path)
    try:
        assert schema_version(conn) >= 32
        rows = conn.execute(
            "SELECT kind, ref_id, status FROM decision_log ORDER BY kind, ref_id"
        ).fetchall()
        assert [tuple(r) for r in rows] == [("phase", 1, "open"), ("workout", 1, "open")]
    finally:
        conn.close()


def test_migration_takes_created_at_and_text_from_objects(tmp_path: Path) -> None:
    conn = migrate_from_31(tmp_path)
    try:
        rows = conn.execute(
            "SELECT kind, text, created_at FROM decision_log ORDER BY kind"
        ).fetchall()
        assert [tuple(r) for r in rows] == [
            ("phase", "База", "2026-11-11 10:00:00"),
            ("workout", "Завтра", "2026-11-10 08:00:00"),
        ]
    finally:
        conn.close()


def test_migration_takes_target_date_from_objects(tmp_path: Path) -> None:
    conn = migrate_from_31(tmp_path)
    try:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        rows = conn.execute("SELECT kind, target_date FROM decision_log ORDER BY kind").fetchall()
        assert [tuple(r) for r in rows] == [("phase", "2026-11-16"), ("workout", tomorrow)]
    finally:
        conn.close()


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    conn = migrate_from_31(tmp_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM planned_workouts").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM phases").fetchone()[0] == 2
    finally:
        conn.close()
