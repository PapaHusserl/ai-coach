"""get_sleep(date) и секция sleep в snapshot. Синтетические данные."""

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest
from fake_clock import freeze
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, tool_names

from ai_coach.load.sleep import sleep_report
from ai_coach.store.garmin_data import upsert_daily_metrics

DAY = "2026-10-31"
KEYS = {
    "date",
    "norm_h",
    "norm_nights",
    "last_night_h",
    "nap_h",
    "debt_7_h",
    "nights_7",
    "debt_14_h",
    "nights_14",
    "wake_at",
    "awake_h",
    "caution_from",
    "signals",
}


def put(conn: sqlite3.Connection, day: str, hours: float, wake: str | None = None) -> None:
    sleep: dict[str, object] = {}
    if wake is not None:
        millis = int(datetime.fromisoformat(wake).replace(tzinfo=UTC).timestamp() * 1000)
        sleep["dailySleepDTO"] = {"sleepEndTimestampLocal": millis}
    upsert_daily_metrics(
        conn,
        {
            "date": day,
            "sleep_seconds": int(hours * 3600),
            "raw_json": {"secret": "SECRET_RAW", "sleep": sleep},
        },
    )


def thirty_nights(conn: sqlite3.Connection) -> None:
    for number in range(29):
        put(conn, (date(2026, 10, 2) + timedelta(days=number)).isoformat(), 7)
    put(conn, DAY, 5.9, "2026-10-31 07:10:00")


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_sleep" in tool_names(conn)


def test_empty_base_has_no_norm_and_no_signals(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_sleep", date=DAY)
    assert set(answer) == KEYS
    assert answer["norm_h"] is None
    assert answer["debt_7_h"] is None
    assert answer["debt_14_h"] is None
    assert answer["signals"] == []
    assert answer["norm_nights"] == 0


def test_thirty_nights_match_report(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    thirty_nights(conn)
    freeze(monkeypatch, "2026-11-05 12:00:00")
    assert call(conn, "get_sleep", date=DAY) == sleep_report(conn, DAY)


def test_thirty_nights_numbers(conn: sqlite3.Connection) -> None:
    thirty_nights(conn)
    answer = call(conn, "get_sleep", date=DAY)
    assert (answer["norm_h"], answer["norm_nights"]) == (7.0, 30)
    assert answer["debt_7_h"] == 1.1
    assert answer["wake_at"] == "2026-10-31 07:10"
    assert answer["caution_from"] == "2026-10-31 23:10"
    assert [s["kind"] for s in answer["signals"]] == ["short_night"]


def test_awake_hours_today(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    thirty_nights(conn)
    freeze(monkeypatch, "2026-10-31 11:00:00")
    assert call(conn, "get_sleep", date=DAY)["awake_h"] == 3.8


def test_bad_date_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_sleep", date="вчера")


def test_answer_has_no_raw_json(conn: sqlite3.Connection) -> None:
    thirty_nights(conn)
    text = call_text(conn, "get_sleep", date=DAY)
    assert "raw_json" not in text
    assert "SECRET_RAW" not in text


# --- snapshot ---


def test_snapshot_has_sleep_with_same_keys(conn: sqlite3.Connection) -> None:
    thirty_nights(conn)
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert set(snapshot["sleep"]) == KEYS
    assert snapshot["sleep"]["norm_h"] == 7.0


def test_snapshot_sleep_equals_tool_answer(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    thirty_nights(conn)
    freeze(monkeypatch, "2026-11-05 12:00:00")
    assert call(conn, "get_morning_snapshot", date=DAY)["sleep"] == call(
        conn, "get_sleep", date=DAY
    )


def test_snapshot_sleep_without_data(conn: sqlite3.Connection) -> None:
    sleep = call(conn, "get_morning_snapshot", date=DAY)["sleep"]
    assert sleep["norm_h"] is None
    assert sleep["signals"] == []


def test_snapshot_sleep_has_no_raw_json(conn: sqlite3.Connection) -> None:
    thirty_nights(conn)
    text = json.dumps(call(conn, "get_morning_snapshot", date=DAY)["sleep"])
    assert "SECRET_RAW" not in text
