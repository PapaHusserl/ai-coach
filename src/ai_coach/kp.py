"""Индекс Kp: чтение и разбор ответа NOAA SWPC (П7, партия 11, Р37 = 2).

Запрос без параметров: координаты в сервис не уходят. Ошибки - WeatherError из weather.py.
"""

import json
import urllib.request
from typing import Any, cast

from ai_coach.weather import WeatherError

KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
TIMEOUT = 5


def fetch_kp() -> Any:
    """Ответ сервиса как есть; сеть, таймаут, не JSON - WeatherError."""
    try:
        with urllib.request.urlopen(KP_URL, timeout=TIMEOUT) as response:
            return json.loads(response.read())
    except (OSError, ValueError) as e:
        raise WeatherError(f"NOAA SWPC не ответил: {e}") from None


def parse_kp(answer: Any) -> list[dict[str, Any]]:
    """Строки {"time", "kp", "kind"} в порядке ответа; не список, не словарь-строка, нет ключа,
    kp не число - WeatherError."""
    if not isinstance(answer, list):
        raise WeatherError("NOAA SWPC: ответ не список.")
    rows: list[dict[str, Any]] = []
    for item in cast(list[Any], answer):
        try:
            time, kp, kind = item["time_tag"], item["kp"], item["observed"]
        except (KeyError, TypeError):
            raise WeatherError("NOAA SWPC: в строке нет time_tag, kp или observed.") from None
        if isinstance(kp, bool) or not isinstance(kp, int | float):
            raise WeatherError("NOAA SWPC: kp не число.")
        if not isinstance(time, str) or not isinstance(kind, str):
            raise WeatherError("NOAA SWPC: time_tag или observed не строка.")
        rows.append({"time": time, "kp": kp, "kind": kind})
    return rows
