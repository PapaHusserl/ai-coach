"""Хранилище погоды: читающие функции без места (П7, партия 4)."""

import sqlite3

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
