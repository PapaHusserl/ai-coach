import copy
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import ai_coach.weather as weather_module
from ai_coach.location import Place
from ai_coach.weather import (
    WeatherError,
    fetch_forecast,  # настоящий читатель снят при импорте: conftest подменяет атрибут модуля
    forecast_url,
    parse_forecast,
    weather_word,
)

FIXTURE = Path(__file__).parent / "fixtures" / "weather" / "open_meteo.json"
HOURLY = "temperature_2m,pressure_msl,surface_pressure,relative_humidity_2m,wind_speed_10m"


def answer() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def test_forecast_url_has_two_digit_coordinates() -> None:
    url = forecast_url(Place(52.52, 13.41))
    assert "latitude=52.52&longitude=13.41" in url


def test_forecast_url_has_no_third_digit() -> None:
    url = forecast_url(Place(52.52, 13.41))
    assert "52.520" not in url
    assert "13.410" not in url


def test_parse_forecast_current_has_five_numbers() -> None:
    current = parse_forecast(answer())["current"]
    assert current["temperature"] == 3.7
    assert current["apparent"] == 0.3
    assert current["code"] == 2
    assert current["wind"] == 3.09
    assert current["pressure"] == 1018.4


def test_parse_forecast_days_in_date_order() -> None:
    days = parse_forecast(answer())["days"]
    assert [d["date"] for d in days] == [f"2026-11-{n}" for n in range(22, 29)]


def test_parse_forecast_day_fields() -> None:
    today = parse_forecast(answer())["days"][0]
    assert (today["code"], today["t_max"], today["t_min"], today["precip_prob"]) == (
        80,
        5.6,
        1.9,
        88,
    )


def test_parse_forecast_utc_offset_is_int_from_root() -> None:
    offset = parse_forecast(answer())["utc_offset_seconds"]
    assert offset == 3600
    assert isinstance(offset, int)


@pytest.mark.parametrize("key", ["current", "daily", "utc_offset_seconds"])
def test_parse_forecast_missing_key_is_error(key: str) -> None:
    data = answer()
    del data[key]
    with pytest.raises(WeatherError):
        parse_forecast(data)


def test_parse_forecast_offset_not_int_is_error() -> None:
    data = answer()
    data["utc_offset_seconds"] = "3600"
    with pytest.raises(WeatherError):
        parse_forecast(data)


@pytest.mark.parametrize("bad", [[], "текст", None, 5])
def test_parse_forecast_not_a_dict_is_error(bad: Any) -> None:
    with pytest.raises(WeatherError):
        parse_forecast(bad)


@pytest.mark.parametrize("key", ["temperature_2m", "apparent_temperature", "wind_speed_10m"])
@pytest.mark.parametrize("bad", [None, "3.7"])
def test_parse_forecast_current_not_a_number_is_error(key: str, bad: Any) -> None:
    data = answer()
    data["current"][key] = bad
    with pytest.raises(WeatherError):
        parse_forecast(data)


@pytest.mark.parametrize("key", ["weather_code", "temperature_2m_max", "temperature_2m_min"])
@pytest.mark.parametrize("bad", [None, "5.6"])
def test_parse_forecast_day_not_a_number_is_error(key: str, bad: Any) -> None:
    data = answer()
    data["daily"][key][0] = bad
    with pytest.raises(WeatherError):
        parse_forecast(data)


def test_parse_forecast_lists_of_different_length_is_error() -> None:
    data = copy.deepcopy(answer())
    data["daily"]["temperature_2m_min"] = data["daily"]["temperature_2m_min"][:-1]
    with pytest.raises(WeatherError):
        parse_forecast(data)


def test_fetch_forecast_returns_parsed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    body = FIXTURE.read_bytes()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(body))
    assert fetch_forecast(Place(52.52, 13.41)) == answer()


def test_fetch_forecast_url_error_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("нет сети")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError):
        fetch_forecast(Place(52.52, 13.41))


def test_fetch_forecast_timeout_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise TimeoutError

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError):
        fetch_forecast(Place(52.52, 13.41))


def test_fetch_forecast_http_500_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.HTTPError("http://x", 500, "Server Error", None, None)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError):
        fetch_forecast(Place(52.52, 13.41))


def test_fetch_forecast_not_json_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"<html>"))
    with pytest.raises(WeatherError):
        fetch_forecast(Place(52.52, 13.41))


@pytest.mark.parametrize(
    ("code", "word"),
    [(0, "ясно"), (2, "переменная облачность"), (80, "ливень"), (3, "пасмурно")],
)
def test_weather_word(code: int, word: str) -> None:
    assert weather_word(code) == word


def test_weather_word_unknown_code_is_none() -> None:
    assert weather_word(1234) is None


def test_forecast_url_query_is_exact() -> None:
    import urllib.parse

    from ai_coach.weather import CURRENT, DAILY

    url = forecast_url(Place(52.52, 13.41))
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    assert query == {
        "latitude": "52.52",
        "longitude": "13.41",
        "current": CURRENT,
        "daily": DAILY,
        "wind_speed_unit": "ms",
        "timezone": "auto",
        "forecast_days": "7",
        "past_days": "1",
        "hourly": HOURLY,
    }


def test_forecast_url_keeps_commas_unescaped() -> None:
    assert "%2C" not in forecast_url(Place(52.52, 13.41))


def test_fetch_forecast_passes_url_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake(*args: Any, **kwargs: Any) -> FakeResponse:
        seen.append((args, kwargs))
        return FakeResponse(FIXTURE.read_bytes())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    place = Place(52.52, 13.41)
    fetch_forecast(place)
    assert seen == [((forecast_url(place),), {"timeout": 5})]


def test_fetch_forecast_error_message_has_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("нет сети")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError, match=r"^Open-Meteo не ответил: .*нет сети"):
        fetch_forecast(Place(52.52, 13.41))


def test_parse_forecast_offset_error_message() -> None:
    data = answer()
    data["utc_offset_seconds"] = "3600"
    with pytest.raises(WeatherError, match=r"^Open-Meteo: utc_offset_seconds не целое\.$"):
        parse_forecast(data)


def test_parse_forecast_lengths_error_message() -> None:
    data = answer()
    data["daily"]["temperature_2m_min"] = data["daily"]["temperature_2m_min"][:-1]
    with pytest.raises(WeatherError, match=r"^Open-Meteo: списки дней разной длины\.$"):
        parse_forecast(data)


def test_parse_forecast_not_number_error_message() -> None:
    data = answer()
    data["current"]["temperature_2m"] = None
    with pytest.raises(WeatherError, match=r"^Open-Meteo: в ответе не число\.$"):
        parse_forecast(data)


def test_parse_forecast_missing_key_error_message() -> None:
    data = answer()
    del data["daily"]
    with pytest.raises(
        WeatherError, match=r"^Open-Meteo: ответ не разобрать \(KeyError\('daily'\)\)\.$"
    ):
        parse_forecast(data)


def test_forecast_url_hourly_is_five_series_in_one_string() -> None:
    assert f"hourly={HOURLY}&" in forecast_url(Place(52.52, 13.41)) + "&"


def test_forecast_url_asks_one_past_day() -> None:
    assert "past_days=1" in forecast_url(Place(52.52, 13.41))


def test_parse_hourly_gives_192_hours_in_time_order() -> None:
    from ai_coach.weather import parse_hourly

    hours = parse_hourly(answer())
    assert len(hours) == 192
    assert hours[0]["time"] == "2026-11-21T00:00"
    assert hours[-1]["time"] == "2026-11-28T23:00"


def test_parse_hourly_hour_has_six_values() -> None:
    from ai_coach.weather import parse_hourly

    hour = parse_hourly(answer())[10]
    assert hour == {
        "time": "2026-11-21T10:00",
        "temperature": 2.8,
        "pressure": 1019.0,
        "pressure_surface": 1009.0,
        "humidity": 80,
        "wind": 2.9,
    }


def test_parse_hourly_pressure_is_sea_level_and_surface_is_not() -> None:
    from ai_coach.weather import parse_hourly

    data = answer()
    data["hourly"]["pressure_msl"][0] = 1111.0
    data["hourly"]["surface_pressure"][0] = 999.0
    hour = parse_hourly(data)[0]
    assert (hour["pressure"], hour["pressure_surface"]) == (1111.0, 999.0)


@pytest.mark.parametrize(
    ("series", "key"),
    [
        ("pressure_msl", "pressure"),
        ("surface_pressure", "pressure_surface"),
        ("relative_humidity_2m", "humidity"),
        ("wind_speed_10m", "wind"),
    ],
)
def test_parse_hourly_null_stays_none_and_other_values_stay(series: str, key: str) -> None:
    from ai_coach.weather import parse_hourly

    data = answer()
    data["hourly"][series][10] = None
    hour = parse_hourly(data)[10]
    assert hour[key] is None
    assert hour["time"] == "2026-11-21T10:00"
    assert hour["temperature"] == 2.8


def test_parse_hourly_without_hourly_is_error() -> None:
    from ai_coach.weather import parse_hourly

    data = answer()
    del data["hourly"]
    with pytest.raises(WeatherError):
        parse_hourly(data)


def test_parse_forecast_without_hourly_parses_as_before() -> None:
    data = answer()
    del data["hourly"]
    assert set(parse_forecast(data)) == {"current", "days", "utc_offset_seconds"}


def test_parse_hourly_null_temperature_is_error() -> None:
    from ai_coach.weather import parse_hourly

    data = answer()
    data["hourly"]["temperature_2m"][10] = None
    with pytest.raises(WeatherError):
        parse_hourly(data)


def test_parse_hourly_string_in_pressure_is_error() -> None:
    from ai_coach.weather import parse_hourly

    data = answer()
    data["hourly"]["pressure_msl"][10] = "1019.0"
    with pytest.raises(WeatherError):
        parse_hourly(data)


def test_parse_hourly_missing_series_is_error() -> None:
    from ai_coach.weather import parse_hourly

    data = answer()
    del data["hourly"]["wind_speed_10m"]
    with pytest.raises(WeatherError):
        parse_hourly(data)


def test_parse_hourly_series_shorter_than_time_is_error() -> None:
    from ai_coach.weather import parse_hourly

    data = answer()
    data["hourly"]["pressure_msl"] = data["hourly"]["pressure_msl"][:-1]
    with pytest.raises(WeatherError):
        parse_hourly(data)


ARCHIVE_FIXTURE = Path(__file__).parent / "fixtures" / "weather" / "archive.json"
START, END = "2026-10-07", "2026-11-21"
# Настоящий читатель снят при импорте файла: conftest подменяет атрибут модуля в каждом тесте.
REAL_FETCH_ARCHIVE: Any = weather_module.fetch_archive


def archive_query(place: Place | None = None) -> dict[str, str]:
    from ai_coach.weather import archive_url

    place = place or Place(52.52, 13.41)
    url = archive_url(place, START, END)
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


def test_archive_url_is_the_archive_address() -> None:
    from ai_coach.weather import archive_url

    url = archive_url(Place(52.52, 13.41), START, END)
    assert url.startswith("https://archive-api.open-meteo.com/v1/archive?")


def test_archive_url_has_two_digit_coordinates() -> None:
    from ai_coach.weather import archive_url

    url = archive_url(Place(52.52, 13.41), START, END)
    assert "latitude=52.52&longitude=13.41" in url
    assert "52.520" not in url
    assert "13.410" not in url


def test_archive_url_rounds_a_precise_place_to_two_digits() -> None:
    query = archive_query(Place(52.5234, 13.4114))
    assert (query["latitude"], query["longitude"]) == ("52.52", "13.41")


def test_archive_url_has_the_period() -> None:
    query = archive_query()
    assert (query["start_date"], query["end_date"]) == (START, END)


def test_archive_url_has_the_same_hourly_set_as_forecast() -> None:
    assert archive_query()["hourly"] == HOURLY


def test_archive_url_has_local_time_and_wind_in_ms_like_forecast() -> None:
    query = archive_query()
    assert (query["timezone"], query["wind_speed_unit"]) == ("auto", "ms")


def test_fetch_archive_returns_parsed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    body = ARCHIVE_FIXTURE.read_bytes()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(body))
    result = REAL_FETCH_ARCHIVE(Place(52.52, 13.41), START, END)
    assert result == json.loads(body)


def test_fetch_archive_passes_archive_url_and_same_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_coach.weather import archive_url

    seen: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake(*args: Any, **kwargs: Any) -> FakeResponse:
        seen.append((args, kwargs))
        return FakeResponse(ARCHIVE_FIXTURE.read_bytes())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    place = Place(52.52, 13.41)
    REAL_FETCH_ARCHIVE(place, START, END)
    assert seen == [((archive_url(place, START, END),), {"timeout": 5})]


def test_fetch_archive_url_error_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("нет сети")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError):
        REAL_FETCH_ARCHIVE(Place(52.52, 13.41), START, END)


def test_fetch_archive_not_json_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"<html>"))
    with pytest.raises(WeatherError):
        REAL_FETCH_ARCHIVE(Place(52.52, 13.41), START, END)


def test_parse_hourly_reads_the_archive_answer() -> None:
    from ai_coach.weather import parse_hourly

    hours = parse_hourly(json.loads(ARCHIVE_FIXTURE.read_text(encoding="utf-8")))
    assert len(hours) == 46 * 24
    assert hours[0]["time"] == "2026-10-07T00:00"
    assert hours[-1]["time"] == "2026-11-21T23:00"
