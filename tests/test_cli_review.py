"""coach review done [--week YYYY-MM-DD] ["заметка"]: недельный обзор проведён (шаг v2.5).
По умолчанию как у coach feel (день самочувствия, до 04:00 - вчера): в понедельник - прошедшая
неделя, в остальные дни - текущая. --week не понедельник - ошибка. Повтор - upsert."""

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
        raise AssertionError("review не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def reviews(db: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM review_log ORDER BY week_start").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def weeks(db: Path) -> list[str]:
    return [r["week_start"] for r in reviews(db)]


def done(*args: str) -> Any:
    return runner.invoke(main.app, ["review", "done", *args])


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2026-10-05 12:00:00", "2026-09-28"),  # понедельник - прошедшая неделя
        ("2026-10-06 12:00:00", "2026-10-05"),  # вторник
        ("2026-10-07 12:00:00", "2026-10-05"),
        ("2026-10-10 12:00:00", "2026-10-05"),  # суббота
        ("2026-10-11 12:00:00", "2026-10-05"),  # воскресенье - текущая
        ("2026-10-12 12:00:00", "2026-10-05"),  # понедельник - прошедшая
        ("2026-10-12 00:00:00", "2026-10-05"),  # ночь на понедельник - ещё воскресенье
        ("2026-10-11 23:59:00", "2026-10-05"),
    ],
)
def test_default_week_by_weekday(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, now: str, expected: str
) -> None:
    freeze(monkeypatch, now)
    assert done().exit_code == 0
    assert weeks(isolated) == [expected]


def test_tuesday_at_0359_is_still_monday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-13 03:59:00")
    done()
    assert weeks(isolated) == ["2026-10-05"]


def test_tuesday_at_0400_is_current_week(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-13 04:00:00")
    done()
    assert weeks(isolated) == ["2026-10-12"]


def test_monday_at_0400_is_previous_week(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-12 04:00:00")
    done()
    assert weeks(isolated) == ["2026-10-05"]


def test_wednesday_is_current_week(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-14 12:00:00")
    done()
    assert weeks(isolated) == ["2026-10-12"]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2027-01-04 10:00:00", "2026-12-28"),  # понедельник нового года - прошедшая неделя 53
        ("2027-01-05 03:00:00", "2026-12-28"),
        ("2027-01-05 04:00:00", "2027-01-04"),
        ("2027-01-01 10:00:00", "2026-12-28"),  # пятница 1 января - неделя из прошлого года
    ],
)
def test_default_week_on_year_border(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, now: str, expected: str
) -> None:
    freeze(monkeypatch, now)
    done()
    assert weeks(isolated) == [expected]


def test_done_at_keeps_real_time(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-12 01:51:00")
    done()
    assert reviews(isolated)[0]["done_at"] == "2026-10-12 01:51:00"


def test_note_is_saved_as_is(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 12:00:00")
    done("снизить вечера, больше сна")
    assert reviews(isolated)[0]["note"] == "снизить вечера, больше сна"


def test_no_note_is_null(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 12:00:00")
    done()
    assert reviews(isolated)[0]["note"] is None


def test_output_names_the_week(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 12:00:00")
    assert "2026-10-05" in done().output


# --- --week ---


def test_week_flag_overrides_default(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-14 12:00:00")
    assert done("--week", "2026-09-28").exit_code == 0
    assert weeks(isolated) == ["2026-09-28"]


def test_week_flag_with_note(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-14 12:00:00")
    done("--week", "2026-09-28", "заметка")
    row = reviews(isolated)[0]
    assert (row["week_start"], row["note"]) == ("2026-09-28", "заметка")


@pytest.mark.parametrize("value", ["2026-10-06", "2026-10-11", "2026-10-04"])
def test_week_not_monday_is_error(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    freeze(monkeypatch, "2026-10-14 12:00:00")
    result = done("--week", value)
    assert result.exit_code != 0
    assert weeks(isolated) == []


@pytest.mark.parametrize("value", ["вчера", "2026-13-01", "2026-9-28", "28.09.2026"])
def test_week_bad_format_is_error(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    freeze(monkeypatch, "2026-10-14 12:00:00")
    assert done("--week", value).exit_code != 0
    assert weeks(isolated) == []


# --- повтор ---


def test_repeat_is_upsert_not_second_row(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 12:00:00")
    done("первая")
    assert done("вторая").exit_code == 0
    rows = reviews(isolated)
    assert len(rows) == 1
    assert rows[0]["note"] == "вторая"


def test_different_weeks_are_different_rows(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-14 12:00:00")
    done()
    done("--week", "2026-10-05")
    assert weeks(isolated) == ["2026-10-05", "2026-10-12"]


def test_repeat_without_note_keeps_old_note(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 12:00:00")
    done("первая")
    assert done().exit_code == 0
    assert reviews(isolated)[0]["note"] == "первая"
