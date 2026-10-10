import sqlite3

import pytest

from ai_coach.store.db import schema_version

NOW = "'2026-10-08 10:00:00'"


def test_schema_version_is_at_least_15(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 15


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def event(**fields: str) -> str:
    base = {
        "source": "'apple_calendar'",
        "uid": "'u1'",
        "date": "'2026-10-08'",
        "start": "'2026-10-08T10:00:00'",
        "category": "'work'",
    }
    base |= fields
    return (
        "INSERT INTO calendar_events (source, uid, date, start_at, end_at, all_day, calendar,"
        " category, title, status, my_status, synced_at, raw_json) VALUES "
        f"({base['source']}, {base['uid']}, {base['date']}, {base['start']},"
        f" '2026-10-08T11:00:00', 0, 'Work', {base['category']}, 'T', 'confirmed', 'accepted',"
        f" {NOW}, '{{}}')"
    )


def counter(**fields: str) -> str:
    base = {"date": "'2026-10-08'", "kind": "'todo_open'", "value": "3"}
    base |= fields
    return (
        "INSERT INTO day_counters (date, kind, value, source, synced_at, raw_json) VALUES "
        f"({base['date']}, {base['kind']}, {base['value']}, 'todo', {NOW}, '{{}}')"
    )


def test_calendar_events_has_expected_columns(conn: sqlite3.Connection) -> None:
    expected = {
        "id", "source", "uid", "date", "start_at", "end_at", "all_day", "calendar",
        "category", "title", "status", "my_status", "synced_at", "raw_json",
    }  # fmt: skip
    assert expected <= columns(conn, "calendar_events")


def test_day_counters_has_expected_columns(conn: sqlite3.Connection) -> None:
    expected = {"date", "kind", "value", "source", "synced_at", "raw_json"}
    assert expected <= columns(conn, "day_counters")


def test_event_source_defaults_to_apple_calendar(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO calendar_events (uid, date, start_at, end_at, all_day, calendar, category,"
        " title, synced_at, raw_json) VALUES ('u1', '2026-10-08', '2026-10-08T10:00:00',"
        f" '2026-10-08T11:00:00', 0, 'Work', 'work', 'T', {NOW}, '{{}}')"
    )
    assert conn.execute("SELECT source FROM calendar_events").fetchone()[0] == "apple_calendar"


@pytest.mark.parametrize("category", ["work", "personal", "hobby", "rest", "unknown"])
def test_event_category_is_allowed(conn: sqlite3.Connection, category: str) -> None:
    conn.execute(event(category=f"'{category}'"))


@pytest.mark.parametrize("category", ["ignore", "other", ""])
def test_event_bad_category_is_refused(conn: sqlite3.Connection, category: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(event(category=f"'{category}'"))


def test_event_same_source_uid_start_is_refused(conn: sqlite3.Connection) -> None:
    conn.execute(event())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(event())


def test_recurring_event_same_uid_other_start_is_allowed(conn: sqlite3.Connection) -> None:
    conn.execute(event())
    conn.execute(event(start="'2026-10-09T10:00:00'", date="'2026-10-09'"))


def test_same_uid_other_source_is_allowed(conn: sqlite3.Connection) -> None:
    conn.execute(event())
    conn.execute(event(source="'other'"))


def test_calendar_events_has_index_on_date(conn: sqlite3.Connection) -> None:
    indexed = []
    for index in conn.execute("PRAGMA index_list(calendar_events)").fetchall():
        indexed.append([r[2] for r in conn.execute(f"PRAGMA index_info({index[1]})").fetchall()])
    assert ["date"] in indexed


def test_counter_same_date_kind_is_refused(conn: sqlite3.Connection) -> None:
    conn.execute(counter())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(counter())


def test_counter_other_kind_same_date_is_allowed(conn: sqlite3.Connection) -> None:
    conn.execute(counter())
    conn.execute(counter(kind="'todo_closed'"))


def test_counter_kind_is_not_limited_by_schema(conn: sqlite3.Connection) -> None:
    """Новый признак = новый kind без миграции: белый список kind - в Python."""
    conn.execute(counter(kind="'brand_new_kind'"))
