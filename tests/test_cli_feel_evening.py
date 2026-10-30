"""coach feel <1-5> ["текст"] [--mood 1-5] [--stress 1-5] [--work ч] [--hobby ч] [--rest ч]:
mood/stress - в wellbeing_log, часы - в day_counters (source manual, kind work_hours и т.д.)."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
TODAY = "2026-10-14"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    freeze(monkeypatch, f"{TODAY} 12:00:00")
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("feel не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def query(db: Path, sql: str) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def wellbeing(db: Path) -> list[sqlite3.Row]:
    return query(db, "SELECT * FROM wellbeing_log ORDER BY id")


def counters(db: Path) -> dict[str, float]:
    found = query(db, "SELECT * FROM day_counters WHERE source = 'manual'")
    return {r["kind"]: r["value"] for r in found}


def test_feel_without_options_leaves_mood_stress_empty(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "4"])
    row = wellbeing(isolated)[0]
    assert (row["mood"], row["stress"]) == (None, None)


def test_feel_without_options_writes_no_counters(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "4"])
    assert counters(isolated) == {}


def test_mood_and_stress_are_saved(isolated: Path) -> None:
    result = runner.invoke(main.app, ["feel", "3", "--mood", "2", "--stress", "4"])
    assert result.exit_code == 0
    row = wellbeing(isolated)[0]
    assert (row["score"], row["mood"], row["stress"]) == (3, 2, 4)


def test_only_mood_is_saved(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--mood", "5"])
    row = wellbeing(isolated)[0]
    assert (row["mood"], row["stress"]) == (5, None)


def test_only_stress_is_saved(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--stress", "1"])
    row = wellbeing(isolated)[0]
    assert (row["mood"], row["stress"]) == (None, 1)


def test_text_and_options_together(isolated: Path) -> None:
    result = runner.invoke(main.app, ["feel", "2", "тяжёлый день", "--mood", "2", "--work", "9"])
    assert result.exit_code == 0
    row = wellbeing(isolated)[0]
    assert (row["text"], row["mood"]) == ("тяжёлый день", 2)


def test_hours_go_to_manual_counters_of_today(isolated: Path) -> None:
    result = runner.invoke(
        main.app, ["feel", "3", "--work", "9.5", "--hobby", "1", "--rest", "2.5"]
    )
    assert result.exit_code == 0
    assert counters(isolated) == {"work_hours": 9.5, "hobby_hours": 1.0, "rest_hours": 2.5}
    dates = query(isolated, "SELECT DISTINCT date FROM day_counters")
    assert [r["date"] for r in dates] == [TODAY]


def test_only_given_hours_are_written(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--work", "8"])
    assert counters(isolated) == {"work_hours": 8.0}


def test_second_feel_overwrites_hours_of_the_day(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--work", "4"])
    runner.invoke(main.app, ["feel", "3", "--work", "9"])
    assert counters(isolated) == {"work_hours": 9.0}


def test_feel_without_hours_keeps_earlier_hours(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--work", "4", "--rest", "1"])
    runner.invoke(main.app, ["feel", "4", "--mood", "4"])
    assert counters(isolated) == {"work_hours": 4.0, "rest_hours": 1.0}


def test_hours_do_not_make_extra_wellbeing_rows(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--work", "4"])
    assert len(wellbeing(isolated)) == 1


@pytest.mark.parametrize("value", ["0", "24"])
def test_hours_limits_are_inclusive(isolated: Path, value: str) -> None:
    assert runner.invoke(main.app, ["feel", "3", "--work", value]).exit_code == 0
    assert counters(isolated) == {"work_hours": float(value)}


@pytest.mark.parametrize("option", ["--work", "--hobby", "--rest"])
@pytest.mark.parametrize("value", ["-1", "24.5", "25", "abc", "nan"])
def test_bad_hours_are_rejected_and_nothing_saved(isolated: Path, option: str, value: str) -> None:
    result = runner.invoke(main.app, ["feel", "3", option, value])
    assert result.exit_code != 0
    assert wellbeing(isolated) == []
    assert counters(isolated) == {}


@pytest.mark.parametrize("value", ["1", "5"])
@pytest.mark.parametrize("option", ["--mood", "--stress"])
def test_mood_stress_limits_are_inclusive(isolated: Path, option: str, value: str) -> None:
    assert runner.invoke(main.app, ["feel", "3", option, value]).exit_code == 0


@pytest.mark.parametrize("option", ["--mood", "--stress"])
@pytest.mark.parametrize("value", ["0", "6", "7", "-1", "3.5", "abc"])
def test_bad_mood_stress_is_rejected_and_nothing_saved(
    isolated: Path, option: str, value: str
) -> None:
    result = runner.invoke(main.app, ["feel", "3", option, value, "--work", "5"])
    assert result.exit_code != 0
    assert wellbeing(isolated) == []
    assert counters(isolated) == {}


def new_fields(db: Path) -> tuple[Any, ...]:
    row = wellbeing(db)[0]
    return (row["work_thoughts"], row["flow"], row["hindrance"], row["valuable"])


def test_detachment_options_are_saved(isolated: Path) -> None:
    args = ["feel", "3", "--thoughts", "4", "--flow", "--hindrance", "2", "--valuable", "4"]
    assert runner.invoke(main.app, args).exit_code == 0
    assert new_fields(isolated) == (4, 1, 2, 4)


def test_no_flow_is_saved_as_zero(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--no-flow"])
    assert new_fields(isolated) == (None, 0, None, None)


def test_detachment_options_absent_are_null(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--mood", "3"])
    assert new_fields(isolated) == (None, None, None, None)


def test_only_one_detachment_option_leaves_others_null(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "3", "--hindrance", "5"])
    assert new_fields(isolated) == (None, None, 5, None)


@pytest.mark.parametrize("option", ["--thoughts", "--hindrance", "--valuable"])
@pytest.mark.parametrize("value", ["1", "5"])
def test_detachment_limits_are_inclusive(isolated: Path, option: str, value: str) -> None:
    assert runner.invoke(main.app, ["feel", "3", option, value]).exit_code == 0


@pytest.mark.parametrize("option", ["--thoughts", "--hindrance", "--valuable"])
@pytest.mark.parametrize("value", ["0", "6", "-1", "3.5", "abc"])
def test_bad_detachment_value_is_rejected_and_nothing_saved(
    isolated: Path, option: str, value: str
) -> None:
    result = runner.invoke(main.app, ["feel", "3", option, value, "--work", "5"])
    assert result.exit_code != 0
    assert wellbeing(isolated) == []
    assert counters(isolated) == {}


def test_detachment_without_mood_stress_keeps_hours_and_score(isolated: Path) -> None:
    runner.invoke(main.app, ["feel", "4", "--thoughts", "2", "--work", "6"])
    assert counters(isolated) == {"work_hours": 6.0}
    assert wellbeing(isolated)[0]["score"] == 4


def test_bad_score_with_options_is_still_rejected(isolated: Path) -> None:
    result = runner.invoke(main.app, ["feel", "6", "--mood", "3"])
    assert result.exit_code != 0
    assert wellbeing(isolated) == []
