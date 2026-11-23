"""Индекс Kp: разбор и чтение ответа NOAA SWPC (П7, партия 11, Р37 = 2)."""

import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import ai_coach.kp as kp_module
from ai_coach.kp import (
    KP_URL,
    fetch_kp,  # настоящий читатель снят при импорте: conftest подменяет атрибут модуля
    parse_kp,
)
from ai_coach.weather import WeatherError

FIXTURE = Path(__file__).parent / "fixtures" / "weather" / "kp.json"
REAL_FETCH_KP: Any = fetch_kp


def answer() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def test_parse_kp_gives_81_rows_with_three_keys() -> None:
    rows = parse_kp(answer())
    assert len(rows) == 81
    assert all(set(row) == {"time", "kp", "kind"} for row in rows)


def test_parse_kp_kinds_are_observed_estimated_predicted() -> None:
    kinds = [row["kind"] for row in parse_kp(answer())]
    assert (kinds.count("observed"), kinds.count("estimated"), kinds.count("predicted")) == (
        61,
        3,
        17,
    )


def test_parse_kp_first_row_keeps_time_tag_and_fraction() -> None:
    first = parse_kp(answer())[0]
    assert first == {"time": "2026-11-15T00:00:00", "kp": 0.67, "kind": "observed"}


def test_parse_kp_keeps_order_of_answer() -> None:
    times = [row["time"] for row in parse_kp(answer())]
    assert times == sorted(times)


def test_parse_kp_integer_kp_is_accepted() -> None:
    raw = [{"time_tag": "2026-11-22T15:00:00", "kp": 3, "observed": "observed"}]
    assert parse_kp(raw)[0]["kp"] == 3


@pytest.mark.parametrize("bad", [{}, "x", None, 5, {"time_tag": "2026-11-22T15:00:00"}])
def test_parse_kp_not_a_list_is_error(bad: Any) -> None:
    with pytest.raises(WeatherError):
        parse_kp(bad)


@pytest.mark.parametrize("key", ["time_tag", "kp", "observed"])
def test_parse_kp_row_without_key_is_error(key: str) -> None:
    raw = answer()
    del raw[5][key]
    with pytest.raises(WeatherError):
        parse_kp(raw)


@pytest.mark.parametrize("bad", [None, "2.0", "", [1], {"v": 1}, True])
def test_parse_kp_kp_not_a_number_is_error(bad: Any) -> None:
    raw = answer()
    raw[5]["kp"] = bad
    with pytest.raises(WeatherError):
        parse_kp(raw)


@pytest.mark.parametrize("key", ["time_tag", "observed"])
@pytest.mark.parametrize("bad", [None, 5, 1.5, ["x"], {"v": 1}, True])
def test_parse_kp_text_field_not_a_string_is_error(key: str, bad: Any) -> None:
    raw = answer()
    raw[5][key] = bad
    with pytest.raises(WeatherError):
        parse_kp(raw)


def test_parse_kp_row_not_a_dict_is_error() -> None:
    raw: list[Any] = answer()
    raw[3] = "строка"
    with pytest.raises(WeatherError):
        parse_kp(raw)


def test_parse_kp_not_a_list_error_text() -> None:
    with pytest.raises(WeatherError) as e:
        parse_kp({})
    assert str(e.value) == "NOAA SWPC: ответ не список."


def test_parse_kp_missing_key_error_text() -> None:
    raw = answer()
    del raw[5]["kp"]
    with pytest.raises(WeatherError) as e:
        parse_kp(raw)
    assert str(e.value) == "NOAA SWPC: в строке нет time_tag, kp или observed."


def test_parse_kp_kp_not_a_number_error_text() -> None:
    raw = answer()
    raw[5]["kp"] = "2.0"
    with pytest.raises(WeatherError) as e:
        parse_kp(raw)
    assert str(e.value) == "NOAA SWPC: kp не число."


def test_parse_kp_text_field_error_text() -> None:
    raw = answer()
    raw[5]["observed"] = None
    with pytest.raises(WeatherError) as e:
        parse_kp(raw)
    assert str(e.value) == "NOAA SWPC: time_tag или observed не строка."


def test_fetch_kp_error_text_has_service_and_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("нет сети")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError) as e:
        REAL_FETCH_KP()
    assert str(e.value).startswith("NOAA SWPC не ответил: ")
    assert "нет сети" in str(e.value)


def test_kp_url_has_no_parameters() -> None:
    assert "?" not in KP_URL
    assert "latitude" not in KP_URL
    assert "longitude" not in KP_URL


def test_fetch_kp_returns_parsed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    body = FIXTURE.read_bytes()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(body))
    assert REAL_FETCH_KP() == answer()


def test_fetch_kp_asks_url_without_parameters_with_timeout_5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[Any, Any]] = []

    def fake(url: Any, *args: object, **kwargs: Any) -> FakeResponse:
        seen.append((url, kwargs.get("timeout", args[1] if len(args) > 1 else None)))
        return FakeResponse(b"[]")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    REAL_FETCH_KP()
    [(url, timeout)] = seen
    assert url == KP_URL
    assert timeout == 5


def test_fetch_kp_url_error_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("нет сети")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError):
        REAL_FETCH_KP()


def test_fetch_kp_timeout_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise TimeoutError

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError):
        REAL_FETCH_KP()


def test_fetch_kp_http_500_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.HTTPError("http://x", 500, "Server Error", None, None)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(WeatherError):
        REAL_FETCH_KP()


def test_fetch_kp_not_json_is_weather_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"<html>"))
    with pytest.raises(WeatherError):
        REAL_FETCH_KP()


def test_conftest_makes_default_fetch_kp_refuse() -> None:
    with pytest.raises(WeatherError):
        kp_module.fetch_kp()
