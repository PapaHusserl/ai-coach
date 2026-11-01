import json
import sqlite3
import urllib.request
from datetime import date
from pathlib import Path

import pytest
from mcp_fakes import call, call_text
from workload_fakes import FakeCalendar, stored_event, write_config

from ai_coach.mcp_server.snapshot import SNAPSHOT_MAX_CHARS
from ai_coach.store.workload import replace_calendar_window, upsert_counter
from ai_coach.sync.workload_sync import sync_workload
from ai_coach.workload.claude import CLAUDE_COUNTERS
from ai_coach.workload.config import load_config
from ai_coach.workload.screen import AwReader

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


def put_screen(conn: sqlite3.Connection, day: str, kind: str, value: float) -> None:
    upsert_counter(
        conn,
        {
            "date": day,
            "kind": kind,
            "value": value,
            "source": "screen",
            "raw_json": None,
            "synced_at": "2026-10-08T10:00:00",
        },
    )


def test_snapshot_workload_has_no_claude_keys(conn: sqlite3.Connection) -> None:
    for kind in CLAUDE_COUNTERS:
        put_screen(conn, "2026-10-05", kind, 3)
    rows = call(conn, "get_morning_snapshot", date=DAY)["workload"]["rows"]
    assert rows
    for row in rows:
        assert [k for k in row if k.startswith("claude_")] == []


def put_claude_week(conn: sqlite3.Connection) -> None:
    for day in range(1, 8):
        for i, kind in enumerate(CLAUDE_COUNTERS):
            upsert_counter(
                conn,
                {
                    "date": f"2026-10-0{day}",
                    "kind": kind,
                    "value": day + i,
                    "source": "claude",
                    "raw_json": {"repos": [{"repo": "alpha-repo", "prompts": 1}]}
                    if kind == "claude_repos"
                    else None,
                    "synced_at": "2026-10-08T10:00:00",
                },
            )


def test_snapshot_claude_has_seven_rows_with_short_keys(conn: sqlite3.Connection) -> None:
    put_claude_week(conn)
    claude = call(conn, "get_morning_snapshot", date=DAY)["claude"]
    assert claude["truncated"] is False
    assert [r["date"] for r in claude["rows"]] == [f"2026-10-0{d}" for d in range(1, 8)]
    for row in claude["rows"]:
        assert set(row) == {"date", "prompts", "evening", "decisions", "repos", "switches"}
    last = claude["rows"][-1]
    assert last["prompts"] == 7
    assert last["evening"] == 8
    assert last["decisions"] == 9
    assert last["repos"] == 10
    assert last["switches"] == 11


def test_snapshot_claude_without_data_has_nulls(conn: sqlite3.Connection) -> None:
    rows = call(conn, "get_morning_snapshot", date=DAY)["claude"]["rows"]
    assert len(rows) == 7
    assert all(r["prompts"] is None for r in rows)


def test_snapshot_claude_has_no_repo_names(conn: sqlite3.Connection) -> None:
    put_claude_week(conn)
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert "alpha-repo" not in text
    assert "claude_repos_names" not in text


def test_snapshot_workload_ahead_has_no_claude_keys(conn: sqlite3.Connection) -> None:
    for day in range(8, 15):
        for kind in CLAUDE_COUNTERS:
            put_screen(conn, f"2026-10-{day:02d}", kind, 3)
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    assert ahead
    for row in ahead:
        assert [k for k in row if k.startswith("claude_")] == []


def test_snapshot_workload_has_seven_rows_not_truncated_on_empty_base(
    conn: sqlite3.Connection,
) -> None:
    workload = call(conn, "get_morning_snapshot", date=DAY)["workload"]
    assert len(workload["rows"]) == 7
    assert workload["truncated"] is False


def test_snapshot_with_claude_data_fits_max_chars(conn: sqlite3.Connection) -> None:
    put_claude_week(conn)
    assert len(call_text(conn, "get_morning_snapshot", date=DAY)) <= SNAPSHOT_MAX_CHARS


def test_snapshot_workload_days_do_not_depend_on_claude_data(conn: sqlite3.Connection) -> None:
    before = call(conn, "get_morning_snapshot", date=DAY)["workload"]
    for day in range(1, 8):
        for kind in CLAUDE_COUNTERS:
            put_screen(conn, f"2026-10-0{day}", kind, 12)
    after = call(conn, "get_morning_snapshot", date=DAY)["workload"]
    assert [r["date"] for r in after["rows"]] == [r["date"] for r in before["rows"]]
    assert after["truncated"] == before["truncated"]


def test_snapshot_workload_rows_have_screen_hours(conn: sqlite3.Connection) -> None:
    put_screen(conn, "2026-10-05", "screen_work_hours", 3.5)
    put_screen(conn, "2026-10-05", "screen_evening_hours", 1.25)
    row = {r["date"]: r for r in call(conn, "get_morning_snapshot", date=DAY)["workload"]["rows"]}[
        "2026-10-05"
    ]
    assert row["screen_work_hours"] == 3.5
    assert row["screen_evening_hours"] == 1.25
    assert row["screen_hobby_hours"] is None


def test_snapshot_workload_rows_have_demand_hours(conn: sqlite3.Connection) -> None:
    put_screen(conn, "2026-10-05", "screen_challenge_hours", 2.5)
    rows = call(conn, "get_morning_snapshot", date=DAY)["workload"]["rows"]
    row = {r["date"]: r for r in rows}["2026-10-05"]
    assert row["screen_challenge_hours"] == 2.5
    assert row["screen_hindrance_hours"] is None


def test_snapshot_workload_has_calendar_demand_hours_but_ahead_has_not(
    conn: sqlite3.Connection,
) -> None:
    replace_calendar_window(
        conn, "2026-09-01", "2026-10-31", [event("2026-10-05", demand="challenge")]
    )
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    row = {r["date"]: r for r in snapshot["workload"]["rows"]}["2026-10-05"]
    assert row["challenge_hours"] == 2.0
    assert row["hindrance_hours"] == 0
    for r in snapshot["workload_ahead"]["rows"]:
        assert "challenge_hours" not in r
        assert "hindrance_hours" not in r


def test_snapshot_workload_ahead_has_no_screen_fields(conn: sqlite3.Connection) -> None:
    put_screen(conn, "2026-10-10", "screen_work_hours", 3.5)
    ahead = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    assert ahead
    for r in ahead:
        assert not [k for k in r if k.startswith("screen_")]


def test_synced_screen_has_no_window_titles_in_mcp_answers(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "СЕКРЕТНЫЙ_ЗАГОЛОВОК_ОКНА"
    events = [
        {"duration": 3600, "data": {"app": "Alpha Editor", "title": secret, "$category": ["work"]}}
    ]

    class Response:
        def read(self) -> bytes:
            return json.dumps([events] * 4).encode("utf-8")

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Response())
    paths = f'[paths]\ntodo = "{tmp_path / "no-todo.json"}"\nhb_watch = "{tmp_path / "no-hb"}"\n'
    config = load_config(
        write_config(tmp_path / "s.toml", paths + '[screen]\nwork = ["Alpha Editor"]\n')
    )
    assert config.screen is not None
    sync_workload(
        conn,
        reader=FakeCalendar(),
        config=config,
        days=1,
        today=date.fromisoformat(DAY),
        screen=AwReader(config.screen),
    )
    assert secret not in "\n".join(conn.iterdump())
    assert call(conn, "get_workload", date_from=DAY, date_to=DAY)["rows"][0]["screen_work_hours"]
    assert secret not in call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=True)
    assert secret not in call_text(conn, "get_morning_snapshot", date=DAY)


def test_snapshot_has_no_event_titles_or_raw_json(conn: sqlite3.Connection) -> None:
    replace_calendar_window(
        conn, "2026-09-01", "2026-10-31", [event("2026-10-05"), event("2026-10-10")]
    )
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert TITLE not in text
    assert "SECRET_RAW_PAYLOAD" not in text
