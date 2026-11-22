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


def parse_forecast(answer: Any) -> dict[str, Any]:
    """{"current": {...}, "days": [...], "utc_offset_seconds": int}; нет ключа, не тот тип или
    списки дня разной длины - WeatherError."""
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
        return {
            "current": {
                "time": now["time"],
                "temperature": now["temperature_2m"],
                "apparent": now["apparent_temperature"],
                "code": now["weather_code"],
                "wind": now["wind_speed_10m"],
                "pressure": now["pressure_msl"],
            },
            "days": [
                {"date": d, "code": c, "t_max": hi, "t_min": lo, "precip_prob": p}
                for d, c, hi, lo, p in zip(*columns, strict=True)
            ],
            "utc_offset_seconds": offset,
        }
    except (KeyError, TypeError) as e:
        raise WeatherError(f"Open-Meteo: ответ не разобрать ({e!r}).") from None
