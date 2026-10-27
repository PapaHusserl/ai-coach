import json
import sqlite3
import urllib.request
from datetime import date
from pathlib import Path

import pytest
from mcp_fakes import call, call_text
from workload_fakes import FakeCalendar, stored_event, write_config

from ai_coach.store.workload import replace_calendar_window, upsert_counter
from ai_coach.sync.workload_sync import sync_workload
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


def test_snapshot_workload_rows_have_screen_hours(conn: sqlite3.Connection) -> None:
    put_screen(conn, "2026-10-05", "screen_work_hours", 3.5)
    put_screen(conn, "2026-10-05", "screen_evening_hours", 1.25)
    row = {r["date"]: r for r in call(conn, "get_morning_snapshot", date=DAY)["workload"]["rows"]}[
        "2026-10-05"
    ]
    assert row["screen_work_hours"] == 3.5
    assert row["screen_evening_hours"] == 1.25
    assert row["screen_hobby_hours"] is None


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
