"""coach feel после полуночи (до EVENING_CUTOFF = 04:00) относится к прошедшему вечеру:
дата записи самочувствия и ручных часов - вчера; остальные записи - по календарной дате."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("feel не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def query(db: Path, sql: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def feel_dates(db: Path) -> list[str]:
    return [r["date"] for r in query(db, "SELECT date FROM wellbeing_log ORDER BY id")]


def counter_dates(db: Path) -> list[str]:
    return [r["date"] for r in query(db, "SELECT DISTINCT date FROM day_counters")]


def test_feel_at_0359_goes_to_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 03:59:00")
    assert runner.invoke(main.app, ["feel", "3", "--mood", "3"]).exit_code == 0
    assert feel_dates(isolated) == ["2026-10-10"]


def test_feel_at_0400_goes_to_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 04:00:00")
    runner.invoke(main.app, ["feel", "3", "--mood", "3"])
    assert feel_dates(isolated) == ["2026-10-11"]


def test_feel_at_0151_goes_to_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 01:51:00")
    runner.invoke(main.app, ["feel", "4"])
    assert feel_dates(isolated) == ["2026-10-10"]


def test_feel_at_midnight_goes_to_yesterday(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 00:00:00")
    runner.invoke(main.app, ["feel", "4"])
    assert feel_dates(isolated) == ["2026-10-10"]


def test_feel_in_the_evening_goes_to_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-10 22:00:00")
    runner.invoke(main.app, ["feel", "4"])
    assert feel_dates(isolated) == ["2026-10-10"]


def test_logged_at_keeps_real_time(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 01:51:00")
    runner.invoke(main.app, ["feel", "4"])
    row = query(isolated, "SELECT logged_at FROM wellbeing_log")[0]
    assert row["logged_at"] == "2026-10-11 01:51:00"


def test_text_mood_stress_go_to_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 02:00:00")
    runner.invoke(main.app, ["feel", "2", "поздно лёг", "--mood", "2", "--stress", "4"])
    row = query(isolated, "SELECT * FROM wellbeing_log")[0]
    assert (row["date"], row["text"], row["mood"], row["stress"]) == (
        "2026-10-10",
        "поздно лёг",
        2,
        4,
    )


def test_hours_at_0359_go_to_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 03:59:00")
    runner.invoke(main.app, ["feel", "3", "--work", "9", "--hobby", "1", "--rest", "2"])
    assert counter_dates(isolated) == ["2026-10-10"]


def test_hours_at_0400_go_to_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 04:00:00")
    runner.invoke(main.app, ["feel", "3", "--work", "9"])
    assert counter_dates(isolated) == ["2026-10-11"]


def test_hours_and_score_share_the_day(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 01:00:00")
    runner.invoke(main.app, ["feel", "3", "--work", "9"])
    assert counter_dates(isolated) == feel_dates(isolated) == ["2026-10-10"]


def test_second_night_feel_overwrites_hours_of_yesterday(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 01:00:00")
    runner.invoke(main.app, ["feel", "3", "--work", "4"])
    runner.invoke(main.app, ["feel", "3", "--work", "9"])
    found = query(isolated, "SELECT date, value FROM day_counters WHERE kind = 'work_hours'")
    assert [(r["date"], r["value"]) for r in found] == [("2026-10-10", 9.0)]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2026-11-01 01:00:00", "2026-10-31"),
        ("2026-11-01 03:59:00", "2026-10-31"),
        ("2026-11-01 04:00:00", "2026-11-01"),
        ("2026-03-01 02:00:00", "2026-02-28"),
        ("2027-01-01 00:30:00", "2026-12-31"),
    ],
)
def test_day_changes_correctly_on_month_and_year_border(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, now: str, expected: str
) -> None:
    freeze(monkeypatch, now)
    runner.invoke(main.app, ["feel", "3", "--work", "5"])
    assert feel_dates(isolated) == counter_dates(isolated) == [expected]


def test_weight_at_night_keeps_calendar_date(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 01:00:00")
    runner.invoke(main.app, ["weight", "81.7"])
    row = query(isolated, "SELECT measured_at FROM weight_log")[0]
    assert row["measured_at"].startswith("2026-10-11")


def test_food_at_night_keeps_calendar_date(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 01:00:00")
    runner.invoke(main.app, ["food", "омлет"])
    row = query(isolated, "SELECT logged_at FROM food_log")[0]
    assert row["logged_at"].startswith("2026-10-11")
