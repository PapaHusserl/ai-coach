import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

OLD_KINDS = ["training", "practice", "rest", "sleep", "checkin", "task"]
INSERT = (
    "INSERT INTO coach_events (id, kind, title, date, start_at, end_at, status, calendar_uid, "
    "created_at) VALUES (?, ?, 'т', '2026-11-02', '2026-11-02T10:00:00', '2026-11-02T11:00:00', "
    "?, ?, '2026-11-01T09:00:00')"
)


def test_schema_version_is_at_least_23(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 23


@pytest.mark.parametrize("kind", ["focus", "meal"])
def test_new_kinds_are_accepted(conn: sqlite3.Connection, kind: str) -> None:
    conn.execute(INSERT, (1, kind, "draft", None))


def test_unknown_kind_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT, (1, "dinner", "draft", None))


def test_indexes_are_in_place(conn: sqlite3.Connection) -> None:
    found = {r[1] for r in conn.execute("PRAGMA index_list(coach_events)").fetchall()}
    assert found >= {"coach_events_date", "coach_events_status", "coach_events_uid"}


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v22.db")
    for number in range(1, 23):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    for number, kind in enumerate(OLD_KINDS, start=10):
        status = "written" if kind == "task" else "draft"
        uid = "uid-7" if kind == "task" else None
        old.execute(INSERT, (number, kind, status, uid))
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v22.db")
    try:
        assert schema_version(conn) >= 23
        rows = conn.execute(
            "SELECT id, kind, status, calendar_uid FROM coach_events ORDER BY id"
        ).fetchall()
        expected = [
            (
                number,
                kind,
                "written" if kind == "task" else "draft",
                "uid-7" if kind == "task" else None,
            )
            for number, kind in enumerate(OLD_KINDS, start=10)
        ]
        assert [tuple(r) for r in rows] == expected
        conn.execute(INSERT, (99, "meal", "draft", None))
    finally:
        conn.close()
