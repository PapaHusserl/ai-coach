import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

INSERT = (
    "INSERT INTO coach_events (id, kind, title, date, start_at, end_at, repeat, status, "
    "calendar_uid, created_at) VALUES (?, ?, 'т', '2026-11-02', '2026-11-02T10:00:00', "
    "'2026-11-02T10:15:00', ?, ?, ?, '2026-11-01T09:00:00')"
)


def test_schema_version_is_at_least_28(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 28


@pytest.mark.parametrize("repeat", ["daily", "weekly", "biweekly"])
def test_repeat_is_accepted_for_checkin(conn: sqlite3.Connection, repeat: str) -> None:
    conn.execute(INSERT, (1, "checkin", repeat, "draft", None))


@pytest.mark.parametrize("repeat", ["daily", "weekly", "biweekly"])
def test_repeat_on_other_kind_is_refused(conn: sqlite3.Connection, repeat: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT, (1, "task", repeat, "draft", None))


def test_monthly_repeat_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT, (1, "checkin", "monthly", "draft", None))


def test_event_without_repeat_is_accepted(conn: sqlite3.Connection) -> None:
    conn.execute(INSERT, (1, "task", None, "draft", None))


def test_indexes_are_in_place(conn: sqlite3.Connection) -> None:
    found = {r[1] for r in conn.execute("PRAGMA index_list(coach_events)").fetchall()}
    assert found >= {"coach_events_date", "coach_events_status", "coach_events_uid"}


def test_migration_keeps_old_rows(tmp_path: Path) -> None:
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v27.db")
    for number in range(1, 28):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(INSERT, (10, "checkin", "daily", "written", "uid-10"))
    old.execute(INSERT, (11, "task", None, "draft", None))
    old.execute(INSERT, (12, "checkin", None, "cancelled", None))
    old.commit()
    old.close()

    conn = open_db(tmp_path / "v27.db")
    try:
        assert schema_version(conn) >= 28
        rows = conn.execute(
            "SELECT id, kind, repeat, status, calendar_uid FROM coach_events ORDER BY id"
        ).fetchall()
        assert [tuple(r) for r in rows] == [
            (10, "checkin", "daily", "written", "uid-10"),
            (11, "task", None, "draft", None),
            (12, "checkin", None, "cancelled", None),
        ]
        conn.execute(INSERT, (99, "checkin", "biweekly", "draft", None))
    finally:
        conn.close()
