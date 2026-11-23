"""Погода из Open-Meteo: адрес, запрос, разбор ответа и слова по коду WMO.

Координаты в адрес уходят округлёнными до 2 знаков (`Place` уже округлён). Ответ сервиса -
`timezone=auto`: время и даты местные, смещение пояса - `utc_offset_seconds` в корне.
"""

import json
import urllib.parse
import urllib.request
from typing import Any, cast

from ai_coach.location import Place

URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 5
CURRENT = "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,pressure_msl"
DAILY = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
HOURLY = "temperature_2m,pressure_msl,surface_pressure,relative_humidity_2m,wind_speed_10m"

# Слова по коду WMO; та же таблица в web/static/weather-model.js (сверяет тест).
WORDS = {
    0: "ясно",
    1: "малооблачно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "туман",
    51: "морось",
    53: "морось",
    55: "морось",
    56: "ледяная морось",
    57: "ледяная морось",
    61: "дождь",
    63: "дождь",
    65: "дождь",
    66: "ледяной дождь",
    67: "ледяной дождь",
    71: "снег",
    73: "снег",
    75: "снег",
    77: "снежная крупа",
    80: "ливень",
    81: "ливень",
    82: "ливень",
    85: "снегопад",
    86: "снегопад",
    95: "гроза",
    96: "гроза с градом",
    99: "гроза с градом",
}


class WeatherError(Exception):
    """Сервис погоды не ответил или ответ не разобрать."""


def weather_word(code: int) -> str | None:
    """Слово по коду WMO; кода нет в таблице - None."""
    return WORDS.get(code)


def forecast_url(place: Place) -> str:
    query = urllib.parse.urlencode(
        {
            "latitude": f"{place.lat:.2f}",
            "longitude": f"{place.lon:.2f}",
            "current": CURRENT,
            "daily": DAILY,
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "forecast_days": 7,
            "past_days": 1,
            "hourly": HOURLY,
        },
        safe=",",
    )
    return f"{URL}?{query}"


def fetch_forecast(place: Place) -> dict[str, Any]:
    """Ответ сервиса как есть; сеть, таймаут, не JSON - WeatherError."""
    try:
        with urllib.request.urlopen(forecast_url(place), timeout=TIMEOUT) as response:
            return json.loads(response.read())
    except (OSError, ValueError) as e:
        raise WeatherError(f"Open-Meteo не ответил: {e}") from None


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def parse_forecast(answer: Any) -> dict[str, Any]:
    """{"current": {...}, "days": [...], "utc_offset_seconds": int}; нет ключа, не тот тип, не
    число в current или в code/t_max/t_min дня или списки дня разной длины - WeatherError."""
    try:
        data = cast(dict[str, Any], answer)
        offset = data["utc_offset_seconds"]
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise WeatherError("Open-Meteo: utc_offset_seconds не целое.")
        now = data["current"]
        daily = data["daily"]
        keys = (
            "time",
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
        )
        columns = [daily[key] for key in keys]
        if len({len(column) for column in columns}) != 1:
            raise WeatherError("Open-Meteo: списки дней разной длины.")
        current: dict[str, Any] = {
            "time": now["time"],
            "temperature": now["temperature_2m"],
            "apparent": now["apparent_temperature"],
            "code": now["weather_code"],
            "wind": now["wind_speed_10m"],
            "pressure": now["pressure_msl"],
        }
        days: list[dict[str, Any]] = [
            {"date": d, "code": c, "t_max": hi, "t_min": lo, "precip_prob": p}
            for d, c, hi, lo, p in zip(*columns, strict=True)
        ]
        numbers: list[Any] = [v for k, v in current.items() if k != "time"]
        for day in days:
            numbers += [day["code"], day["t_max"], day["t_min"]]
        if not all(_is_number(v) for v in numbers):
            raise WeatherError("Open-Meteo: в ответе не число.")
        return {"current": current, "days": days, "utc_offset_seconds": offset}
    except (KeyError, TypeError) as e:
        raise WeatherError(f"Open-Meteo: ответ не разобрать ({e!r}).") from None


# Ряд сервиса -> ключ часа; температура обязательна, остальные могут быть null.
HOUR_SERIES = {
    "temperature_2m": "temperature",
    "pressure_msl": "pressure",
    "surface_pressure": "pressure_surface",
    "relative_humidity_2m": "humidity",
    "wind_speed_10m": "wind",
}


def parse_hourly(answer: Any) -> list[dict[str, Any]]:
    """Часы из блока hourly (прогноз и архив): список {"time", "temperature", "pressure",
    "pressure_surface", "humidity", "wind"}. Нет блока или ряда, ряды разной длины, время не
    строка, температура не число, в остальных рядах не число и не null - WeatherError."""
    try:
        hourly = answer["hourly"]
        times = hourly["time"]
        columns = [hourly[name] for name in HOUR_SERIES]
        if any(len(column) != len(times) for column in columns):
            raise WeatherError("Open-Meteo: ряды часов разной длины.")
        hours = [
            {"time": t, **dict(zip(HOUR_SERIES.values(), values, strict=True))}
            for t, *values in zip(times, *columns, strict=True)
        ]
    except (KeyError, TypeError) as e:
        raise WeatherError(f"Open-Meteo: ответ не разобрать ({e!r}).") from None
    for hour in hours:
        rest = [v for k, v in hour.items() if k not in ("time", "temperature")]
        if not isinstance(hour["time"], str) or not _is_number(hour["temperature"]):
            raise WeatherError("Open-Meteo: час без времени или температуры.")
        if not all(v is None or _is_number(v) for v in rest):
            raise WeatherError("Open-Meteo: в ответе не число.")
    return hours
