import sqlite3

import pytest

from ai_coach.store.db import schema_version

INSERT = (
    "INSERT INTO calendar_events (source, uid, date, start_at, end_at, all_day, calendar, "
    "category, synced_at{col}) VALUES ('apple_calendar', 'u1', '2026-10-07', "
    "'2026-10-07T10:00:00', '2026-10-07T11:00:00', 0, 'Work', 'work', '2026-10-08T10:00:00'{val})"
)


def test_schema_version_is_at_least_25(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 25


def test_calendar_events_has_demand_column(conn: sqlite3.Connection) -> None:
    found = {r[1] for r in conn.execute("PRAGMA table_info(calendar_events)").fetchall()}
    assert "demand" in found


def test_row_without_demand_is_null(conn: sqlite3.Connection) -> None:
    conn.execute(INSERT.format(col="", val=""))
    assert conn.execute("SELECT demand FROM calendar_events").fetchone()[0] is None


@pytest.mark.parametrize("demand", ["challenge", "hindrance"])
def test_known_demand_is_accepted(conn: sqlite3.Connection, demand: str) -> None:
    conn.execute(INSERT.format(col=", demand", val=f", '{demand}'"))
    assert conn.execute("SELECT demand FROM calendar_events").fetchone()[0] == demand


def test_unknown_demand_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(INSERT.format(col=", demand", val=", 'foo'"))
