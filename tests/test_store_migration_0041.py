"""Шаг Н34, партия 1: миграция 0041, таблица system_report."""

import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

REPORT_COLUMNS = {"id", "text", "created_at", "status", "closed_at", "backlog"}


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate_from_40(tmp_path: Path) -> sqlite3.Connection:
    """База версии 40 со строкой kp_index."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v40.db")
    for number in range(1, 41):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO kp_index (time, kp, kind, fetched_at) "
        "VALUES ('2026-11-22T15:00:00', 2.0, 'observed', '2026-11-22T14:10:00')"
    )
    old.commit()
    old.close()
    return open_db(tmp_path / "v40.db")


def insert_report(conn: sqlite3.Connection, **values: object) -> None:
    row: dict[str, object] = {"text": "случай", "created_at": "2026-11-24 12:00:00"}
    row.update(values)
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO system_report ({names}) VALUES ({marks})", list(row.values()))


def test_schema_version_is_at_least_41(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 41


def test_old_base_gets_system_report_with_exact_columns(tmp_path: Path) -> None:
    conn = migrate_from_40(tmp_path)
    try:
        assert schema_version(conn) >= 41
        assert columns(conn, "system_report") == REPORT_COLUMNS
    finally:
        conn.close()


def test_old_tables_survive(tmp_path: Path) -> None:
    conn = migrate_from_40(tmp_path)
    try:
        [hour] = conn.execute("SELECT kp FROM kp_index").fetchall()
        assert hour["kp"] == 2.0
        assert columns(conn, "decision_log")
    finally:
        conn.close()


def test_status_index_exists_on_status_column(conn: sqlite3.Connection) -> None:
    [index] = conn.execute(
        "SELECT name, tbl_name FROM sqlite_master WHERE type = 'index' AND name = ?",
        ("system_report_status",),
    ).fetchall()
    assert index["tbl_name"] == "system_report"
    assert [r["name"] for r in conn.execute("PRAGMA index_info(system_report_status)")] == [
        "status"
    ]


def test_old_base_gets_status_index(tmp_path: Path) -> None:
    conn = migrate_from_40(tmp_path)
    try:
        names = {r["name"] for r in conn.execute("PRAGMA index_list(system_report)")}
        assert "system_report_status" in names
    finally:
        conn.close()


def test_new_report_defaults_to_open(conn: sqlite3.Connection) -> None:
    insert_report(conn)
    row = conn.execute("SELECT status, closed_at, backlog FROM system_report").fetchone()
    assert (row["status"], row["closed_at"], row["backlog"]) == ("open", None, None)


@pytest.mark.parametrize("status", ["open", "done", "dropped"])
def test_allowed_statuses(conn: sqlite3.Connection, status: str) -> None:
    insert_report(conn, status=status)
    assert conn.execute("SELECT COUNT(*) FROM system_report").fetchone()[0] == 1


def test_unknown_status_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_report(conn, status="closed")


def test_empty_text_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_report(conn, text="")
