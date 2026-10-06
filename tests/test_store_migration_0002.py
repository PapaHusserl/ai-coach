import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import migrate, open_db, schema_version
from ai_coach.store.goals import add_goal, add_goal_event, list_goal_events, list_goals
from ai_coach.store.journal import add_sync_log, last_sync_log


def old_db(path: Path) -> sqlite3.Connection:
    """База на версии 1: применена только 0001_init.sql."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    sql = folder.joinpath("0001_init.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = 1;\nCOMMIT;")
    return conn


def test_schema_version_is_at_least_2(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 2


def test_goal_garbage_status_rejected_by_db(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_goal(conn, {"title": "g", "status": "мусор"})


@pytest.mark.parametrize("status", ["active", "done", "cancelled"])
def test_goal_allowed_status_in_db(conn: sqlite3.Connection, status: str) -> None:
    goal_id = add_goal(conn, {"title": "g", "status": status})
    assert goal_id


def test_goal_update_to_garbage_status_rejected_by_db(conn: sqlite3.Connection) -> None:
    from ai_coach.store.goals import update_goal

    goal_id = add_goal(conn, {"title": "g"})
    with pytest.raises(sqlite3.IntegrityError):
        update_goal(conn, goal_id, {"status": "мусор"})


def test_sync_log_garbage_status_rejected_by_db(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_sync_log(conn, {"started_at": "2026-03-01T10:00:00", "kind": "sync", "status": "?"})


@pytest.mark.parametrize("status", ["ok", "error"])
def test_sync_log_allowed_status_in_db(conn: sqlite3.Connection, status: str) -> None:
    add_sync_log(conn, {"started_at": "2026-03-01T10:00:00", "kind": "sync", "status": status})
    last = last_sync_log(conn)
    assert last is not None
    assert last["status"] == status


def test_migration_keeps_goals_and_events(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    old = old_db(path)
    goal_id = add_goal(old, {"title": "Марафон", "target": "3:30", "status": "active"})
    add_goal_event(
        old,
        {
            "goal_id": goal_id,
            "event_type": "created",
            "occurred_at": "2026-03-01T10:00:00",
            "payload_json": {"title": "Марафон"},
        },
    )
    add_sync_log(old, {"started_at": "2026-03-01T10:00:00", "kind": "sync", "status": "ok"})
    old.commit()
    old.close()

    conn = open_db(path)
    try:
        assert schema_version(conn) >= 2
        goals = list_goals(conn)
        assert [(g["id"], g["title"], g["target"]) for g in goals] == [(goal_id, "Марафон", "3:30")]
        assert len(list_goal_events(conn, goal_id)) == 1
        last = last_sync_log(conn)
        assert last is not None
        assert last["status"] == "ok"
    finally:
        conn.close()


def test_migration_twice_is_noop(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    old = old_db(path)
    migrate(old)
    version = schema_version(old)
    goal_id = add_goal(old, {"title": "g"})
    old.commit()
    migrate(old)
    assert schema_version(old) == version
    assert [g["id"] for g in list_goals(old)] == [goal_id]
    old.close()
