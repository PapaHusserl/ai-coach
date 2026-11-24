"""get_weekly_review(weeks=4): 1..12, {rows, truncated}; snapshot week_review_due (шаг v2.5)."""

import asyncio
import sqlite3
from datetime import date, timedelta

import pytest
from fake_clock import freeze
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, db_file, rows, tool_names

from ai_coach.mcp_server import build_server
from ai_coach.store.garmin_data import upsert_daily_metrics

# 2026-10-11 - воскресенье, 12 - понедельник, 13 - вторник
SUN, MON, TUE, WED, SAT = "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-10"


def reviewed(conn: sqlite3.Connection, week: str) -> None:
    conn.execute(
        "INSERT INTO review_log (week_start, done_at) VALUES (?, '2026-10-01 20:00:00')", (week,)
    )


def due(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch, now: str) -> object:
    freeze(monkeypatch, now)
    return call(conn, "get_morning_snapshot", date=now[:10])["week_review_due"]


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_weekly_review" in tool_names(conn)


def test_default_is_four_weeks(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    result = call(conn, "get_weekly_review")
    assert set(result) == {"rows", "truncated", "recovery"}
    assert result["truncated"] is False
    assert len(result["rows"]) == 4


def test_recovery_lists_three_factors_in_order(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    found = call(conn, "get_weekly_review")["recovery"]
    assert [f["factor"] for f in found["factors"]] == [
        "evening_work",
        "claude_evening",
        "heavy_day",
    ]
    assert all(f["enough"] is False for f in found["factors"])


def test_recovery_counts_pairs_from_the_database(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    conn.execute(
        "INSERT INTO day_counters (date, kind, value, source, synced_at) "
        "VALUES (?, 'screen_work_evening_hours', 2.0, 'screen', '2026-10-14T10:00:00')",
        (SAT,),
    )
    upsert_daily_metrics(
        conn,
        {
            "date": SUN,
            "hrv_last_night": 41,
            "sleep_seconds": 25200,
            "raw_json": {"sleep": {"restingHeartRate": 52}},
        },
    )
    found = call(conn, "get_weekly_review")["recovery"]["factors"][0]
    assert (found["factor"], found["with"], found["without"]) == ("evening_work", 1, 0)


@pytest.mark.parametrize("weeks", [1, 2, 12])
def test_weeks_in_range(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch, weeks: int
) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    assert len(rows(conn, "get_weekly_review", weeks=weeks)) == weeks


@pytest.mark.parametrize("weeks", [0, -1, 13, 100])
def test_weeks_out_of_range_is_error(conn: sqlite3.Connection, weeks: int) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_weekly_review", weeks=weeks)


def test_rows_oldest_first_and_current_is_partial(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    found = rows(conn, "get_weekly_review", weeks=3)
    assert [r["week_start"] for r in found] == ["2026-09-28", "2026-10-05", "2026-10-12"]
    assert [r["partial"] for r in found] == [False, False, True]


def test_row_has_expected_fields(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    need = {
        "week_start", "week_end", "partial", "tss", "work_hours", "evening_hours",
        "weekend_work_hours", "todo_closed", "todo_open", "mood", "stress", "sleep",
        "readiness", "days_with_data", "delta", "fatigue", "irritability",
    }  # fmt: skip
    assert need <= set(rows(conn, "get_weekly_review")[0])


def test_row_has_rest_fields_and_recovery_stays(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    result = call(conn, "get_weekly_review")
    assert {"rest_hours", "rest_days", "days_off"} <= set(result["rows"][0])
    assert {"rest_hours", "days_off"} <= set(result["rows"][-1]["delta"])
    assert "recovery" in result


def test_tool_description_names_fatigue_and_irritability(conn: sqlite3.Connection) -> None:
    server = build_server(db_file(conn))
    tool = next(t for t in asyncio.run(server.list_tools()) if t.name == "get_weekly_review")
    description = tool.description or ""
    assert "fatigue" in description
    assert "irritability" in description


def test_twelve_weeks_with_marks_every_day_are_not_truncated(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    for offset in range(12 * 7):
        day = (date.fromisoformat(WED) - timedelta(days=offset)).isoformat()
        conn.execute(
            "INSERT INTO wellbeing_log (date, logged_at, score, fatigue, irritability) "
            "VALUES (?, ?, 3, 4, 2)",
            (day, f"{day} 21:00:00"),
        )
    result = call(conn, "get_weekly_review", weeks=12)
    assert result["truncated"] is False
    assert len(result["rows"]) == 12
    assert result["rows"][-1]["fatigue"] == pytest.approx(4)
    assert result["rows"][-1]["irritability"] == pytest.approx(2)


# --- week_review_due ---


def test_evening_hours_of_week_come_from_screen_counter(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{WED} 12:00:00")
    for day in (MON, TUE):
        conn.execute(
            "INSERT INTO day_counters (date, kind, value, source, synced_at) "
            "VALUES (?, 'screen_work_evening_hours', 1.0, 'screen', '2026-10-14T10:00:00')",
            (day,),
        )
    assert rows(conn, "get_weekly_review", weeks=1)[0]["evening_hours"] == pytest.approx(2.0)


def test_due_on_sunday_without_record(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert due(conn, monkeypatch, f"{SUN} 12:00:00") is True


def test_not_due_on_sunday_with_current_week_record(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed(conn, "2026-10-05")
    assert due(conn, monkeypatch, f"{SUN} 12:00:00") is False


def test_sunday_ignores_record_of_previous_week(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed(conn, "2026-09-28")
    assert due(conn, monkeypatch, f"{SUN} 12:00:00") is True


def test_due_on_monday_without_record_of_past_week(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert due(conn, monkeypatch, f"{MON} 12:00:00") is True


def test_not_due_on_monday_with_record_of_past_week(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed(conn, "2026-10-05")
    assert due(conn, monkeypatch, f"{MON} 12:00:00") is False


def test_monday_ignores_record_of_new_week(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed(conn, "2026-10-12")
    assert due(conn, monkeypatch, f"{MON} 12:00:00") is True


@pytest.mark.parametrize("day", ["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", SAT])
def test_not_due_tuesday_to_saturday(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch, day: str
) -> None:
    assert due(conn, monkeypatch, f"{day} 12:00:00") is False


def test_not_due_tuesday_even_with_missing_record_of_past_week(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert due(conn, monkeypatch, f"{TUE} 12:00:00") is False
