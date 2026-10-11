import sqlite3

import pytest

from ai_coach.store.db import schema_version

BASE = {
    "kind": "task",
    "title": "Синтетика",
    "date": "2026-10-10",
    "start_at": "2026-10-10T10:00:00",
    "end_at": "2026-10-10T11:00:00",
    "created_at": "2026-10-09T09:00:00",
}


def put(conn: sqlite3.Connection, **fields: object) -> None:
    values = BASE | fields
    cols = ", ".join(f'"{k}"' for k in values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO coach_events ({cols}) VALUES ({marks})", tuple(values.values()))


def indexed_columns(conn: sqlite3.Connection) -> set[str]:
    found: set[str] = set()
    for index in conn.execute("PRAGMA index_list(coach_events)").fetchall():
        for col in conn.execute(f"PRAGMA index_info({index[1]})").fetchall():
            found.add(col[2])
    return found


def test_schema_version_is_at_least_19(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 19


def test_columns(conn: sqlite3.Connection) -> None:
    names = {r[1] for r in conn.execute("PRAGMA table_info(coach_events)").fetchall()}
    assert {
        "id", "kind", "title", "date", "start_at", "end_at", "all_day", "note", "category",
        "alarm_min", "repeat", "workout_id", "practice_id", "status", "calendar_uid",
        "created_at", "written_at", "removed_at", "removed_by",
    } <= names  # fmt: skip


def test_defaults_are_draft_and_not_all_day(conn: sqlite3.Connection) -> None:
    put(conn)
    row = conn.execute("SELECT status, all_day, category FROM coach_events").fetchone()
    assert (row[0], row[1], row[2]) == ("draft", 0, None)


@pytest.mark.parametrize("kind", ["training", "practice", "rest", "sleep", "checkin", "task"])
def test_known_kinds_are_accepted(conn: sqlite3.Connection, kind: str) -> None:
    put(conn, kind=kind)


def test_unknown_kind_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        put(conn, kind="meeting")


@pytest.mark.parametrize("status", ["draft", "written", "cancelled", "removed"])
def test_known_statuses_are_accepted(conn: sqlite3.Connection, status: str) -> None:
    put(conn, status=status)


def test_unknown_status_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        put(conn, status="sent")


@pytest.mark.parametrize("category", ["work", "personal", "hobby", "rest"])
def test_known_categories_are_accepted(conn: sqlite3.Connection, category: str) -> None:
    put(conn, category=category)


def test_unknown_category_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        put(conn, category="coach")


def test_repeat_daily_is_accepted_for_checkin(conn: sqlite3.Connection) -> None:
    put(conn, kind="checkin", repeat="daily")


def test_repeat_weekly_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        put(conn, kind="checkin", repeat="weekly")


def test_repeat_is_rejected_for_other_kinds(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        put(conn, kind="task", repeat="daily")


def test_removed_by_accepts_cli_and_calendar(conn: sqlite3.Connection) -> None:
    put(conn, status="removed", removed_by="cli")
    put(conn, status="removed", removed_by="calendar")


def test_removed_by_rejects_other_values(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        put(conn, status="removed", removed_by="mcp")


@pytest.mark.parametrize("column", ["kind", "title", "date", "start_at", "end_at"])
def test_required_columns(conn: sqlite3.Connection, column: str) -> None:
    values = {k: v for k, v in BASE.items() if k != column}
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(f"INSERT INTO coach_events ({cols}) VALUES ({marks})", tuple(values.values()))


def test_indexes_cover_date_and_calendar_uid(conn: sqlite3.Connection) -> None:
    assert {"date", "calendar_uid"} <= indexed_columns(conn)
