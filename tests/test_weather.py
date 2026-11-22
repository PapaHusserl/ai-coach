import copy
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from ai_coach.location import Place
from ai_coach.weather import (
    WeatherError,
    fetch_forecast,  # настоящий читатель снят при импорте: conftest подменяет атрибут модуля
    forecast_url,
    parse_forecast,
    weather_word,
)

FIXTURE = Path(__file__).parent / "fixtures" / "weather" / "open_meteo.json"


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
