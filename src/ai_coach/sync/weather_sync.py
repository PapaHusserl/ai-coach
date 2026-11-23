"""Синхронизация погоды -> база: место, сервис, три таблицы и sync_log kind='weather'.

Место и сервис читаются до записи; три таблицы и строка sync_log пишутся одной транзакцией.
Сбой не бросает исключение: строка итога и status='error'. kind='weather', а не 'sync':
иначе ломается first_run_today.

После удачной записи backfill_weather («тихое назад») дозагружает из архива дни от первой
отметки самочувствия до вчера, которых нет в weather_hours, по месту этого же синка; своя
транзакция и строка kind='weather_archive'; сбой архива основную запись не откатывает.
"""

import math
import sqlite3
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach import kp, location, weather
from ai_coach.load.weather_signal import weather_report
from ai_coach.location import LocationError, Place
from ai_coach.store.journal import add_sync_log, first_wellbeing_day
from ai_coach.store.weather import (
    add_weather_now,
    add_weather_signal,
    days_with_hours,
    upsert_kp,
    upsert_weather_day,
    upsert_weather_hours,
)
from ai_coach.weather import WeatherError
from ai_coach.workload.config import WorkloadConfigError, load_config

KIND = "weather"
ARCHIVE_KIND = "weather_archive"
KP_KIND = "kp"
NO_ACCESS = ("denied", "off")


def degrees(value: float) -> str:
    """Градусы целым со знаком, как на пульте (половина вверх): +4°, −3°, 0°."""
    whole = math.floor(value + 0.5)
    if whole == 0:
        return "0°"
    return f"{'+' if whole > 0 else '−'}{abs(whole)}°"


def _log(
    conn: sqlite3.Connection, started: str, message: str, status: str, kind: str = KIND
) -> None:
    add_sync_log(
        conn,
        {
            "started_at": started,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "kind": kind,
            "status": status,
            "message": message,
        },
    )


def _fail(conn: sqlite3.Connection, started: str, message: str) -> str:
    with conn:
        _log(conn, started, message, "error")
    return message


def missing_days(have: set[str], first: str | None, last: str) -> list[str]:
    """Даты first..last (ISO) по возрастанию, которых нет в have; first нет или позже last - []."""
    if first is None or first > last:
        return []
    day, end = date.fromisoformat(first), date.fromisoformat(last)
    days = [day + timedelta(days=i) for i in range((end - day).days + 1)]
    return [d.isoformat() for d in days if d.isoformat() not in have]


def _days_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "дня"
    return "дней"


def backfill_weather(
    conn: sqlite3.Connection,
    place: Place,
    source: str,
    now: datetime,
    fetch: Callable[[Place, str, str], dict[str, Any]] | None = None,
) -> str | None:
    """Дозагружает из архива дни от первой отметки самочувствия до вчера, которых нет в
    weather_hours; одним запросом на диапазон недостающих. Возвращает строку итога или None
    (недостающих дней нет). Сбой - строка «нет связи» и status='error', исключений наружу нет."""
    yesterday = (now.date() - timedelta(days=1)).isoformat()
    first = first_wellbeing_day(conn)
    missing = missing_days(days_with_hours(conn, first or yesterday, yesterday), first, yesterday)
    if not missing:
        return None
    started = now.isoformat(timespec="seconds")
    try:
        raw = (fetch or weather.fetch_archive)(place, missing[0], missing[-1])
        extra = {
            "fetched_at": started,
            "lat": place.lat,
            "lon": place.lon,
            "place_source": source,
            "source": "archive",
        }
        hours = weather.parse_hourly(raw)
        rows = [{**h, **extra} for h in hours if str(h["time"])[:10] in missing]
        if not rows:
            raise WeatherError("Open-Meteo: в ответе нет часов недостающих дней.")
    except WeatherError:
        message = "погода, архив: нет связи"
        with conn:
            _log(conn, started, message, "error", ARCHIVE_KIND)
        return message
    days = len({str(row["time"])[:10] for row in rows})
    message = f"погода, архив: дозагружено {days} {_days_word(days)}"
    with conn:
        upsert_weather_hours(conn, rows)
        _log(conn, started, message, "ok", ARCHIVE_KIND)
    return message


def _write_signals(conn: sqlite3.Connection, now: datetime) -> None:
    """Сработавшие сегодня сигналы по часам базы; первая запись дня и кода остаётся."""
    day = now.date()
    for signal in weather_report(conn, day.isoformat(), now)["signals"]:
        at_day = day + timedelta(days=1) if signal["next_day"] else day
        add_weather_signal(
            conn,
            {
                "date": day.isoformat(),
                "kind": signal["kind"],
                "value": signal["value"],
                "limit_value": signal["limit"],
                "extreme_at": f"{at_day.isoformat()}T{signal['at']}",
                "created_at": now.isoformat(timespec="seconds"),
            },
        )


def sync_kp(
    conn: sqlite3.Connection,
    now: datetime | None = None,
    fetch: Callable[[], Any] | None = None,
) -> None:
    """Записывает индекс Kp (NOAA SWPC) и строку sync_log kind='kp' одной транзакцией. От места и
    погоды не зависит; сбой - status='error', таблица не тронута; в вывод ничего не идёт."""
    now = now or datetime.now()
    started = now.isoformat(timespec="seconds")
    try:
        rows = kp.parse_kp((fetch or kp.fetch_kp)())
    except WeatherError as e:
        with conn:
            _log(conn, started, str(e), "error", KP_KIND)
        return
    with conn:
        upsert_kp(conn, [{**row, "fetched_at": started} for row in rows])
        _log(conn, started, f"Kp: записано {len(rows)}", "ok", KP_KIND)


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
        raw = (fetch or weather.fetch_forecast)(place)
        data = weather.parse_forecast(raw)
        hours = weather.parse_hourly(raw)
    except WeatherError:
        return _fail(conn, started, "погода: нет связи")
    current = data["current"]
    mark = " (место из конфига)" if source == "config" else ""
    message = f"погода: записана, {degrees(current['temperature'])}{mark}"
    spot = {"lat": place.lat, "lon": place.lon}
    hour_extra = {"fetched_at": started, **spot, "place_source": source, "source": "forecast"}
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
        upsert_weather_hours(conn, [{**hour, **hour_extra} for hour in hours])
        _write_signals(conn, now)
        _log(conn, started, message, "ok")
    archive = backfill_weather(conn, place, source, now)
    return message if archive is None else f"{message}\n{archive}"
