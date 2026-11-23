"""Синхронизация погоды -> база: место, сервис, обе таблицы и sync_log kind='weather'.

Место и сервис читаются до записи; обе таблицы и строка sync_log пишутся одной транзакцией.
Сбой не бросает исключение: строка итога и status='error'. kind='weather', а не 'sync':
иначе ломается first_run_today.
"""

import math
import sqlite3
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ai_coach import location, weather
from ai_coach.location import LocationError, Place
from ai_coach.store.journal import add_sync_log
from ai_coach.store.weather import add_weather_now, upsert_weather_day
from ai_coach.weather import WeatherError
from ai_coach.workload.config import WorkloadConfigError, load_config

KIND = "weather"
NO_ACCESS = ("denied", "off")


def degrees(value: float) -> str:
    """Градусы целым со знаком, как на пульте (половина вверх): +4°, −3°, 0°."""
    whole = math.floor(value + 0.5)
    if whole == 0:
        return "0°"
    return f"{'+' if whole > 0 else '−'}{abs(whole)}°"


def _log(conn: sqlite3.Connection, started: str, message: str, status: str) -> None:
    add_sync_log(
        conn,
        {
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "kind": KIND,
            "status": status,
            "message": message,
        },
    )


def _fail(conn: sqlite3.Connection, started: str, message: str) -> str:
    with conn:
        _log(conn, started, message, "error")
    return message


def sync_weather(
    conn: sqlite3.Connection,
    now: datetime | None = None,
    locate: Callable[[], Place] | None = None,
    fetch: Callable[[Place], dict[str, Any]] | None = None,
) -> str:
    """Записывает погоду места и возвращает строку итога (при сбое - его текст)."""
    now = now or datetime.now()
    started = now.isoformat(timespec="seconds")
    try:
        spare = load_config().weather
    except WorkloadConfigError:
        spare = None  # битый конфиг - запаса нет
    try:
        place, source = location.resolve_place(spare and Place(spare.lat, spare.lon), locate)
    except LocationError as e:
        reason = "нет доступа к геолокации" if e.args[0] in NO_ACCESS else "место не определено"
        return _fail(conn, started, f"погода: {reason}")
    try:
        data = weather.parse_forecast((fetch or weather.fetch_forecast)(place))
    except WeatherError:
        return _fail(conn, started, "погода: нет связи")
    current = data["current"]
    mark = " (место из конфига)" if source == "config" else ""
    message = f"погода: записана, {degrees(current['temperature'])}{mark}"
    spot = {"lat": place.lat, "lon": place.lon}
    with conn:
        add_weather_now(
            conn,
            {
                "observed_at": current["time"],
                "temperature": current["temperature"],
                "apparent": current["apparent"],
                "code": current["code"],
                "wind": current["wind"],
                "pressure": current["pressure"],
                "fetched_at": started,
                **spot,
                "place_source": source,
                "utc_offset_seconds": data["utc_offset_seconds"],
            },
        )
        for day in data["days"]:
            upsert_weather_day(conn, {**day, "fetched_at": started, **spot})
        _log(conn, started, message, "ok")
    return message
