"""ai_coach.load.weather_signal (П7, партия 8; «Решения» п. 43, 48, 51, 54).

Контракт, принятый тестами (план оставил форму на усмотрение кабана, «Файлы прогноза»):
- hours - строки как у list_weather_hours (time «YYYY-MM-DDTHH:MM», temperature, pressure,
  pressure_surface), по возрастанию; now - datetime.
- pressure_ahead(hours, now) -> (value, at) | None; value - падение (текущий час минус минимум
  окна, может быть <= 0), at - datetime часа минимума.
- temperature_ahead(hours, now) -> ((rise, at), (fall, at)) | None; at - datetime часа экстремума.
- find_weather_signals(hours, now, limits), limits - словарь {"pressure": число | None,
  "temperature": число | None}; None - кода нет.
- Пороги модуля - константы PRESSURE_LIMIT и TEMPERATURE_LIMIT
  (давление 4 гПа, температура 10 °C, «Решения» п. 75-77).
- weather_report(conn, day, now): day - строка «YYYY-MM-DD».
"""

import sqlite3
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

START = datetime(2026, 11, 22, 0, 0)
NOW = datetime(2026, 11, 22, 7, 20)
FMT = "%Y-%m-%dT%H:%M"
LIMITS = {"pressure": 5, "temperature": 7}

Level = Callable[[datetime], float | None]


def level(base: float | None, points: Mapping[str, float | None] | None = None) -> Level:
    """Ряд: base везде, кроме часов из points (ключ «YYYY-MM-DDTHH:MM»)."""
    marks = points or {}
    return lambda t: marks.get(t.strftime(FMT), base)


def series(
    pressure: Level | None = None,
    temperature: Level | None = None,
    count: int = 72,
    start: datetime = START,
) -> list[dict[str, Any]]:
    pressure = pressure or level(1015.0)
    temperature = temperature or level(4.0)
    rows = []
    for i in range(count):
        t = start + timedelta(hours=i)
        rows.append(
            {
                "time": t.strftime(FMT),
                "temperature": temperature(t),
                "pressure": pressure(t),
                "pressure_surface": 1000.0,
            }
        )
    return rows


def test_pressure_drop_to_evening_minimum_with_its_hour() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    hours = series(pressure=level(1015.0, {"2026-11-22T19:00": 1008.0}))
    assert pressure_ahead(hours, NOW) == (pytest.approx(7.0), datetime(2026, 11, 22, 19, 0))


def test_current_hour_is_start_of_hour_not_nearest() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    points = {"2026-11-22T08:00": 1000.0}
    result = pressure_ahead(series(pressure=level(1015.0, points)), datetime(2026, 11, 22, 7, 50))
    assert result == (pytest.approx(15.0), datetime(2026, 11, 22, 8, 0))


def test_minimum_on_24th_hour_counts() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    hours = series(pressure=level(1015.0, {"2026-11-23T07:00": 1008.0}))
    assert pressure_ahead(hours, NOW) == (pytest.approx(7.0), datetime(2026, 11, 23, 7, 0))


def test_minimum_on_25th_hour_does_not_count() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    points = {"2026-11-23T08:00": 1008.0, "2026-11-22T19:00": 1012.0}
    result = pressure_ahead(series(pressure=level(1015.0, points)), NOW)
    assert result == (pytest.approx(3.0), datetime(2026, 11, 22, 19, 0))


def test_first_of_equal_minimums_gives_the_hour() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    points = {"2026-11-22T19:00": 1008.0, "2026-11-22T22:00": 1008.0}
    result = pressure_ahead(series(pressure=level(1015.0, points)), NOW)
    assert result is not None
    assert result[1] == datetime(2026, 11, 22, 19, 0)


def test_minimum_tomorrow_night_gives_tomorrows_date() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    result = pressure_ahead(series(pressure=level(1015.0, {"2026-11-23T03:00": 1008.0})), NOW)
    assert result == (pytest.approx(7.0), datetime(2026, 11, 23, 3, 0))


def test_flat_pressure_is_not_a_drop() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    result = pressure_ahead(series(), NOW)
    assert result is not None
    assert result[0] <= 0


def test_fall_already_behind_is_not_counted() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    points = {"2026-11-22T05:00": 1000.0, "2026-11-22T06:00": 1005.0, "2026-11-22T07:00": 1010.0}
    result = pressure_ahead(series(pressure=level(1020.0, points)), NOW)
    assert result is not None
    assert result[0] <= 0


def test_pressure_rise_is_not_a_drop() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    result = pressure_ahead(series(pressure=level(1015.0, {"2026-11-22T19:00": 1022.0})), NOW)
    assert result is not None
    assert result[0] <= 0


def test_pressure_none_without_current_hour() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    hours = series(start=datetime(2026, 11, 22, 8, 0))
    assert pressure_ahead(hours, NOW) is None


def test_pressure_none_when_current_hour_pressure_is_null() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    hours = series(pressure=level(1015.0, {"2026-11-22T07:00": None, "2026-11-22T19:00": 1008.0}))
    assert pressure_ahead(hours, NOW) is None


def test_pressure_none_when_less_than_24_hours_ahead() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    hours = series(pressure=level(1015.0, {"2026-11-22T19:00": 1008.0}), count=31)
    assert pressure_ahead(hours, NOW) is None


def test_pressure_exactly_24_hours_ahead_is_enough() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    hours = series(pressure=level(1015.0, {"2026-11-22T19:00": 1008.0}), count=32)
    assert pressure_ahead(hours, NOW) is not None


def test_pressure_none_for_empty_series() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    assert pressure_ahead([], NOW) is None


def test_null_pressure_inside_window_is_skipped() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    points = {"2026-11-22T19:00": None, "2026-11-22T22:00": 1010.0}
    result = pressure_ahead(series(pressure=level(1015.0, points)), NOW)
    assert result == (pytest.approx(5.0), datetime(2026, 11, 22, 22, 0))


def test_pressure_is_counted_by_sea_level_column() -> None:
    from ai_coach.load.weather_signal import pressure_ahead

    hours = series(pressure=level(1015.0, {"2026-11-22T19:00": 1008.0}))
    assert all(h["pressure_surface"] == 1000.0 for h in hours)
    result = pressure_ahead(hours, NOW)
    assert result is not None
    assert result[0] == pytest.approx(7.0)


def test_temperature_rise_and_fall_with_hours() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    points = {"2026-11-22T15:00": 12.0, "2026-11-23T05:00": 3.0}
    result = temperature_ahead(series(temperature=level(4.0, points)), NOW)
    assert result == (
        (pytest.approx(8.0), datetime(2026, 11, 22, 15, 0)),
        (pytest.approx(1.0), datetime(2026, 11, 23, 5, 0)),
    )


def test_daily_warming_counts_as_rise_though_next_morning_is_same() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    points = {"2026-11-22T15:00": 12.0, "2026-11-23T07:00": 4.5}
    result = temperature_ahead(series(temperature=level(4.0, points)), NOW)
    assert result is not None
    assert result[0] == (pytest.approx(8.0), datetime(2026, 11, 22, 15, 0))


def test_cooling_gives_fall_and_no_rise() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    points = {"2026-11-22T07:00": 4.0, "2026-11-23T06:00": -4.0}
    result = temperature_ahead(series(temperature=level(0.0, points)), NOW)
    assert result is not None
    rise, fall = result
    assert fall == (pytest.approx(8.0), datetime(2026, 11, 23, 6, 0))
    assert rise[0] <= 0


def test_temperature_none_without_current_hour() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    assert temperature_ahead(series(start=datetime(2026, 11, 22, 8, 0)), NOW) is None


def test_temperature_none_when_current_hour_is_null() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    hours = series(temperature=level(4.0, {"2026-11-22T07:00": None, "2026-11-22T15:00": 12.0}))
    assert temperature_ahead(hours, NOW) is None


def test_temperature_none_when_less_than_24_hours_ahead() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    hours = series(temperature=level(4.0, {"2026-11-22T15:00": 12.0}), count=31)
    assert temperature_ahead(hours, NOW) is None


def test_temperature_none_for_empty_series() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    assert temperature_ahead([], NOW) is None


def test_null_temperature_inside_window_is_not_a_maximum() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    points = {"2026-11-22T15:00": None, "2026-11-22T16:00": 10.0}
    result = temperature_ahead(series(temperature=level(4.0, points)), NOW)
    assert result is not None
    assert result[0] == (pytest.approx(6.0), datetime(2026, 11, 22, 16, 0))


def test_null_temperature_inside_window_is_not_a_minimum() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    points = {"2026-11-23T05:00": None, "2026-11-23T06:00": 2.0}
    result = temperature_ahead(series(temperature=level(4.0, points)), NOW)
    assert result is not None
    assert result[1] == (pytest.approx(2.0), datetime(2026, 11, 23, 6, 0))


def test_temperature_maximum_on_24th_hour_counts() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    result = temperature_ahead(series(temperature=level(4.0, {"2026-11-23T07:00": 12.0})), NOW)
    assert result is not None
    assert result[0] == (pytest.approx(8.0), datetime(2026, 11, 23, 7, 0))


def test_temperature_maximum_on_25th_hour_does_not_count() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    points = {"2026-11-23T08:00": 12.0, "2026-11-22T19:00": 6.0}
    result = temperature_ahead(series(temperature=level(4.0, points)), NOW)
    assert result is not None
    assert result[0] == (pytest.approx(2.0), datetime(2026, 11, 22, 19, 0))


def test_equal_temperature_maximums_give_the_first_hour() -> None:
    from ai_coach.load.weather_signal import temperature_ahead

    points = {"2026-11-22T14:00": 12.0, "2026-11-22T15:00": 12.0}
    result = temperature_ahead(series(temperature=level(4.0, points)), NOW)
    assert result is not None
    assert result[0][1] == datetime(2026, 11, 22, 14, 0)


def test_pressure_drop_equal_to_limit_is_no_signal() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1015.0, {"2026-11-22T19:00": 1010.0}))
    assert find_weather_signals(hours, NOW, LIMITS) == []


def test_pressure_drop_above_limit_is_a_row() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1015.1, {"2026-11-22T19:00": 1010.0}))
    assert find_weather_signals(hours, NOW, LIMITS) == [
        {"kind": "pressure_drop", "value": 5.1, "limit": 5, "at": "19:00", "next_day": False}
    ]


def test_minimum_after_midnight_is_next_day() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1015.0, {"2026-11-23T03:00": 1008.0}))
    [row] = find_weather_signals(hours, NOW, LIMITS)
    assert (row["at"], row["next_day"]) == ("03:00", True)


def test_next_day_is_by_the_date_of_now_late_evening() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1015.0, {"2026-11-23T00:00": 1008.0}))
    [row] = find_weather_signals(hours, datetime(2026, 11, 22, 23, 20), LIMITS)
    assert (row["at"], row["next_day"]) == ("00:00", True)


def test_next_day_is_by_the_date_of_now_after_midnight() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1015.0, {"2026-11-22T23:00": 1008.0}))
    [row] = find_weather_signals(hours, datetime(2026, 11, 22, 0, 20), LIMITS)
    assert (row["at"], row["next_day"]) == ("23:00", False)


def test_pressure_rise_is_no_signal() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1015.0, {"2026-11-22T19:00": 1022.0}))
    assert find_weather_signals(hours, NOW, LIMITS) == []


def test_temperature_rise_above_limit_is_a_row() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(temperature=level(4.0, {"2026-11-22T15:00": 12.0}))
    assert find_weather_signals(hours, NOW, LIMITS) == [
        {"kind": "temperature_rise", "value": 8.0, "limit": 7, "at": "15:00", "next_day": False}
    ]


def test_temperature_fall_above_limit_is_temperature_drop() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(temperature=level(4.0, {"2026-11-23T06:00": -4.0}))
    [row] = find_weather_signals(hours, NOW, LIMITS)
    assert (row["kind"], row["value"], row["next_day"]) == ("temperature_drop", 8.0, True)


@pytest.mark.parametrize("point", [11.0, -3.0])
def test_temperature_change_equal_to_limit_is_no_signal(point: float) -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(temperature=level(4.0, {"2026-11-22T15:00": point}))
    assert find_weather_signals(hours, NOW, LIMITS) == []


def test_pressure_and_temperature_give_two_rows_pressure_first() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(
        pressure=level(1015.0, {"2026-11-22T19:00": 1008.0}),
        temperature=level(4.0, {"2026-11-22T15:00": 12.0}),
    )
    rows = find_weather_signals(hours, NOW, LIMITS)
    assert [r["kind"] for r in rows] == ["pressure_drop", "temperature_rise"]


def test_both_calculations_none_give_no_rows() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(count=10)
    assert find_weather_signals(hours, NOW, LIMITS) == []


def test_empty_series_gives_no_rows() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    assert find_weather_signals([], NOW, LIMITS) == []


def test_rise_and_fall_both_above_limit_give_one_row_with_bigger_value() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    points = {"2026-11-22T14:00": 12.0, "2026-11-23T06:00": -5.0}
    rows = find_weather_signals(series(temperature=level(4.0, points)), NOW, LIMITS)
    assert [(r["kind"], r["value"]) for r in rows] == [("temperature_drop", 9.0)]


def test_equal_rise_and_fall_give_the_earlier_hour_rise() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    points = {"2026-11-22T14:00": 12.0, "2026-11-23T06:00": -4.0}
    rows = find_weather_signals(series(temperature=level(4.0, points)), NOW, LIMITS)
    assert [(r["kind"], r["at"]) for r in rows] == [("temperature_rise", "14:00")]


def test_equal_rise_and_fall_give_the_earlier_hour_fall() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    points = {"2026-11-22T12:00": -4.0, "2026-11-22T15:00": 12.0}
    rows = find_weather_signals(series(temperature=level(4.0, points)), NOW, LIMITS)
    assert [(r["kind"], r["at"]) for r in rows] == [("temperature_drop", "12:00")]


def big_swings() -> list[dict[str, Any]]:
    return series(
        pressure=level(1015.0, {"2026-11-22T19:00": 1000.0}),
        temperature=level(4.0, {"2026-11-22T15:00": 20.0}),
    )


def test_unset_limits_give_no_rows() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    assert find_weather_signals(big_swings(), NOW, {"pressure": None, "temperature": None}) == []


def test_only_pressure_limit_set_gives_only_pressure() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    rows = find_weather_signals(big_swings(), NOW, {"pressure": 5, "temperature": None})
    assert [r["kind"] for r in rows] == ["pressure_drop"]


def test_only_temperature_limit_set_gives_only_temperature() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    rows = find_weather_signals(big_swings(), NOW, {"pressure": None, "temperature": 7})
    assert [r["kind"] for r in rows] == ["temperature_rise"]


def put_hours(conn: sqlite3.Connection, hours: list[dict[str, Any]]) -> None:
    for h in hours:
        conn.execute(
            "INSERT INTO weather_hours (time, temperature, pressure, pressure_surface, humidity, "
            "wind, fetched_at, lat, lon, place_source, source) "
            "VALUES (?, ?, ?, ?, 80, 3.0, '2026-11-22T07:10:00', 52.52, 13.41, 'macos', "
            "'forecast')",
            (h["time"], h["temperature"], h["pressure"], h["pressure_surface"]),
        )
    conn.commit()


@pytest.fixture
def limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai_coach.load.weather_signal.PRESSURE_LIMIT", 5)
    monkeypatch.setattr("ai_coach.load.weather_signal.TEMPERATURE_LIMIT", 7)


@pytest.mark.usefixtures("limits")
def test_report_for_today_gives_date_and_signals(conn: sqlite3.Connection) -> None:
    from ai_coach.load.weather_signal import weather_report

    put_hours(conn, series(pressure=level(1015.0, {"2026-11-22T19:00": 1008.0})))
    report = weather_report(conn, "2026-11-22", NOW)
    assert report["date"] == "2026-11-22"
    assert [(s["kind"], s["value"], s["at"]) for s in report["signals"]] == [
        ("pressure_drop", 7.0, "19:00")
    ]


@pytest.mark.usefixtures("limits")
def test_report_for_other_day_has_no_signals(conn: sqlite3.Connection) -> None:
    from ai_coach.load.weather_signal import weather_report

    put_hours(conn, series(pressure=level(1015.0, {"2026-11-22T19:00": 1008.0})))
    assert weather_report(conn, "2026-11-21", NOW)["signals"] == []


@pytest.mark.usefixtures("limits")
def test_report_for_empty_table_has_no_signals(conn: sqlite3.Connection) -> None:
    from ai_coach.load.weather_signal import weather_report

    assert weather_report(conn, "2026-11-22", NOW) == {"date": "2026-11-22", "signals": []}


@pytest.mark.usefixtures("limits")
def test_report_window_moves_with_now(conn: sqlite3.Connection) -> None:
    from ai_coach.load.weather_signal import weather_report

    put_hours(conn, series(pressure=level(1015.0, {"2026-11-22T19:00": 1008.0})))
    morning = weather_report(conn, "2026-11-22", NOW)["signals"]
    evening = weather_report(conn, "2026-11-22", datetime(2026, 11, 22, 19, 20))["signals"]
    assert [s["value"] for s in morning] == [7.0]
    assert evening == []


@pytest.mark.usefixtures("limits")
def test_report_daily_warming_is_morning_signal_not_afternoon(conn: sqlite3.Connection) -> None:
    from ai_coach.load.weather_signal import weather_report

    put_hours(conn, series(temperature=level(4.0, {"2026-11-22T15:00": 12.0})))
    morning = weather_report(conn, "2026-11-22", NOW)["signals"]
    assert [(s["kind"], s["value"]) for s in morning] == [("temperature_rise", 8.0)]


@pytest.mark.usefixtures("limits")
def test_report_afternoon_gives_night_cooling_instead(conn: sqlite3.Connection) -> None:
    from ai_coach.load.weather_signal import weather_report

    put_hours(conn, series(temperature=level(4.0, {"2026-11-22T15:00": 12.0})))
    signals = weather_report(conn, "2026-11-22", datetime(2026, 11, 22, 15, 20))["signals"]
    assert [(s["kind"], s["value"]) for s in signals] == [("temperature_drop", 8.0)]


def test_limit_constants_cite_decisions_and_research() -> None:
    from ai_coach.load import weather_signal

    text = Path(weather_signal.__file__).read_text(encoding="utf-8")
    assert "Решения" in text
    assert "research-weather-wellbeing.md" in text
    assert "Пороги и окно" in text
    assert "выбран по частоте на ряде Влада, наукой не проверен" in text


def test_temperature_subtraction_noise_on_the_limit_is_no_signal() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(temperature=level(4.3, {"2026-11-22T15:00": 11.3}))
    assert find_weather_signals(hours, NOW, LIMITS) == []


def test_temperature_just_above_the_limit_gives_one_decimal_value() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(temperature=level(4.3, {"2026-11-22T15:00": 11.4}))
    [row] = find_weather_signals(hours, NOW, LIMITS)
    assert (row["kind"], row["value"]) == ("temperature_rise", 7.1)


def test_pressure_subtraction_noise_on_the_limit_is_no_signal() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1024.4, {"2026-11-22T19:00": 1017.4}))
    assert find_weather_signals(hours, NOW, {"pressure": 7, "temperature": None}) == []


def test_pressure_drop_rounding_to_the_limit_is_no_signal() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1020.0, {"2026-11-22T19:00": 1014.96}))
    assert find_weather_signals(hours, NOW, {"pressure": 5, "temperature": None}) == []


@pytest.mark.usefixtures("limits")
def test_report_for_other_day_keeps_its_date(conn: sqlite3.Connection) -> None:
    from ai_coach.load.weather_signal import weather_report

    assert weather_report(conn, "2026-11-21", NOW) == {"date": "2026-11-21", "signals": []}


def test_pressure_just_above_the_limit_gives_one_decimal_value() -> None:
    from ai_coach.load.weather_signal import find_weather_signals

    hours = series(pressure=level(1024.5, {"2026-11-22T19:00": 1017.4}))
    [row] = find_weather_signals(hours, NOW, {"pressure": 7, "temperature": None})
    assert (row["kind"], row["value"]) == ("pressure_drop", 7.1)
