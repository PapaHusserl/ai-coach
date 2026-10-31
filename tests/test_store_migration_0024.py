import sqlite3

import pytest

from ai_coach.store.db import schema_version

COLUMNS = (
    "date, started_at, duration_s, trials, false_starts, lapses, mean_rt_ms, median_rt_ms, "
    "slow10_ms, speed, rts"
)


def insert(trials: int = 4, lapses: int = 0, false_starts: int = 0) -> str:
    return (
        f"INSERT INTO pvt_log ({COLUMNS}) VALUES ('2026-10-31', '2026-10-31 09:30:00', 180, "
        f"{trials}, {false_starts}, {lapses}, 300, 290, 400, 3.3, '[250, 300]')"
    )


def test_schema_version_is_at_least_24(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 24


def test_pvt_log_has_expected_columns(conn: sqlite3.Connection) -> None:
    found = {r[1] for r in conn.execute("PRAGMA table_info(pvt_log)").fetchall()}
    assert found == {"id", *(c.strip() for c in COLUMNS.split(","))}


@pytest.mark.parametrize("column", ["trials", "lapses", "false_starts"])
def test_negative_counts_are_rejected(conn: sqlite3.Connection, column: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert(**{column: -1}))


def test_zero_counts_are_accepted(conn: sqlite3.Connection) -> None:
    conn.execute(insert(trials=0, lapses=0, false_starts=0))
    assert conn.execute("SELECT COUNT(*) FROM pvt_log").fetchone()[0] == 1


def test_metrics_may_be_null_for_false_starts_only(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"INSERT INTO pvt_log ({COLUMNS}) VALUES ('2026-10-31', '2026-10-31 09:30:00', 180, "
        "2, 2, 0, NULL, NULL, NULL, NULL, '[null, null]')"
    )
    row = conn.execute("SELECT mean_rt_ms, median_rt_ms, slow10_ms, speed FROM pvt_log").fetchone()
    assert tuple(row) == (None, None, None, None)


def test_pvt_log_has_date_index(conn: sqlite3.Connection) -> None:
    indexes = {r[1] for r in conn.execute("PRAGMA index_list(pvt_log)").fetchall()}
    assert "pvt_log_date" in indexes
