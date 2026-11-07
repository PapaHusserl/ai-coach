import json
import sqlite3
from datetime import UTC, datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, rows, tool_names
from workload_fakes import stored_event

from ai_coach.store.garmin_data import upsert_daily_metrics
from ai_coach.store.workload import replace_calendar_window

DAY = "2026-10-07"


def slip(conn: sqlite3.Connection, day: str, at: str, text: str = "бесит") -> None:
    conn.execute(
        "INSERT INTO slip_log (date, logged_at, text) VALUES (?, ?, ?)",
        (day, at, text),
    )


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_slip_log" in tool_names(conn)


@pytest.mark.parametrize("name", ["get_slip_log", "get_focus_log", "get_wellbeing"])
def test_description_mentions_event_id(name: str) -> None:
    from ai_coach.mcp_server.server import TOOLS

    assert "event_id" in TOOLS[name][1]


def test_empty_period(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_slip_log", start=DAY, end=DAY) == {"rows": [], "truncated": False}


def test_returns_entries_of_period_inclusive_in_time_order(conn: sqlite3.Connection) -> None:
    slip(conn, "2026-10-05", "2026-10-05 12:00:00", "рано")
    slip(conn, DAY, "2026-10-07 15:00:00", "после обеда")
    slip(conn, "2026-10-06", "2026-10-06 11:00:00", "вчера")
    slip(conn, "2026-10-08", "2026-10-08 12:00:00", "поздно")
    found = rows(conn, "get_slip_log", start="2026-10-06", end=DAY)
    assert [(r["date"], r["text"]) for r in found] == [
        ("2026-10-06", "вчера"),
        (DAY, "после обеда"),
    ]


def test_rows_limited_newest_kept(conn: sqlite3.Connection) -> None:
    for number in range(70):
        slip(conn, DAY, f"{DAY} 08:{number // 60:02d}:{number % 60:02d}", str(number))
    answer = call(conn, "get_slip_log", start=DAY, end=DAY)
    assert len(answer["rows"]) == 60
    assert answer["truncated"] is True
    assert answer["rows"][-1]["text"] == "69"
    assert answer["rows"][0]["text"] == "10"


def wake_at(conn: sqlite3.Connection, day: str, moment: str) -> None:
    millis = int(datetime.fromisoformat(moment).replace(tzinfo=UTC).timestamp() * 1000)
    upsert_daily_metrics(
        conn,
        {"date": day, "raw_json": {"sleep": {"dailySleepDTO": {"sleepEndTimestampLocal": millis}}}},
    )


def test_awake_hours_from_wake_of_the_day(conn: sqlite3.Connection) -> None:
    wake_at(conn, DAY, f"{DAY} 07:10:00")
    slip(conn, DAY, f"{DAY} 11:00:00")
    assert rows(conn, "get_slip_log", start=DAY, end=DAY)[0]["awake_h"] == 3.8


def test_awake_hours_none_without_daily_metrics(conn: sqlite3.Connection) -> None:
    slip(conn, DAY, f"{DAY} 11:00:00")
    assert rows(conn, "get_slip_log", start=DAY, end=DAY)[0]["awake_h"] is None


def test_period_over_92_days_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_slip_log", start="2026-01-01", end="2026-06-01")


def test_snapshot_has_no_slip_keys(conn: sqlite3.Connection) -> None:
    slip(conn, DAY, f"{DAY} 12:00:00")
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert not [key for key in snapshot if "slip" in key]


def stress_points(conn: sqlite3.Connection, day: str, points: list[tuple[str, int]]) -> None:
    array = [[int(datetime.fromisoformat(at).timestamp() * 1000), lvl] for at, lvl in points]
    upsert_daily_metrics(conn, {"date": day, "raw_json": {"stress": {"stressValuesArray": array}}})


def test_stress_garmin_is_average_around_the_slip(conn: sqlite3.Connection) -> None:
    stress_points(
        conn,
        DAY,
        [(f"{DAY} 13:55:00", 20), (f"{DAY} 14:00:00", 40), (f"{DAY} 14:05:00", 60)]
        + [(f"{DAY} 16:00:00", 95)],
    )
    slip(conn, DAY, f"{DAY} 14:00:00")
    assert rows(conn, "get_slip_log", start=DAY, end=DAY)[0]["stress_garmin"] == 40


def test_stress_garmin_null_without_daily_metrics(conn: sqlite3.Connection) -> None:
    slip(conn, DAY, f"{DAY} 14:00:00")
    found = rows(conn, "get_slip_log", start=DAY, end=DAY)[0]
    assert "stress_garmin" in found
    assert found["stress_garmin"] is None


def test_stress_garmin_null_when_no_points_near(conn: sqlite3.Connection) -> None:
    stress_points(conn, DAY, [(f"{DAY} 09:00:00", 50), (f"{DAY} 14:05:00", -1)])
    slip(conn, DAY, f"{DAY} 14:00:00")
    assert rows(conn, "get_slip_log", start=DAY, end=DAY)[0]["stress_garmin"] is None


def test_stress_garmin_uses_next_day_points_after_midnight(conn: sqlite3.Connection) -> None:
    stress_points(conn, DAY, [(f"{DAY} 23:55:00", 20)])
    stress_points(conn, "2026-10-08", [("2026-10-08 00:05:00", 40)])
    slip(conn, DAY, f"{DAY} 23:58:00")
    assert rows(conn, "get_slip_log", start=DAY, end=DAY)[0]["stress_garmin"] == 30


def test_stress_garmin_after_midnight_slip_takes_next_row_points(conn: sqlite3.Connection) -> None:
    stress_points(conn, "2026-10-08", [("2026-10-08 00:25:00", 20), ("2026-10-08 00:35:00", 60)])
    slip(conn, DAY, "2026-10-08 00:30:00")
    assert rows(conn, "get_slip_log", start=DAY, end=DAY)[0]["stress_garmin"] == 40


def test_stress_garmin_per_row(conn: sqlite3.Connection) -> None:
    stress_points(conn, DAY, [(f"{DAY} 10:00:00", 30), (f"{DAY} 15:00:00", 70)])
    slip(conn, DAY, f"{DAY} 10:02:00")
    slip(conn, DAY, f"{DAY} 15:02:00")
    slip(conn, DAY, f"{DAY} 20:00:00")
    found = rows(conn, "get_slip_log", start=DAY, end=DAY)
    assert [r["stress_garmin"] for r in found] == [30, 70, None]


def test_snapshot_has_no_stress_garmin(conn: sqlite3.Connection) -> None:
    stress_points(conn, DAY, [(f"{DAY} 12:00:00", 50)])
    slip(conn, DAY, f"{DAY} 12:00:00")
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert "stress_garmin" not in json.dumps(snapshot)


def seed_day(conn: sqlite3.Connection, day: str) -> None:
    """Самочувствие (в т.ч. вечернее, отклонение) и тяжёлая рабочая нагрузка."""
    for at, mood, stress in (("08:00:00", 4, 2), ("21:00:00", 2, 5)):
        conn.execute(
            "INSERT INTO wellbeing_log (date, logged_at, score, mood, stress) "
            "VALUES (?, ?, 3, ?, ?)",
            (day, f"{day} {at}", mood, stress),
        )
    event = stored_event(
        uid=f"w-{day}", start_at=f"{day}T08:00:00", end_at=f"{day}T22:00:00", calendar="Work"
    )
    replace_calendar_window(conn, day, day, [event])


def test_slips_do_not_change_other_reports(conn: sqlite3.Connection) -> None:
    seed_day(conn, DAY)
    seed_day(conn, "2026-10-06")

    def state() -> list[object]:
        return [
            call(conn, "get_deviations", date=DAY),
            call(conn, "get_overload", date=DAY),
            call(conn, "get_weekly_review", weeks=4),
            call(conn, "get_morning_snapshot", date=DAY)["evening_done_today"],
        ]

    before = state()
    slip(conn, DAY, f"{DAY} 12:00:00")
    slip(conn, DAY, f"{DAY} 21:00:00", "вечером")
    assert state() == before
