"""weather_view: погода в шапке пульта, место в памяти, кэш, устаревший ответ (П7, партия 2)."""

import importlib
import json
import sqlite3
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ai_coach import location, weather
from ai_coach.location import LocationError, Place
from ai_coach.weather import WeatherError

NOW = datetime(2026, 11, 22, 14, 10)
TODAY = NOW.date()
PLACE = Place(52.52, 13.41)


@pytest.fixture(autouse=True)
def wv() -> Iterator[ModuleType]:
    """Место и кэш погоды - модульные: чистое состояние до и после каждого теста."""
    from ai_coach.web import weather as web_weather

    importlib.reload(web_weather)
    yield web_weather
    importlib.reload(web_weather)


def answer(temperature: float = 3.7, start: date = TODAY, count: int = 7) -> dict[str, Any]:
    """Сырой ответ сервиса: count дней с start; день i: максимум 10+i, минимум i."""
    days = [start + timedelta(days=i) for i in range(count)]
    return {
        "utc_offset_seconds": 3600,
        "current": {
            "time": "2026-11-22T14:00",
            "temperature_2m": temperature,
            "apparent_temperature": 0.3,
            "weather_code": 2,
            "wind_speed_10m": 3.09,
            "pressure_msl": 1015.4,
        },
        "daily": {
            "time": [d.isoformat() for d in days],
            "weather_code": [80, 3, 3, 3, 3, 3, 3][:count],
            "temperature_2m_max": [10.0 + i for i in range(count)],
            "temperature_2m_min": [float(i) for i in range(count)],
            "precipitation_probability_max": [88, 28, 0, 0, 0, 0, 0][:count],
        },
    }


class Fakes:
    """Подмена читателей: место и сервис погоды, со счётом вызовов."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.places: list[Place | LocationError] = []
        self.answers: list[dict[str, Any] | WeatherError] = []
        self.place_calls = 0
        self.fetched: list[Place] = []
        monkeypatch.setattr(location, "read_place", self.read_place)
        monkeypatch.setattr(weather, "fetch_forecast", self.fetch)

    def read_place(self, *_: object, **__: object) -> Place:
        self.place_calls += 1
        item = self.places[min(self.place_calls, len(self.places)) - 1]
        if isinstance(item, LocationError):
            raise item
        return item

    def fetch(self, place: Place) -> dict[str, Any]:
        self.fetched.append(place)
        item = self.answers[min(len(self.fetched), len(self.answers)) - 1]
        if isinstance(item, WeatherError):
            raise item
        return item


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    fake = Fakes(monkeypatch)
    fake.places = [PLACE]
    fake.answers = [answer()]
    return fake


def view_at(wv: ModuleType, conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    return wv.weather_view(conn, day, now)


def test_today_has_current_today_tomorrow_and_fresh(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    view = view_at(wv, conn, TODAY, NOW)
    assert view["current"]["temperature"] == 3.7
    assert view["current"]["apparent"] == 0.3
    assert view["current"]["code"] == 2
    assert view["current"]["wind"] == 3.09
    assert (view["today"]["t_max"], view["today"]["t_min"], view["today"]["code"]) == (
        10.0,
        0.0,
        80,
    )
    assert view["today"]["precip_prob"] == 88
    assert (view["tomorrow"]["t_max"], view["tomorrow"]["t_min"]) == (11.0, 1.0)
    assert view["tomorrow"]["precip_prob"] == 28
    assert view["stale"] is False
    assert "fetched_at" in view
    assert "missing" not in view


def test_view_has_no_coordinates(wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes) -> None:
    text = json.dumps(view_at(wv, conn, TODAY, NOW))
    assert '"lat"' not in text
    assert '"lon"' not in text
    assert "52.52" not in text
    assert "13.41" not in text


def test_place_is_rounded_place_from_reader(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    view_at(wv, conn, TODAY, NOW)
    assert fakes.fetched == [PLACE]


@pytest.mark.parametrize("offset", [1, 6])
def test_other_day_in_range_is_day(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes, offset: int
) -> None:
    view = view_at(wv, conn, TODAY + timedelta(days=offset), NOW)
    assert (view["day"]["t_max"], view["day"]["t_min"]) == (10.0 + offset, float(offset))
    assert view["day"]["date"] == (TODAY + timedelta(days=offset)).isoformat()
    assert "missing" not in view


@pytest.mark.parametrize("offset", [7, -1])
def test_day_out_of_range_is_missing_range_and_nothing_is_called(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes, offset: int
) -> None:
    view = view_at(wv, conn, TODAY + timedelta(days=offset), NOW)
    assert view == {"missing": "range"}
    assert (fakes.place_calls, fakes.fetched) == (0, [])


@pytest.mark.parametrize("reason", ["denied", "off", "timeout", "unavailable"])
def test_no_place_is_missing_place_with_reason(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes, reason: str
) -> None:
    fakes.places = [LocationError(reason)]
    view = view_at(wv, conn, TODAY, NOW)
    assert view == {"missing": "place", "why": reason}
    assert fakes.fetched == []


def write_weather_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "with-weather.toml"
    config.write_text("[weather]\nlatitude = 52.5234\nlongitude = 13.4114\n", encoding="utf-8")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))


def test_fallback_from_config_when_place_denied(
    wv: ModuleType,
    conn: sqlite3.Connection,
    fakes: Fakes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_weather_config(tmp_path, monkeypatch)
    fakes.places = [LocationError("denied")]
    view = view_at(wv, conn, TODAY, NOW)
    assert view["current"]["temperature"] == 3.7
    assert "missing" not in view
    assert fakes.fetched == [Place(52.52, 13.41)]


def test_fallback_view_has_same_keys_and_no_source(
    wv: ModuleType,
    conn: sqlite3.Connection,
    fakes: Fakes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view_macos = view_at(wv, conn, TODAY, NOW)
    importlib.reload(wv)
    write_weather_config(tmp_path, monkeypatch)
    fakes.places = [LocationError("denied")]
    view_config = view_at(wv, conn, TODAY, NOW)
    assert set(view_config) == set(view_macos)
    text = json.dumps(view_config)
    assert "config" not in text
    assert "source" not in text


def test_place_is_remembered_for_an_hour(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    view_at(wv, conn, TODAY, NOW)
    view_at(wv, conn, TODAY, NOW)
    assert fakes.place_calls == 1


def test_place_is_read_again_after_61_minutes(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    view_at(wv, conn, TODAY, NOW)
    view_at(wv, conn, TODAY, NOW + timedelta(minutes=61))
    assert fakes.place_calls == 2


def test_refusal_after_success_keeps_previous_place(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.places = [PLACE, LocationError("denied")]
    view_at(wv, conn, TODAY, NOW)
    later = NOW + timedelta(minutes=61)
    view = view_at(wv, conn, TODAY, later)
    assert fakes.place_calls == 2
    assert "missing" not in view
    assert fakes.fetched == [PLACE, PLACE]


def test_weather_is_cached_for_14_minutes(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    view_at(wv, conn, TODAY, NOW)
    view_at(wv, conn, TODAY, NOW + timedelta(minutes=14))
    assert len(fakes.fetched) == 1


def test_weather_is_fetched_again_after_16_minutes(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [answer(3.7), answer(5.5)]
    view_at(wv, conn, TODAY, NOW)
    view = view_at(wv, conn, TODAY, NOW + timedelta(minutes=16))
    assert len(fakes.fetched) == 2
    assert view["current"]["temperature"] == 5.5
    assert view["stale"] is False


def test_network_down_after_success_gives_previous_numbers_stale(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [answer(), WeatherError("нет сети")]
    first = view_at(wv, conn, TODAY, NOW)
    view = view_at(wv, conn, TODAY, NOW + timedelta(minutes=20))
    assert len(fakes.fetched) == 2
    assert view["stale"] is True
    assert view["current"] == first["current"]
    assert view["fetched_at"] == first["fetched_at"]


def test_network_down_for_over_3_hours_is_missing_silent(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [answer(), WeatherError("нет сети")]
    view_at(wv, conn, TODAY, NOW)
    view = view_at(wv, conn, TODAY, NOW + timedelta(hours=3, minutes=1))
    assert view == {"missing": "silent"}


def test_network_down_for_just_under_3_hours_is_still_stale(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [answer(), WeatherError("нет сети")]
    view_at(wv, conn, TODAY, NOW)
    view = view_at(wv, conn, TODAY, NOW + timedelta(hours=2, minutes=59))
    assert view["stale"] is True


def test_network_down_without_previous_answer_is_missing_silent(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [WeatherError("нет сети")]
    assert view_at(wv, conn, TODAY, NOW) == {"missing": "silent"}


def test_view_writes_nothing_to_database(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    before = conn.total_changes
    view_at(wv, conn, TODAY, NOW)
    view_at(wv, conn, TODAY + timedelta(days=1), NOW + timedelta(minutes=20))
    assert conn.total_changes == before


def test_refusal_at_61_then_call_at_62_does_not_read_place_again(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.places = [PLACE, LocationError("denied")]
    view_at(wv, conn, TODAY, NOW)
    view_at(wv, conn, TODAY, NOW + timedelta(minutes=61))
    view_at(wv, conn, TODAY, NOW + timedelta(minutes=62))
    assert fakes.place_calls == 2


def test_refusal_after_success_with_config_section_uses_config_place(
    wv: ModuleType,
    conn: sqlite3.Connection,
    fakes: Fakes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_weather_config(tmp_path, monkeypatch)
    fakes.places = [Place(48.85, 2.35), LocationError("denied")]
    view_at(wv, conn, TODAY, NOW)
    view_at(wv, conn, TODAY, NOW + timedelta(minutes=61))
    assert fakes.fetched == [Place(48.85, 2.35), Place(52.52, 13.41)]


def test_fetched_at_is_local_iso_to_seconds(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    assert view_at(wv, conn, TODAY, NOW)["fetched_at"] == "2026-11-22T14:10:00"


MIDNIGHT_BEFORE = datetime(2026, 11, 22, 23, 50)
MIDNIGHT_AFTER = datetime(2026, 11, 23, 0, 4)


def test_new_date_refetches_even_within_cache_time(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    new_day = MIDNIGHT_AFTER.date()
    fakes.answers = [answer(), answer(start=new_day)]
    view_at(wv, conn, TODAY, MIDNIGHT_BEFORE)
    view = view_at(wv, conn, new_day, MIDNIGHT_AFTER)
    assert len(fakes.fetched) == 2
    assert view["today"]["date"] == new_day.isoformat()


def test_new_date_with_network_down_is_stale_with_shifted_days(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    new_day = MIDNIGHT_AFTER.date()
    fakes.answers = [answer(), WeatherError("нет сети")]
    view_at(wv, conn, TODAY, MIDNIGHT_BEFORE)
    view = view_at(wv, conn, new_day, MIDNIGHT_AFTER)
    assert view["stale"] is True
    assert view["today"]["date"] == new_day.isoformat()
    assert view["tomorrow"]["date"] == (new_day + timedelta(days=1)).isoformat()


def test_new_date_with_network_down_day_plus_6_is_missing_silent(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    new_day = MIDNIGHT_AFTER.date()
    fakes.answers = [answer(), WeatherError("нет сети")]
    view_at(wv, conn, TODAY, MIDNIGHT_BEFORE)
    view = view_at(wv, conn, new_day + timedelta(days=6), MIDNIGHT_AFTER)
    assert view == {"missing": "silent"}


def test_answer_with_one_day_is_missing_silent(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [answer(count=1)]
    assert view_at(wv, conn, TODAY, NOW) == {"missing": "silent"}


def test_unparseable_answer_without_previous_is_missing_silent(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [{}]
    assert view_at(wv, conn, TODAY, NOW) == {"missing": "silent"}


def test_unparseable_answer_after_success_is_stale(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [answer(), {}]
    view_at(wv, conn, TODAY, NOW)
    view = view_at(wv, conn, TODAY, NOW + timedelta(minutes=20))
    assert view["stale"] is True


def test_weather_is_fetched_again_at_exactly_15_minutes(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    view_at(wv, conn, TODAY, NOW)
    view_at(wv, conn, TODAY, NOW + timedelta(minutes=15))
    assert len(fakes.fetched) == 2


def test_place_is_read_again_at_exactly_60_minutes(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    view_at(wv, conn, TODAY, NOW)
    view_at(wv, conn, TODAY, NOW + timedelta(minutes=60))
    assert fakes.place_calls == 2


def test_network_down_for_exactly_3_hours_is_missing_silent(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [answer(), WeatherError("нет сети")]
    view_at(wv, conn, TODAY, NOW)
    assert view_at(wv, conn, TODAY, NOW + timedelta(hours=3)) == {"missing": "silent"}


def write_broken_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "broken.toml"
    config.write_text("[weather]\nlatitude = 120\nlongitude = 0\n", encoding="utf-8")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))


def test_broken_config_with_macos_place_still_gives_numbers(
    wv: ModuleType,
    conn: sqlite3.Connection,
    fakes: Fakes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_broken_config(tmp_path, monkeypatch)
    view = view_at(wv, conn, TODAY, NOW)
    assert view["current"]["temperature"] == 3.7


def test_broken_config_without_place_is_missing_place_denied(
    wv: ModuleType,
    conn: sqlite3.Connection,
    fakes: Fakes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_broken_config(tmp_path, monkeypatch)
    fakes.places = [LocationError("denied")]
    view = view_at(wv, conn, TODAY, NOW)
    assert view == {"missing": "place", "why": "denied"}


def test_day_view_with_network_down_is_stale_with_previous_fetched_at(
    wv: ModuleType, conn: sqlite3.Connection, fakes: Fakes
) -> None:
    fakes.answers = [answer(), WeatherError("нет сети")]
    first = view_at(wv, conn, TODAY, NOW)
    view = view_at(wv, conn, TODAY + timedelta(days=1), NOW + timedelta(minutes=20))
    assert view["day"]["t_max"] == 11.0
    assert view["stale"] is True
    assert view["fetched_at"] == first["fetched_at"]
