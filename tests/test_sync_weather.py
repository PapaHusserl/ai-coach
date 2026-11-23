"""sync_weather: место, сервис, обе таблицы и sync_log (П7, партия 4)."""

import copy
import json
import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ai_coach.location import LocationError, Place
from ai_coach.store.journal import sync_runs_on
from ai_coach.weather import WeatherError

FIXTURE = Path(__file__).parent / "fixtures" / "weather" / "open_meteo.json"
NOW = datetime(2026, 11, 22, 14, 10)
PLACE = Place(52.52, 13.41)


def answer(shift_days: int = 0) -> dict[str, Any]:
    """Настоящий ответ сервиса; shift_days - сдвиг дат дней назад (вчерашний ответ)."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if shift_days:
        data = copy.deepcopy(data)
        daily = data["daily"]["time"]
        daily[:] = [(date.fromisoformat(d) - timedelta(days=shift_days)).isoformat() for d in daily]
        stamp = datetime.fromisoformat(data["current"]["time"]) - timedelta(days=shift_days)
        data["current"]["time"] = stamp.strftime("%Y-%m-%dT%H:%M")
    return data


def sync(
    conn: sqlite3.Connection,
    now: datetime = NOW,
    locate: Callable[[], Place] | None = None,
    fetch: Callable[[Place], dict[str, Any]] | None = None,
) -> str:
    from ai_coach.sync.weather_sync import sync_weather

    return sync_weather(
        conn,
        now=now,
        locate=locate or (lambda: PLACE),
        fetch=fetch or (lambda place: answer()),
    )


def refuse(reason: str) -> Callable[[], Place]:
    def locate() -> Place:
        raise LocationError(reason)

    return locate


def no_network(place: Place) -> dict[str, Any]:
    raise WeatherError("нет связи")


def count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def weather_log(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    sql = "SELECT kind, status FROM sync_log WHERE kind = 'weather' ORDER BY id"
    return [(r["kind"], r["status"]) for r in conn.execute(sql)]


def write_spare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "with-weather.toml"
    config.write_text("[weather]\nlatitude = 52.5234\nlongitude = 13.4114\n", encoding="utf-8")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))


def test_writes_one_now_row_and_seven_day_rows(conn: sqlite3.Connection) -> None:
    sync(conn)
    assert count(conn, "weather_now") == 1
    assert count(conn, "weather_days") == 7


def test_every_row_has_rounded_place(conn: sqlite3.Connection) -> None:
    sync(conn)
    for table in ("weather_now", "weather_days"):
        places = {(r["lat"], r["lon"]) for r in conn.execute(f"SELECT lat, lon FROM {table}")}
        assert places == {(52.52, 13.41)}, table


def test_now_row_has_macos_source_and_offset_from_answer(conn: sqlite3.Connection) -> None:
    sync(conn)
    row = conn.execute("SELECT * FROM weather_now").fetchone()
    assert row["place_source"] == "macos"
    assert row["utc_offset_seconds"] == answer()["utc_offset_seconds"]
    assert row["observed_at"] == "2026-11-22T14:00"


def test_success_logs_weather_ok(conn: sqlite3.Connection) -> None:
    sync(conn)
    assert weather_log(conn) == [("weather", "ok")]


def test_summary_without_mark_for_macos_place(conn: sqlite3.Connection) -> None:
    assert sync(conn) == "погода: записана, +4°"


def test_config_place_gives_config_source_and_mark(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_spare(tmp_path, monkeypatch)
    result = sync(conn, locate=refuse("denied"))
    assert result == "погода: записана, +4° (место из конфига)"
    row = conn.execute("SELECT place_source, lat, lon FROM weather_now").fetchone()
    assert (row["place_source"], row["lat"], row["lon"]) == ("config", 52.52, 13.41)


def test_config_place_is_passed_to_service_rounded(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_spare(tmp_path, monkeypatch)
    asked: list[Place] = []

    def fetch(place: Place) -> dict[str, Any]:
        asked.append(place)
        return answer()

    sync(conn, locate=refuse("denied"), fetch=fetch)
    assert asked == [Place(52.52, 13.41)]


@pytest.mark.parametrize(
    ("reason", "text"),
    [
        ("denied", "погода: нет доступа к геолокации"),
        ("off", "погода: нет доступа к геолокации"),
        ("timeout", "погода: место не определено"),
        ("unavailable", "погода: место не определено"),
    ],
)
def test_place_failure_without_spare_gives_reason_text(
    conn: sqlite3.Connection, reason: str, text: str
) -> None:
    assert sync(conn, locate=refuse(reason)) == text


def test_service_failure_gives_no_connection_text(conn: sqlite3.Connection) -> None:
    assert sync(conn, fetch=no_network) == "погода: нет связи"


def test_place_failure_leaves_tables_untouched_and_logs_error(conn: sqlite3.Connection) -> None:
    sync(conn, locate=refuse("denied"))
    assert (count(conn, "weather_now"), count(conn, "weather_days")) == (0, 0)
    assert weather_log(conn) == [("weather", "error")]


def test_service_failure_leaves_tables_untouched_and_logs_error(conn: sqlite3.Connection) -> None:
    sync(conn, fetch=no_network)
    assert (count(conn, "weather_now"), count(conn, "weather_days")) == (0, 0)
    assert weather_log(conn) == [("weather", "error")]


def test_unparsable_answer_is_no_connection_and_writes_nothing(conn: sqlite3.Connection) -> None:
    result = sync(conn, fetch=lambda place: {"current": {}})
    assert result == "погода: нет связи"
    assert (count(conn, "weather_now"), count(conn, "weather_days")) == (0, 0)
    assert weather_log(conn) == [("weather", "error")]


def test_failure_does_not_raise_after_earlier_data(conn: sqlite3.Connection) -> None:
    sync(conn)
    sync(conn, now=NOW + timedelta(minutes=20), fetch=no_network)
    assert count(conn, "weather_now") == 1
    assert weather_log(conn) == [("weather", "ok"), ("weather", "error")]


def test_second_sync_same_answer_keeps_one_now_row_and_seven_days(
    conn: sqlite3.Connection,
) -> None:
    sync(conn)
    sync(conn, now=NOW + timedelta(minutes=20))
    assert count(conn, "weather_now") == 1
    assert count(conn, "weather_days") == 7


def test_second_sync_updates_days_with_fresh_numbers(conn: sqlite3.Connection) -> None:
    sync(conn)
    changed = answer()
    changed["daily"]["temperature_2m_max"][0] = 9.9
    later = NOW + timedelta(minutes=20)
    sync(conn, now=later, fetch=lambda place: changed)
    row = conn.execute("SELECT t_max, fetched_at FROM weather_days WHERE date = '2026-11-22'")
    first = row.fetchone()
    assert first["t_max"] == 9.9
    assert "14:30" in first["fetched_at"]
    assert count(conn, "weather_days") == 7


def test_new_observation_time_adds_now_row(conn: sqlite3.Connection) -> None:
    sync(conn)
    later = answer()
    later["current"]["time"] = "2026-11-22T14:15"
    sync(conn, now=NOW + timedelta(minutes=20), fetch=lambda place: later)
    assert count(conn, "weather_now") == 2


def test_yesterday_row_is_not_changed_by_next_day_sync(conn: sqlite3.Connection) -> None:
    yesterday = NOW - timedelta(days=1)
    sync(conn, now=yesterday, fetch=lambda place: answer(shift_days=1))
    sql = "SELECT * FROM weather_days WHERE date = '2026-11-21'"
    before = dict(conn.execute(sql).fetchone())
    sync(conn)
    assert dict(conn.execute(sql).fetchone()) == before
    assert count(conn, "weather_days") == 8


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (3.7, "+4°"),
        (2.5, "+3°"),
        (0.5, "+1°"),
        (-1.5, "−1°"),
        (-0.3, "0°"),
        (-2.6, "−3°"),
    ],
)
def test_degrees_rounds_half_up_with_real_minus(value: float, text: str) -> None:
    from ai_coach.sync.weather_sync import degrees

    assert degrees(value) == text


def test_summary_with_negative_temperature(conn: sqlite3.Connection) -> None:
    cold = answer()
    cold["current"]["temperature_2m"] = -2.6
    assert sync(conn, fetch=lambda place: cold) == "погода: записана, −3°"


@pytest.mark.parametrize("bad", [None, "3.7"])
def test_non_number_in_current_is_no_connection_and_writes_nothing(
    conn: sqlite3.Connection, bad: Any
) -> None:
    broken = answer()
    broken["current"]["temperature_2m"] = bad
    assert sync(conn, fetch=lambda place: broken) == "погода: нет связи"
    assert (count(conn, "weather_now"), count(conn, "weather_days")) == (0, 0)
    assert weather_log(conn) == [("weather", "error")]


@pytest.mark.parametrize("key", ["weather_code", "temperature_2m_max", "temperature_2m_min"])
def test_none_in_day_is_no_connection_and_writes_nothing(
    conn: sqlite3.Connection, key: str
) -> None:
    broken = answer()
    broken["daily"][key][0] = None
    assert sync(conn, fetch=lambda place: broken) == "погода: нет связи"
    assert (count(conn, "weather_now"), count(conn, "weather_days")) == (0, 0)
    assert weather_log(conn) == [("weather", "error")]


def test_day_without_precip_prob_is_written_with_null(conn: sqlite3.Connection) -> None:
    data = answer()
    data["daily"]["precipitation_probability_max"][0] = None
    assert sync(conn, fetch=lambda place: data) == "погода: записана, +4°"
    row = conn.execute("SELECT precip_prob FROM weather_days WHERE date = '2026-11-22'")
    assert row.fetchone()["precip_prob"] is None


def test_weather_does_not_count_as_sync_run(conn: sqlite3.Connection) -> None:
    sync(conn)
    sync(conn, locate=refuse("denied"))
    assert sync_runs_on(conn, NOW.date().isoformat()) == 0
    assert sync_runs_on(conn, date.today().isoformat()) == 0
