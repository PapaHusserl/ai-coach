"""evening_done_today в snapshot: до EVENING_CUTOFF (04:00) «день самочувствия» - вчера,
поэтому ночью виден вчерашний чек-ин; остальные поля snapshot - по переданной дате."""

import sqlite3

import pytest
from fake_clock import freeze
from mcp_fakes import call

TODAY = "2026-10-11"
YESTERDAY = "2026-10-10"


def feel(conn: sqlite3.Connection, day: str, at: str, **fields: object) -> None:
    values = {"date": day, "logged_at": f"{day} {at}", "score": 3, **fields}
    names = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(f"INSERT INTO wellbeing_log ({names}) VALUES ({marks})", tuple(values.values()))


def done(conn: sqlite3.Connection, day: str = TODAY) -> bool:
    return call(conn, "get_morning_snapshot", date=day)["evening_done_today"]


def test_at_0100_sees_yesterdays_checkin(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    feel(conn, YESTERDAY, "21:00:00", mood=4)
    freeze(monkeypatch, "2026-10-11 01:00:00")
    assert done(conn) is True


def test_at_0100_checkin_written_after_midnight_counts(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    feel(conn, YESTERDAY, "01:51:00", stress=2)
    freeze(monkeypatch, "2026-10-11 02:00:00")
    assert done(conn) is True


def test_at_0359_still_yesterday(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    feel(conn, YESTERDAY, "21:00:00", mood=4)
    freeze(monkeypatch, "2026-10-11 03:59:00")
    assert done(conn) is True


def test_at_0400_yesterdays_checkin_is_not_counted(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    feel(conn, YESTERDAY, "21:00:00", mood=4)
    freeze(monkeypatch, "2026-10-11 04:00:00")
    assert done(conn) is False


def test_at_0100_todays_dated_checkin_is_not_counted(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    feel(conn, TODAY, "00:30:00", mood=4)
    freeze(monkeypatch, "2026-10-11 01:00:00")
    assert done(conn) is False


def test_at_0100_without_checkin_is_false(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 01:00:00")
    assert done(conn) is False


def test_at_0100_morning_entry_without_mood_stress_is_not_evening(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    feel(conn, YESTERDAY, "08:00:00", score=4)
    freeze(monkeypatch, "2026-10-11 01:00:00")
    assert done(conn) is False


def test_at_0100_on_first_of_month_sees_last_day_of_previous(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    feel(conn, "2026-10-31", "22:00:00", mood=3)
    freeze(monkeypatch, "2026-11-01 01:00:00")
    assert done(conn, "2026-11-01") is True


def test_daytime_uses_the_given_date(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    feel(conn, YESTERDAY, "21:00:00", mood=4)
    freeze(monkeypatch, "2026-10-11 12:00:00")
    assert done(conn) is False


def test_at_0100_explicit_yesterday_date_sees_its_checkin(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    feel(conn, YESTERDAY, "21:00:00", mood=4)
    freeze(monkeypatch, "2026-10-11 01:00:00")
    assert done(conn, YESTERDAY) is True
