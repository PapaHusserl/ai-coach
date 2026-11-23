"""Инструмент MCP get_weather: погода из базы (П7, партия 5)."""

import json
import sqlite3
from datetime import date, datetime, timedelta

import pytest
from fake_clock import freeze
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, tool_names

from ai_coach.mcp_server.server import INSTRUCTIONS, TOOLS
from ai_coach.mcp_server.tools import MAX_CHARS

DAY = "2026-11-22"


@pytest.fixture(autouse=True)
def today(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{DAY} 14:10:00")


HIDDEN_KEYS = ("lat", "lon", "place_source", "utc_offset_seconds")
# Значения, которых нет ни в одном числе ответа: координаты и смещение пояса не должны просочиться.
LAT, LON, OFFSET = 52.52, 13.41, 12345


def put_now(
    conn: sqlite3.Connection,
    observed_at: str,
    temperature: float = 3.7,
    code: int = 2,
    pressure: float = 1018.4,
) -> None:
    conn.execute(
        "INSERT INTO weather_now (observed_at, temperature, apparent, code, wind, pressure, "
        "fetched_at, lat, lon, place_source, utc_offset_seconds) "
        "VALUES (?, ?, 0.3, ?, 3.09, ?, '2026-11-22T14:10:00', ?, ?, 'macos', ?)",
        (observed_at, temperature, code, pressure, LAT, LON, OFFSET),
    )
    conn.commit()


def put_day(conn: sqlite3.Connection, day: str, code: int = 80) -> None:
    conn.execute(
        "INSERT INTO weather_days (date, code, t_max, t_min, precip_prob, fetched_at, lat, lon) "
        "VALUES (?, ?, 5.6, 1.9, 88, '2026-11-22T14:10:00', ?, ?)",
        (day, code, LAT, LON),
    )
    conn.commit()


def put_many_days(conn: sqlite3.Connection, first: str, count: int) -> None:
    start = date.fromisoformat(first)
    for i in range(count):
        put_day(conn, (start + timedelta(days=i)).isoformat())


def put_many_now(conn: sqlite3.Connection, day: str, count: int) -> None:
    for i in range(count):
        put_now(conn, f"{day}T{i // 60:02d}:{i % 60:02d}", temperature=float(i))


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_weather" in tool_names(conn)


def put_hours(conn: sqlite3.Connection, first: str, count: int) -> None:
    start = datetime.fromisoformat(first)
    for i in range(count):
        conn.execute(
            "INSERT INTO weather_hours (time, temperature, pressure, pressure_surface, humidity, "
            "wind, fetched_at, lat, lon, place_source, source) "
            "VALUES (?, ?, ?, 1008.4, 80, 3.0, '2026-11-22T14:10:00', ?, ?, 'macos', 'forecast')",
            (
                (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M"),
                float(i),
                1000.0 + i,
                LAT,
                LON,
            ),
        )
    conn.commit()


def test_answer_has_now_rows_truncated_history_and_hourly(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_weather", date_from=DAY, date_to=DAY)
    assert set(answer) == {"now", "rows", "truncated", "history", "hourly"}


def test_now_is_last_observation_even_outside_period(conn: sqlite3.Connection) -> None:
    put_now(conn, "2026-11-22T08:30", temperature=1.0)
    put_now(conn, "2026-11-23T19:15", temperature=8.0)
    answer = call(conn, "get_weather", date_from=DAY, date_to=DAY)
    assert answer["now"]["observed_at"] == "2026-11-23T19:15"
    assert answer["now"]["temperature"] == 8.0


def test_now_has_exactly_its_keys(conn: sqlite3.Connection) -> None:
    put_now(conn, "2026-11-22T08:30")
    now = call(conn, "get_weather", date_from=DAY, date_to=DAY)["now"]
    assert set(now) == {
        "observed_at",
        "temperature",
        "apparent",
        "code",
        "word",
        "wind",
        "pressure",
    }


def test_now_word_is_taken_from_code(conn: sqlite3.Connection) -> None:
    put_now(conn, "2026-11-22T08:30", code=2)
    now = call(conn, "get_weather", date_from=DAY, date_to=DAY)["now"]
    assert now["word"] == "переменная облачность"


def test_rows_are_days_of_period_with_word(conn: sqlite3.Connection) -> None:
    put_day(conn, "2026-11-21")
    put_day(conn, DAY, code=80)
    put_day(conn, "2026-11-23", code=3)
    answer = call(conn, "get_weather", date_from=DAY, date_to="2026-11-23")
    assert [r["date"] for r in answer["rows"]] == [DAY, "2026-11-23"]
    assert [r["word"] for r in answer["rows"]] == ["ливень", "пасмурно"]


def test_day_row_has_exactly_its_keys(conn: sqlite3.Connection) -> None:
    put_day(conn, DAY)
    row = call(conn, "get_weather", date_from=DAY, date_to=DAY)["rows"][0]
    assert set(row) == {"date", "code", "word", "t_max", "t_min", "precip_prob", "fetched_at"}


def test_history_row_has_three_keys(conn: sqlite3.Connection) -> None:
    put_now(conn, "2026-11-22T08:30")
    history = call(conn, "get_weather", date_from=DAY, date_to=DAY)["history"]
    assert set(history) == {"rows", "truncated"}
    assert set(history["rows"][0]) == {"observed_at", "temperature", "pressure"}


def test_history_is_in_time_order_inside_period(conn: sqlite3.Connection) -> None:
    put_now(conn, "2026-11-22T19:15", temperature=1.0)
    put_now(conn, "2026-11-21T23:45", temperature=9.0)
    put_now(conn, "2026-11-22T08:30", temperature=2.0)
    history = call(conn, "get_weather", date_from=DAY, date_to=DAY)["history"]
    assert [r["observed_at"] for r in history["rows"]] == ["2026-11-22T08:30", "2026-11-22T19:15"]
    assert history["truncated"] is False


def test_history_same_observation_time_is_one_point(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import add_weather_now

    for fetched in ("2026-11-22T14:10:00", "2026-11-22T14:20:00"):
        add_weather_now(
            conn,
            {
                "observed_at": "2026-11-22T14:00",
                "temperature": 3.7,
                "apparent": 0.3,
                "code": 2,
                "wind": 3.09,
                "pressure": 1018.4,
                "fetched_at": fetched,
                "lat": LAT,
                "lon": LON,
                "place_source": "macos",
                "utc_offset_seconds": OFFSET,
            },
        )
    history = call(conn, "get_weather", date_from=DAY, date_to=DAY)["history"]
    assert len(history["rows"]) == 1


def test_answer_has_no_place_keys_or_values(conn: sqlite3.Connection) -> None:
    put_now(conn, "2026-11-22T08:30")
    put_day(conn, DAY)
    text = call_text(conn, "get_weather", date_from=DAY, date_to=DAY)
    for key in HIDDEN_KEYS:
        assert key not in text
    for value in (str(LAT), str(LON), str(OFFSET), "macos"):
        assert value not in text


def test_history_over_limit_drops_oldest_and_marks_only_history(conn: sqlite3.Connection) -> None:
    put_many_now(conn, "2026-11-01", 61)
    put_day(conn, "2026-11-01")
    answer = call(conn, "get_weather", date_from="2026-11-01", date_to="2026-11-01")
    history = answer["history"]
    assert len(history["rows"]) == 60
    assert history["rows"][0]["observed_at"] == "2026-11-01T00:01"
    assert history["rows"][-1]["observed_at"] == "2026-11-01T01:00"
    assert history["truncated"] is True
    assert answer["truncated"] is False


def test_days_over_limit_keep_newest_and_do_not_mark_history(conn: sqlite3.Connection) -> None:
    put_many_days(conn, "2026-08-01", 92)
    answer = call(conn, "get_weather", date_from="2026-08-01", date_to="2026-10-31")
    assert len(answer["rows"]) == 60
    assert answer["rows"][-1]["date"] == "2026-10-31"
    assert answer["rows"][0]["date"] == "2026-09-02"
    assert answer["truncated"] is True
    assert answer["history"]["truncated"] is False


def test_full_answer_is_shorter_than_max_chars(conn: sqlite3.Connection) -> None:
    put_many_days(conn, "2026-09-01", 60)
    put_many_now(conn, "2026-10-15", 60)
    answer = call(conn, "get_weather", date_from="2026-09-01", date_to="2026-10-30")
    assert len(answer["rows"]) == 60
    assert len(answer["history"]["rows"]) == 60
    assert len(json.dumps(answer, ensure_ascii=False)) < MAX_CHARS


def test_empty_tables_give_empty_answer(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_weather", date_from=DAY, date_to=DAY)
    assert answer["now"] is None
    assert answer["rows"] == []
    assert answer["truncated"] is False
    assert answer["history"] == {"rows": [], "truncated": False}


def test_bad_date_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_weather", date_from="22.11.2026", date_to=DAY)


def test_range_over_92_days_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_weather", date_from="2026-07-01", date_to=DAY)


def test_end_before_start_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_weather", date_from=DAY, date_to="2026-11-20")


def test_description_names_sync_and_freshness() -> None:
    text = TOOLS["get_weather"][1]
    assert "coach sync" in text
    assert "последн" in text


def test_description_says_history_is_a_point_per_sync() -> None:
    text = TOOLS["get_weather"][1]
    assert "history" in text
    assert "на синк" in text


def test_hourly_192_hours_give_60_rows_every_third_hour(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-21T00:00", 192)
    hourly = call(conn, "get_weather", date_from=DAY, date_to=DAY)["hourly"]
    wide = call(conn, "get_weather", date_from="2026-11-21", date_to="2026-11-28")["hourly"]
    assert wide == hourly
    assert len(hourly["rows"]) == 60
    assert hourly["rows"][0]["time"] == "2026-11-21T00:00"
    assert hourly["rows"][1]["time"] == "2026-11-21T03:00"
    assert hourly["rows"][-1]["time"] == "2026-11-28T09:00"
    assert hourly["truncated"] is True


def test_hourly_row_has_only_time_temperature_and_pressure(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-21T00:00", 24)
    hourly = call(conn, "get_weather", date_from=DAY, date_to=DAY)["hourly"]
    assert set(hourly["rows"][0]) == {"time", "temperature", "pressure"}
    assert hourly["rows"][1] == {"time": "2026-11-21T03:00", "temperature": 3.0, "pressure": 1003.0}


def test_hourly_short_series_is_not_truncated(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-21T00:00", 24)
    hourly = call(conn, "get_weather", date_from=DAY, date_to=DAY)["hourly"]
    assert len(hourly["rows"]) == 8
    assert hourly["truncated"] is False


def test_hourly_does_not_change_history(conn: sqlite3.Connection) -> None:
    put_now(conn, "2026-11-22T08:30")
    put_hours(conn, "2026-11-21T00:00", 24)
    history = call(conn, "get_weather", date_from=DAY, date_to=DAY)["history"]
    assert [r["observed_at"] for r in history["rows"]] == ["2026-11-22T08:30"]


def test_empty_hours_give_empty_hourly(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_weather", date_from=DAY, date_to=DAY)
    assert answer["hourly"] == {"rows": [], "truncated": False}


def test_hourly_leaks_no_place_keys_or_values(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-22T00:00", 24)
    text = call_text(conn, "get_weather", date_from=DAY, date_to=DAY)
    for key in (*HIDDEN_KEYS, "pressure_surface", "humidity"):
        assert key not in text
    for value in (str(LAT), str(LON), "macos"):
        assert value not in text


def test_three_full_lists_are_shorter_than_max_chars(conn: sqlite3.Connection) -> None:
    put_many_days(conn, "2026-09-01", 60)
    put_many_now(conn, "2026-10-15", 60)
    put_hours(conn, "2026-11-21T00:00", 192)
    answer = call(conn, "get_weather", date_from="2026-09-01", date_to="2026-10-30")
    assert len(answer["hourly"]["rows"]) == 60
    assert len(json.dumps(answer, ensure_ascii=False)) < MAX_CHARS


def test_hourly_starts_yesterday_even_when_archive_hours_are_older(
    conn: sqlite3.Connection,
) -> None:
    put_hours(conn, "2026-11-19T00:00", 240)
    rows = call(conn, "get_weather", date_from=DAY, date_to=DAY)["hourly"]["rows"]
    assert rows[0]["time"] == "2026-11-21T00:00"
    assert not [r for r in rows if r["time"] < "2026-11-21"]


def test_hourly_without_hours_since_yesterday_is_empty(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-19T00:00", 48)
    hourly = call(conn, "get_weather", date_from=DAY, date_to=DAY)["hourly"]
    assert hourly == {"rows": [], "truncated": False}


def test_hourly_step_follows_hour_of_day_not_row_number(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-21T00:00", 24)
    conn.execute("DELETE FROM weather_hours WHERE time = '2026-11-21T01:00'")
    conn.commit()
    rows = call(conn, "get_weather", date_from=DAY, date_to=DAY)["hourly"]["rows"]
    assert [r["time"][-5:] for r in rows[:3]] == ["00:00", "03:00", "06:00"]


def test_hourly_row_with_null_pressure_is_kept(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-21T00:00", 24)
    conn.execute("UPDATE weather_hours SET pressure = NULL WHERE time = '2026-11-21T03:00'")
    conn.commit()
    rows = call(conn, "get_weather", date_from=DAY, date_to=DAY)["hourly"]["rows"]
    assert rows[1]["time"] == "2026-11-21T03:00"
    assert rows[1]["pressure"] is None


def backfill_old_days(conn: sqlite3.Connection) -> None:
    """Дозагрузка архивом дней до вчера (Р24 = 1: тренеру она ничего не меняет)."""
    import json
    from pathlib import Path

    from ai_coach.location import Place
    from ai_coach.sync.weather_sync import backfill_weather

    path = Path(__file__).parent / "fixtures" / "weather" / "archive.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    now = datetime(2026, 11, 22, 14, 10)
    backfill_weather(conn, Place(52.52, 13.41), "macos", now, lambda *a: raw)


def mark_first_day(conn: sqlite3.Connection) -> None:
    from ai_coach.store.journal import add_wellbeing

    values = {"date": "2026-10-07", "logged_at": "2026-10-07 09:00:00", "score": 3, "text": ""}
    add_wellbeing(conn, values)


def test_get_weather_is_the_same_after_archive_backfill(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-21T00:00", 192)
    put_now(conn, "2026-11-22T14:00")
    put_day(conn, DAY)
    mark_first_day(conn)
    before = call(conn, "get_weather", date_from="2026-10-07", date_to="2026-11-28")
    backfill_old_days(conn)
    assert call(conn, "get_weather", date_from="2026-10-07", date_to="2026-11-28") == before


def test_morning_snapshot_is_the_same_after_archive_backfill(conn: sqlite3.Connection) -> None:
    put_hours(conn, "2026-11-21T00:00", 192)
    mark_first_day(conn)
    before = call(conn, "get_morning_snapshot", date=DAY)
    backfill_old_days(conn)
    assert call(conn, "get_morning_snapshot", date=DAY) == before


def test_description_names_hourly_and_three_hour_step() -> None:
    text = TOOLS["get_weather"][1]
    assert "hourly" in text
    assert "шаг 3 ч" in text


def test_instructions_say_weather_comes_from_sync_not_from_service() -> None:
    tail = INSTRUCTIONS.split("get_weather", 1)[1][:300]
    assert "coach sync" in tail
    assert "не ходит" in tail
