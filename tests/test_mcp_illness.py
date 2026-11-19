"""get_illness(date) и секция illness в snapshot. Синтетические данные."""

import asyncio
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, db_file, tool_names

from ai_coach.load.episode import REST_DAYS
from ai_coach.load.illness import STREAK_DAYS, SWC_K, illness_report
from ai_coach.mcp_server import build_server
from ai_coach.store.garmin_data import upsert_activity, upsert_daily_metrics, upsert_threshold

DAY = "2026-11-02"
COACH = Path(__file__).resolve().parent.parent / ".claude" / "agents" / "coach.md"


def shift(days: int) -> str:
    return (date.fromisoformat(DAY) - timedelta(days=days)).isoformat()


def put(conn: sqlite3.Connection, days: int, rhr: float, hrv: float) -> None:
    upsert_daily_metrics(
        conn,
        {
            "date": shift(days),
            "hrv_last_night": hrv,
            "raw_json": {"secret": "SECRET_RAW", "sleep": {"restingHeartRate": rhr}},
        },
    )


def thirty_days(conn: sqlite3.Connection) -> None:
    """30 дней до DAY включительно, два последних вне коридора; порог пульса для нагрузки."""
    for days in range(29, -1, -1):
        outlier = days == 20
        put(conn, days, 60 if outlier else 50, 70 if outlier else 60)
    put(conn, 1, 90, 10)
    put(conn, 0, 90, 10)
    upsert_threshold(
        conn,
        {
            "sport": "run",
            "source": "garmin_lt",
            "calendar_date": shift(40),
            "lthr": 170,
            "raw_json": {},
        },
    )


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_illness" in tool_names(conn)


def test_empty_base_has_no_corridors_and_no_signal(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_illness", date=DAY)
    assert answer["rhr_high_from"] is None
    assert answer["hrv_low_from"] is None
    assert answer["streak"] == 0
    assert answer["signals"] == []
    assert answer["baseline_days"] == 0


def test_answer_matches_illness_report(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    answer = call(conn, "get_illness", date=DAY)
    expected = illness_report(conn, DAY, {shift(1): 0.0})
    assert "load_error" not in answer
    assert answer == expected
    assert answer["streak"] == 2
    assert answer["signals"][0]["kind"] == "illness_risk"


def one_out_day(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    put(conn, 1, 50, 60)


def test_one_out_day_gives_one_corridor_out_in_tool_and_snapshot(conn: sqlite3.Connection) -> None:
    one_out_day(conn)
    expected = [{"kind": "corridor_out", "value": 1, "limit": STREAK_DAYS}]
    assert call(conn, "get_illness", date=DAY)["signals"] == expected
    assert call(conn, "get_morning_snapshot", date=DAY)["illness"]["signals"] == expected


def test_get_illness_description_names_signal_and_corridor(conn: sqlite3.Connection) -> None:
    server = build_server(db_file(conn))
    tools = asyncio.run(server.list_tools())
    text = next(t.description or "" for t in tools if t.name == "get_illness")
    swc = f"{SWC_K:g}".replace(".", ",")
    assert "corridor_out" in text
    assert f"±{swc} SD" in text
    assert "выше или HRV ниже" in text
    assert "выше и HRV ниже" not in text


def test_answer_has_seven_days(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    assert len(call(conn, "get_illness", date=DAY)["days"]) == 7


def test_without_resting_hr_for_load_reports_load_error(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_illness", date=DAY)
    assert "пульса покоя" in answer["load_error"]
    assert answer["tss_yesterday"] is None


def test_trained_yesterday_comes_from_load(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    upsert_activity(
        conn,
        {
            "activity_id": 1,
            "start_time_local": f"{shift(1)} 07:00:00",
            "type_key": "running",
            "duration_s": 3600,
            "avg_hr": 150,
            "raw_json": {},
        },
    )
    answer = call(conn, "get_illness", date=DAY)
    assert "trained_yesterday" in answer["confounders"]
    assert answer["tss_yesterday"] > 0


def test_coach_allows_tool() -> None:
    assert "mcp__ai-coach__get_illness" in COACH.read_text()


def test_bad_date_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_illness", date="вчера")


def test_answer_has_no_raw_json(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    assert "SECRET_RAW" not in call_text(conn, "get_illness", date=DAY)


# --- snapshot ---


def test_snapshot_has_illness_without_days(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    section = call(conn, "get_morning_snapshot", date=DAY)["illness"]
    full = call(conn, "get_illness", date=DAY)
    assert "days" not in section
    assert section == {k: v for k, v in full.items() if k != "days"}


# --- episode и сигналы фаз (Н33, партия 2б) ---


def heavy_yesterday(conn: sqlite3.Connection) -> None:
    from ai_coach.store.journal import add_wellbeing

    add_wellbeing(
        conn,
        {"date": shift(1), "logged_at": f"{shift(1)} 09:00:00", "score": 2, "text": "озноб"},
    )


def test_get_illness_answer_has_episode_with_phase(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    heavy_yesterday(conn)
    answer = call(conn, "get_illness", date=DAY)
    assert answer["episode"]["phase"] == "rest"
    assert answer["episode"]["not_clean"] == ["no_record", "corridor"]


def test_get_illness_signal_illness_rest_has_why(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    heavy_yesterday(conn)
    signals = call(conn, "get_illness", date=DAY)["signals"]
    rest = [s for s in signals if s["kind"] == "illness_rest"]
    assert rest == [
        {"kind": "illness_rest", "value": 1, "limit": REST_DAYS, "why": ["no_record", "corridor"]}
    ]


def test_get_illness_empty_base_has_episode_without_phase(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_illness", date=DAY)
    assert answer["episode"]["phase"] is None


def test_get_illness_description_names_episode_and_phase_signals(
    conn: sqlite3.Connection,
) -> None:
    server = build_server(db_file(conn))
    tools = asyncio.run(server.list_tools())
    text = next(t.description or "" for t in tools if t.name == "get_illness")
    for needle in ("episode", "illness_rest", "illness_return", "why"):
        assert needle in text, needle


def test_snapshot_illness_has_episode_and_fits_limit(conn: sqlite3.Connection) -> None:
    from ai_coach.mcp_server.snapshot import SNAPSHOT_MAX_CHARS

    thirty_days(conn)
    heavy_yesterday(conn)
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    section = json.loads(text)["illness"]
    assert section["episode"]["phase"] == "rest"
    assert len(text) <= SNAPSHOT_MAX_CHARS


def test_snapshot_illness_without_data(conn: sqlite3.Connection) -> None:
    section = call(conn, "get_morning_snapshot", date=DAY)["illness"]
    assert section["signals"] == []
    assert section["rhr_high_from"] is None


def test_snapshot_illness_has_no_raw_json(conn: sqlite3.Connection) -> None:
    thirty_days(conn)
    text = json.dumps(call(conn, "get_morning_snapshot", date=DAY)["illness"])
    assert "SECRET_RAW" not in text
