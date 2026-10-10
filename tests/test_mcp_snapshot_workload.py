import sqlite3

from mcp_fakes import call, call_text
from workload_fakes import stored_event

from ai_coach.store.workload import replace_calendar_window

DAY = "2026-10-07"
TITLE = "Секретное название встречи"


def event(day: str, **fields: object) -> dict[str, object]:
    return stored_event(
        uid=f"u-{day}",
        start_at=f"{day}T10:00:00",
        end_at=f"{day}T12:00:00",
        title=TITLE,
        raw_json={"secret": "SECRET_RAW_PAYLOAD"},
        **fields,
    )


def test_snapshot_has_workload_sections(conn: sqlite3.Connection) -> None:
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert {"workload", "workload_ahead"} <= set(snapshot)
    assert set(snapshot["workload"]) == {"rows", "truncated"}
    assert set(snapshot["workload_ahead"]) == {"rows", "truncated"}


def test_snapshot_workload_covers_seven_days_back(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, "2026-09-01", "2026-10-31", [event("2026-10-02")])
    days = [r["date"] for r in call(conn, "get_morning_snapshot", date=DAY)["workload"]["rows"]]
    assert "2026-10-02" in days
    assert all("2026-09-30" <= d <= DAY for d in days)


def test_snapshot_workload_ahead_covers_seven_days_forward(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, "2026-09-01", "2026-10-31", [event("2026-10-10")])
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    days = [r["date"] for r in ahead]
    assert "2026-10-10" in days
    assert all(DAY < d <= "2026-10-14" for d in days)


def test_snapshot_workload_ahead_has_hours(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, "2026-09-01", "2026-10-31", [event("2026-10-10")])
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    assert [r["work_hours"] for r in ahead if r["date"] == "2026-10-10"] == [2.0]


def test_snapshot_has_no_event_titles_or_raw_json(conn: sqlite3.Connection) -> None:
    replace_calendar_window(
        conn, "2026-09-01", "2026-10-31", [event("2026-10-05"), event("2026-10-10")]
    )
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert TITLE not in text
    assert "SECRET_RAW_PAYLOAD" not in text
