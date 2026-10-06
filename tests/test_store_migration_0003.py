import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version
from ai_coach.store.goals import (
    add_goal,
    add_goal_event,
    add_phase,
    add_phase_event,
    add_phase_goal,
    get_phase,
    list_goal_events,
    list_goals,
    list_phase_events,
    list_phase_goal_ids,
)


def v2_db(path: Path) -> sqlite3.Connection:
    """База на версии 2: применены только 0001 и 0002."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for number, name in ((1, "0001_init.sql"), (2, "0002_goals_phases.sql")):
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    return conn


def test_schema_version_is_at_least_3(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 3


def test_phase_rejected_status_allowed_in_db(conn: sqlite3.Connection) -> None:
    phase_id = add_phase(conn, {"name": "p", "status": "rejected"})
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "rejected"


def test_phase_garbage_status_rejected_by_db(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_phase(conn, {"name": "p", "status": "мусор"})


@pytest.mark.parametrize("event_type", ["proposed", "updated", "accepted", "rejected"])
def test_phase_event_types_allowed_in_db(conn: sqlite3.Connection, event_type: str) -> None:
    phase_id = add_phase(conn, {"name": "p"})
    add_phase_event(
        conn, {"phase_id": phase_id, "event_type": event_type, "occurred_at": "2026-03-01T10:00:00"}
    )
    assert len(list_phase_events(conn, phase_id)) == 1


def test_phase_event_garbage_type_rejected_by_db(conn: sqlite3.Connection) -> None:
    phase_id = add_phase(conn, {"name": "p"})
    with pytest.raises(sqlite3.IntegrityError):
        add_phase_event(
            conn,
            {"phase_id": phase_id, "event_type": "мусор", "occurred_at": "2026-03-01T10:00:00"},
        )


def test_migration_keeps_v2_data(tmp_path: Path) -> None:
    path = tmp_path / "v2.db"
    old = v2_db(path)
    g1 = add_goal(old, {"title": "a", "target": "t"})
    g2 = add_goal(old, {"title": "b", "status": "done"})
    add_goal_event(
        old,
        {"goal_id": g1, "event_type": "created", "occurred_at": "2026-03-01T10:00:00"},
    )
    accepted = add_phase(old, {"name": "База", "description": "d"})
    proposed = add_phase(old, {"name": "Пик"})
    old.execute(
        "UPDATE phases SET status = 'accepted', accepted_at = '2026-03-26T09:00:00' WHERE id = ?",
        (accepted,),
    )
    add_phase_goal(old, accepted, g1)
    add_phase_goal(old, accepted, g2)
    add_phase_event(
        old,
        {"phase_id": accepted, "event_type": "proposed", "occurred_at": "2026-03-25T10:00:00"},
    )
    add_phase_event(
        old,
        {"phase_id": accepted, "event_type": "accepted", "occurred_at": "2026-03-26T09:00:00"},
    )
    old.commit()
    old.close()

    conn = open_db(path)
    try:
        assert schema_version(conn) >= 3
        assert [(g["id"], g["title"], g["status"]) for g in list_goals(conn)] == [
            (g1, "a", "active"),
            (g2, "b", "done"),
        ]
        assert len(list_goal_events(conn, g1)) == 1
        first = get_phase(conn, accepted)
        assert first is not None
        assert (first["name"], first["description"]) == ("База", "d")
        assert first["status"] == "accepted"
        assert first["accepted_at"] == "2026-03-26T09:00:00"
        second = get_phase(conn, proposed)
        assert second is not None
        assert second["status"] == "proposed"
        assert list_phase_goal_ids(conn, accepted) == [g1, g2]
        assert [e["event_type"] for e in list_phase_events(conn, accepted)] == [
            "proposed",
            "accepted",
        ]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()
