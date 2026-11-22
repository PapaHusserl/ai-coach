"""Погода в шапке пульта: место в памяти процесса, кэш ответа сервиса, вид по дню (П7, партия 2).

Координат и источника места в ответе нет: числа и коды, тексты собирает JS-модель.
"""

import sqlite3
import threading
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach import location, weather
from ai_coach.location import LocationError, Place
from ai_coach.weather import WeatherError
from ai_coach.workload.config import WorkloadConfigError, load_config

PLACE_TTL = timedelta(minutes=60)
CACHE_TTL = timedelta(minutes=15)
STALE_LIMIT = timedelta(hours=3)
DAYS = 7

_place_lock = threading.Lock()
_place: tuple[Place, datetime] | None = None
_cache_lock = threading.Lock()
_cache: tuple[Place, datetime, dict[str, Any]] | None = None


def current_place(now: datetime) -> Place:
    """Место из памяти (60 минут) или от macOS с запасом из конфига; отказ после удачи - прежнее
    место; места нет совсем - LocationError."""
    global _place
    with _place_lock:
        if _place is not None and now - _place[1] < PLACE_TTL:
            return _place[0]
        try:
            try:
                spare = load_config().weather
            except WorkloadConfigError:
                spare = None  # битый конфиг - запаса нет
            found = location.resolve_place(spare and Place(spare.lat, spare.lon))[0]
        except LocationError:
            if _place is None:
                raise
            found = _place[0]
        _place = (found, now)
        return found


def _forecast(place: Place, now: datetime) -> tuple[dict[str, Any], datetime, bool] | None:
    """Разобранный прогноз, время его получения, устарел ли; None - ответа нет и не было."""
    global _cache
    with _cache_lock:
        same_day = _cache is not None and _cache[1].date() == now.date()
        if _cache is not None and same_day and _cache[0] == place and now - _cache[1] < CACHE_TTL:
            return _cache[2], _cache[1], False
        try:
            fresh = weather.parse_forecast(weather.fetch_forecast(place))
        except WeatherError:
            if _cache is None or _cache[0] != place or now - _cache[1] >= STALE_LIMIT:
                return None
            return _cache[2], _cache[1], True
        _cache = (place, now, fresh)
        return fresh, now, False


def _day_answer(place: Place, day: date, offset: int, now: datetime) -> dict[str, Any]:
    """Ответ по дню из прогноза места; нет ответа сервиса или дня в данных - "silent"."""
    forecast = _forecast(place, now)
    if forecast is None:
        return {"missing": "silent"}
    data, fetched, stale = forecast
    days = {d["date"]: d for d in data["days"]}
    found = days.get(day.isoformat())
    tomorrow = days.get((day + timedelta(days=1)).isoformat())
    if found is None or (not offset and tomorrow is None):
        return {"missing": "silent"}
    meta = {"fetched_at": fetched.isoformat(timespec="seconds"), "stale": stale}
    if offset:
        return {"day": found} | meta
    return {"current": data["current"], "today": found, "tomorrow": tomorrow} | meta


def weather_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """GET /api/weather: сегодня - сейчас, сегодня, завтра; другой день до +6 - {"day"}; иначе
    {"missing": "range" | "place" | "silent"}. conn не используется, в базу не пишет."""
    offset = (day - now.date()).days
    if not 0 <= offset < DAYS:
        return {"missing": "range"}
    try:
        place = current_place(now)
    except LocationError as error:
        return {"missing": "place", "why": str(error)}
    return _day_answer(place, day, offset, now)
