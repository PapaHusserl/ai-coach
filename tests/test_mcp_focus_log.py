import json
import sqlite3
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, rows, tool_names

DAY = "2026-10-07"
ROOT = Path(__file__).resolve().parent.parent / ".claude"


def focus(conn: sqlite3.Connection, day: str, at: str, text: str | None = None) -> None:
    conn.execute(
        "INSERT INTO focus_log (date, logged_at, focus, fatigue, effort, text) "
        "VALUES (?, ?, 4, 2, 3, ?)",
        (day, at, text),
    )


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_focus_log" in tool_names(conn)


def test_empty_period(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_focus_log", start=DAY, end=DAY) == {"rows": [], "truncated": False}


def test_returns_entries_of_period_inclusive_in_time_order(conn: sqlite3.Connection) -> None:
    focus(conn, "2026-10-05", "2026-10-05 12:00:00")
    focus(conn, DAY, "2026-10-07 15:00:00", "после обеда")
    focus(conn, "2026-10-06", "2026-10-06 11:00:00")
    focus(conn, "2026-10-08", "2026-10-08 12:00:00")
    found = rows(conn, "get_focus_log", start="2026-10-06", end=DAY)
    assert [(r["date"], r["text"]) for r in found] == [("2026-10-06", None), (DAY, "после обеда")]
    assert (found[0]["focus"], found[0]["fatigue"], found[0]["effort"]) == (4, 2, 3)


def test_rows_limited_newest_kept(conn: sqlite3.Connection) -> None:
    for number in range(70):
        focus(conn, DAY, f"{DAY} 08:{number // 60:02d}:{number % 60:02d}", str(number))
    answer = call(conn, "get_focus_log", start=DAY, end=DAY)
    assert len(answer["rows"]) == 60
    assert answer["truncated"] is True
    assert answer["rows"][-1]["text"] == "69"
    assert answer["rows"][0]["text"] == "10"


def test_period_over_92_days_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_focus_log", start="2026-01-01", end="2026-06-01")


def test_snapshot_has_no_focus_keys(conn: sqlite3.Connection) -> None:
    focus(conn, DAY, f"{DAY} 12:00:00")
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert not [key for key in snapshot if "focus" in key]


def test_settings_allow_coach_focus() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert "Bash(uv run coach focus:*)" in allow


def test_coach_md_mentions_focus_and_fits_limit() -> None:
    path = ROOT / "agents" / "coach.md"
    assert "focus" in path.read_text()
    assert len(path.read_bytes()) <= 15360
