import sqlite3
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, rows, tool_names

DAY = "2026-10-07"
ROOT = Path(__file__).resolve().parent.parent / ".claude"


def pvt(conn: sqlite3.Connection, day: str, at: str, median: int | None = 300) -> None:
    conn.execute(
        "INSERT INTO pvt_log (date, started_at, duration_s, trials, false_starts, lapses, "
        "mean_rt_ms, median_rt_ms, slow10_ms, speed, rts) "
        "VALUES (?, ?, 180, 54, 1, 2, 301, ?, 420, 3.41, '[250, null]')",
        (day, at, median),
    )


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_pvt_log" in tool_names(conn)


def test_empty_period(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_pvt_log", start=DAY, end=DAY) == {"rows": [], "truncated": False}


def test_returns_entries_of_period_inclusive_in_time_order(conn: sqlite3.Connection) -> None:
    pvt(conn, "2026-10-05", "2026-10-05 09:30:00")
    pvt(conn, DAY, "2026-10-07 09:30:00", 280)
    pvt(conn, "2026-10-06", "2026-10-06 09:30:00", 290)
    pvt(conn, "2026-10-08", "2026-10-08 09:30:00")
    found = rows(conn, "get_pvt_log", start="2026-10-06", end=DAY)
    assert [(r["date"], r["median_rt_ms"]) for r in found] == [("2026-10-06", 290), (DAY, 280)]


def test_row_has_metrics_and_no_rts(conn: sqlite3.Connection) -> None:
    pvt(conn, DAY, f"{DAY} 09:30:00")
    (row,) = rows(conn, "get_pvt_log", start=DAY, end=DAY)
    assert "rts" not in row
    assert (row["slow10_ms"], row["speed"], row["mean_rt_ms"]) == (420, 3.41, 301)
    assert (row["lapses"], row["false_starts"], row["trials"]) == (2, 1, 54)


def test_rows_limited_newest_kept(conn: sqlite3.Connection) -> None:
    for number in range(70):
        pvt(conn, DAY, f"{DAY} 08:{number // 60:02d}:{number % 60:02d}", number)
    answer = call(conn, "get_pvt_log", start=DAY, end=DAY)
    assert len(answer["rows"]) == 60
    assert answer["truncated"] is True
    assert answer["rows"][-1]["median_rt_ms"] == 69
    assert answer["rows"][0]["median_rt_ms"] == 10


def test_period_over_92_days_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_pvt_log", start="2026-01-01", end="2026-06-01")


def test_snapshot_has_no_pvt_keys(conn: sqlite3.Connection) -> None:
    pvt(conn, DAY, f"{DAY} 09:30:00")
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert not [key for key in snapshot if "pvt" in key]


def test_coach_md_allows_tool_and_fits_limit() -> None:
    path = ROOT / "agents" / "coach.md"
    assert "mcp__ai-coach__get_pvt_log" in path.read_text()
    assert len(path.read_bytes()) <= 15360
