import sqlite3
from pathlib import Path

import pytest
from fake_clock import freeze
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, rows, tool_names

from ai_coach.store.journal import add_who5

DAY = "2026-10-07"
ROOT = Path(__file__).resolve().parent.parent / ".claude"


def who5(conn: sqlite3.Connection, day: str, at: str, q1: int = 5, text: str | None = None) -> None:
    add_who5(
        conn,
        {
            "date": day,
            "logged_at": f"{day} {at}",
            "q1": q1,
            "q2": 1,
            "q3": 1,
            "q4": 1,
            "q5": 1,
            "score": (q1 + 4) * 4,
            "text": text,
        },
    )


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_who5" in tool_names(conn)


def test_empty_period(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_who5", start=DAY, end=DAY) == {"rows": [], "truncated": False}


def test_returns_entries_of_period_inclusive_in_time_order(conn: sqlite3.Connection) -> None:
    who5(conn, "2026-10-05", "09:30:00")
    who5(conn, DAY, "09:30:00", 3)
    who5(conn, "2026-10-06", "09:30:00", 4)
    who5(conn, "2026-10-08", "09:30:00")
    found = rows(conn, "get_who5", start="2026-10-06", end=DAY)
    assert [(r["date"], r["q1"]) for r in found] == [("2026-10-06", 4), (DAY, 3)]


def test_row_has_answers_score_text_and_no_raw_json(conn: sqlite3.Connection) -> None:
    who5(conn, DAY, "09:30:00", 3, "устал")
    (row,) = rows(conn, "get_who5", start=DAY, end=DAY)
    assert "raw_json" not in row
    assert [row[f"q{n}"] for n in range(1, 6)] == [3, 1, 1, 1, 1]
    assert (row["score"], row["text"]) == (28, "устал")


def test_rows_limited_newest_kept(conn: sqlite3.Connection) -> None:
    for number in range(70):
        who5(conn, DAY, f"08:{number // 60:02d}:{number % 60:02d}", number % 6)
    answer = call(conn, "get_who5", start=DAY, end=DAY)
    assert len(answer["rows"]) == 60
    assert answer["truncated"] is True
    assert answer["rows"][-1]["logged_at"] == f"{DAY} 08:01:09"
    assert answer["rows"][0]["logged_at"] == f"{DAY} 08:00:10"


def test_period_over_92_days_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_who5", start="2026-01-01", end="2026-06-01")


def test_snapshot_has_who5_report_without_rows(conn: sqlite3.Connection) -> None:
    who5(conn, "2026-10-06", "09:30:00", 3)
    part = call(conn, "get_morning_snapshot", date=DAY)["who5"]
    assert "rows" not in part
    assert set(part) == {
        "last_date",
        "score",
        "prev_date",
        "prev_score",
        "delta",
        "days_since",
        "due",
        "low_until",
        "signals",
    }
    assert (part["score"], part["days_since"], part["due"]) == (28, 1, False)
    assert [s["kind"] for s in part["signals"]] == ["who5_low"]


def test_snapshot_who5_without_entries_is_due(conn: sqlite3.Connection) -> None:
    part = call(conn, "get_morning_snapshot", date=DAY)["who5"]
    assert (part["score"], part["due"], part["signals"]) == (None, True, [])


def test_snapshot_who5_counts_wellbeing_day_after_midnight(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    # замер вечером 1 ноября, сводка в 03:00 2 ноября: «день самочувствия» ещё 1 ноября
    who5(conn, "2026-11-01", "23:50:00")
    freeze(monkeypatch, "2026-11-02 03:00:00")
    part = call(conn, "get_morning_snapshot", date="2026-11-02")["who5"]
    assert (part["days_since"], part["due"]) == (0, False)


def test_coach_md_allows_tool() -> None:
    assert "mcp__ai-coach__get_who5" in (ROOT / "agents" / "coach.md").read_text()
