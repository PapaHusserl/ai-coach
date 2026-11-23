"""Хранилище погоды: читающие функции без места (П7, партия 4)."""

import sqlite3

import pytest

HIDDEN = {"lat", "lon", "place_source", "utc_offset_seconds"}


def put_now(conn: sqlite3.Connection, observed_at: str, temperature: float = 3.7) -> None:
    conn.execute(
        "INSERT INTO weather_now (observed_at, temperature, apparent, code, wind, pressure, "
        "fetched_at, lat, lon, place_source, utc_offset_seconds) "
        "VALUES (?, ?, 0.3, 2, 3.09, 1018.4, '2026-11-22T14:10:00', 52.52, 13.41, 'macos', 3600)",
        (observed_at, temperature),
    )
    conn.commit()


def put_day(conn: sqlite3.Connection, day: str) -> None:
    conn.execute(
        "INSERT INTO weather_days (date, code, t_max, t_min, precip_prob, fetched_at, lat, lon) "
        "VALUES (?, 80, 5.6, 1.9, 88, '2026-11-22T14:10:00', 52.52, 13.41)",
        (day,),
    )
    conn.commit()


def test_list_weather_now_takes_period_in_time_order(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import list_weather_now

    put_now(conn, "2026-11-22T19:15", 1.0)
    put_now(conn, "2026-11-21T23:45", 9.0)
    put_now(conn, "2026-11-22T08:30", 2.0)
    rows = list_weather_now(conn, "2026-11-22", "2026-11-22")
    assert [r["observed_at"] for r in rows] == ["2026-11-22T08:30", "2026-11-22T19:15"]


def test_list_weather_now_rows_have_no_place_or_offset(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import list_weather_now

    put_now(conn, "2026-11-22T08:30")
    [row] = list_weather_now(conn, "2026-11-22", "2026-11-22")
    assert not HIDDEN & set(row)


def test_list_weather_now_empty_period_is_empty(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import list_weather_now

    put_now(conn, "2026-11-22T08:30")
    assert list_weather_now(conn, "2026-11-23", "2026-11-24") == []


def test_last_weather_now_is_latest_even_if_older_inserted_last(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import last_weather_now

    put_now(conn, "2026-11-22T19:15", 1.0)
    put_now(conn, "2026-11-21T23:45", 9.0)
    row = last_weather_now(conn)
    assert row is not None
    assert row["observed_at"] == "2026-11-22T19:15"
    assert not HIDDEN & set(row)


def test_last_weather_now_empty_is_none(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import last_weather_now

    assert last_weather_now(conn) is None


def test_list_weather_days_period_order_and_no_place(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import list_weather_days

    for day in ("2026-11-24", "2026-11-22", "2026-11-23"):
        put_day(conn, day)
    rows = list_weather_days(conn, "2026-11-22", "2026-11-23")
    assert [r["date"] for r in rows] == ["2026-11-22", "2026-11-23"]
    assert not HIDDEN & set(rows[0])


def put_hour(conn: sqlite3.Connection, time: str, temperature: float = 2.0) -> None:
    conn.execute(
        "INSERT INTO weather_hours (time, temperature, pressure, pressure_surface, humidity, wind, "
        "fetched_at, lat, lon, place_source, source) "
        "VALUES (?, ?, 1018.4, 1008.4, 80, 3.0, '2026-11-22T14:10:00', 52.52, 13.41, 'macos', "
        "'forecast')",
        (time, temperature),
    )
    conn.commit()


def test_list_weather_hours_takes_period_in_time_order(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import list_weather_hours

    for time in (
        "2026-11-23T00:00",
        "2026-11-22T23:00",
        "2026-11-22T00:00",
        "2026-11-22T12:00",
        "2026-11-21T23:00",
    ):
        put_hour(conn, time)
    rows = list_weather_hours(conn, "2026-11-22", "2026-11-22")
    assert [r["time"] for r in rows] == ["2026-11-22T00:00", "2026-11-22T12:00", "2026-11-22T23:00"]


def test_list_weather_hours_rows_have_no_place_and_keep_numbers(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import list_weather_hours

    put_hour(conn, "2026-11-22T12:00", temperature=2.5)
    [row] = list_weather_hours(conn, "2026-11-22", "2026-11-22")
    assert not HIDDEN & set(row)
    assert (row["temperature"], row["pressure"]) == (2.5, 1018.4)


def hour_row(time: str, temperature: float) -> dict[str, object]:
    return {
        "time": time,
        "temperature": temperature,
        "pressure": 1018.4,
        "pressure_surface": 1008.4,
        "humidity": 80,
        "wind": 3.0,
        "fetched_at": "2026-11-22T14:10:00",
        "lat": 52.52,
        "lon": 13.41,
        "place_source": "macos",
        "source": "forecast",
    }


def test_upsert_weather_hours_two_rows_are_two_records(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import upsert_weather_hours

    upsert_weather_hours(
        conn, [hour_row("2026-11-22T12:00", 1.0), hour_row("2026-11-22T13:00", 2.0)]
    )
    assert conn.execute("SELECT COUNT(*) FROM weather_hours").fetchone()[0] == 2


def test_upsert_weather_hours_same_time_replaces_temperature(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import upsert_weather_hours

    upsert_weather_hours(conn, [hour_row("2026-11-22T12:00", 1.0)])
    upsert_weather_hours(conn, [hour_row("2026-11-22T12:00", 7.5)])
    rows = conn.execute("SELECT temperature FROM weather_hours").fetchall()
    assert [r["temperature"] for r in rows] == [7.5]


def test_list_weather_hours_empty_period_is_empty(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import list_weather_hours

    put_hour(conn, "2026-11-22T12:00")
    assert list_weather_hours(conn, "2026-11-24", "2026-11-25") == []


def test_days_with_hours_gives_each_day_once_inside_period(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import days_with_hours

    for time in (
        "2026-11-18T23:00",
        "2026-11-19T00:00",
        "2026-11-19T12:00",
        "2026-11-21T05:00",
        "2026-11-22T00:00",
    ):
        put_hour(conn, time)
    assert sorted(days_with_hours(conn, "2026-11-19", "2026-11-21")) == ["2026-11-19", "2026-11-21"]


@pytest.mark.parametrize("fetched_at", ["2026-11-22T14:10:00", "2026-11-20T08:00:00"])
def test_days_with_hours_skips_hour_fetched_not_later_than_its_day(
    conn: sqlite3.Connection, fetched_at: str
) -> None:
    from ai_coach.store.weather import days_with_hours, upsert_weather_hours

    upsert_weather_hours(conn, [{**hour_row("2026-11-22T12:00", 1.0), "fetched_at": fetched_at}])
    assert not days_with_hours(conn, "2026-11-01", "2026-11-30")


def test_days_with_hours_empty_table_is_empty(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import days_with_hours

    assert not list(days_with_hours(conn, "2026-11-01", "2026-11-30"))


def signal_row(**values: object) -> dict[str, object]:
    row: dict[str, object] = {
        "date": "2026-11-22",
        "kind": "pressure_drop",
        "value": 7.0,
        "limit_value": 5,
        "extreme_at": "2026-11-22T19:00",
        "created_at": "2026-11-22T07:20:00",
    }
    return {**row, **values}


def stored_signals(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    sql = "SELECT date, kind, value, extreme_at FROM weather_signals ORDER BY date, kind"
    return [tuple(r) for r in conn.execute(sql)]


def test_add_weather_signal_writes_the_row(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import add_weather_signal

    add_weather_signal(conn, signal_row())
    assert stored_signals(conn) == [("2026-11-22", "pressure_drop", 7.0, "2026-11-22T19:00")]


def test_add_weather_signal_first_record_of_day_stays(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import add_weather_signal

    add_weather_signal(conn, signal_row())
    add_weather_signal(conn, signal_row(value=9.5, extreme_at="2026-11-23T03:00"))
    assert stored_signals(conn) == [("2026-11-22", "pressure_drop", 7.0, "2026-11-22T19:00")]


def test_add_weather_signal_other_kind_and_other_day_are_new_rows(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import add_weather_signal

    add_weather_signal(conn, signal_row())
    add_weather_signal(conn, signal_row(kind="temperature_rise"))
    add_weather_signal(conn, signal_row(date="2026-11-23"))
    assert len(stored_signals(conn)) == 3


def kp_row(**values: object) -> dict[str, object]:
    row: dict[str, object] = {
        "time": "2026-11-22T15:00:00",
        "kp": 2.0,
        "kind": "predicted",
        "fetched_at": "2026-11-22T14:10:00",
    }
    return {**row, **values}


def stored_kp(conn: sqlite3.Connection) -> list[tuple[object, ...]]:
    sql = "SELECT time, kp, kind, fetched_at FROM kp_index ORDER BY time"
    return [tuple(r) for r in conn.execute(sql)]


def test_upsert_kp_writes_all_rows(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import upsert_kp

    upsert_kp(conn, [kp_row(), kp_row(time="2026-11-22T18:00:00", kp=0.67)])
    assert stored_kp(conn) == [
        ("2026-11-22T15:00:00", 2.0, "predicted", "2026-11-22T14:10:00"),
        ("2026-11-22T18:00:00", 0.67, "predicted", "2026-11-22T14:10:00"),
    ]


def test_upsert_kp_same_time_is_overwritten_by_fresh_row(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import upsert_kp

    upsert_kp(conn, [kp_row()])
    upsert_kp(conn, [kp_row(kind="observed", kp=3.33, fetched_at="2026-11-22T20:10:00")])
    assert stored_kp(conn) == [("2026-11-22T15:00:00", 3.33, "observed", "2026-11-22T20:10:00")]


def test_upsert_kp_keeps_rows_absent_from_new_answer(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import upsert_kp

    upsert_kp(conn, [kp_row(), kp_row(time="2026-11-22T18:00:00")])
    upsert_kp(conn, [kp_row(time="2026-11-22T18:00:00", kind="observed")])
    assert [r[0] for r in stored_kp(conn)] == ["2026-11-22T15:00:00", "2026-11-22T18:00:00"]


def test_upsert_kp_empty_list_changes_nothing(conn: sqlite3.Connection) -> None:
    from ai_coach.store.weather import upsert_kp

    upsert_kp(conn, [])
    assert stored_kp(conn) == []
