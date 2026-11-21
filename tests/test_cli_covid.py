"""Шаг Н49, партия 2: coach covid - отметка COVID за день, снятие, ошибки."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
TODAY = "2026-11-20"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    return db


@pytest.fixture
def noon(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def marks(db: Path) -> list[str]:
    conn = sqlite3.connect(db)
    try:
        return [r[0] for r in conn.execute("SELECT date FROM covid_marks ORDER BY date")]
    finally:
        conn.close()


@pytest.mark.usefixtures("noon")
def test_mark_today(isolated: Path) -> None:
    result = run("covid")
    assert result.exit_code == 0
    assert "COVID отмечен за 2026-11-20." in result.output
    assert marks(isolated) == [TODAY]


@pytest.mark.usefixtures("noon")
def test_mark_twice_gives_same_output_and_one_row(isolated: Path) -> None:
    first = run("covid")
    second = run("covid")
    assert second.exit_code == 0
    assert second.output == first.output
    assert marks(isolated) == [TODAY]


@pytest.mark.usefixtures("noon")
def test_mark_with_date(isolated: Path) -> None:
    result = run("covid", "--date", "2026-11-18")
    assert result.exit_code == 0
    assert "COVID отмечен за 2026-11-18." in result.output
    assert marks(isolated) == ["2026-11-18"]


def test_mark_at_night_is_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-11-20 03:30:00")
    result = run("covid")
    assert result.exit_code == 0
    assert marks(isolated) == ["2026-11-19"]


def test_mark_at_four_is_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-11-20 04:00:00")
    assert run("covid").exit_code == 0
    assert marks(isolated) == [TODAY]


def test_night_explicit_calendar_today_is_accepted(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-11-20 03:30:00")
    assert run("covid", "--date", "2026-11-20").exit_code == 0
    assert marks(isolated) == [TODAY]


def test_night_explicit_tomorrow_is_error(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-11-20 03:30:00")
    result = run("covid", "--date", "2026-11-21")
    assert result.exit_code == 1
    assert "--date в будущем." in result.output
    assert marks(isolated) == []


@pytest.mark.usefixtures("noon")
def test_undo_removes_todays_mark(isolated: Path) -> None:
    run("covid")
    result = run("covid", "--undo")
    assert result.exit_code == 0
    assert "Отметка COVID за 2026-11-20 снята." in result.output
    assert marks(isolated) == []


@pytest.mark.usefixtures("noon")
def test_undo_with_date_removes_only_that_day(isolated: Path) -> None:
    run("covid", "--date", "2026-11-18")
    run("covid")
    assert run("covid", "--date", "2026-11-18", "--undo").exit_code == 0
    assert marks(isolated) == [TODAY]


@pytest.mark.usefixtures("noon")
def test_undo_without_todays_mark_lists_other_days(isolated: Path) -> None:
    run("covid", "--date", "2026-11-18")
    result = run("covid", "--undo")
    assert result.exit_code == 1
    assert "Отметки COVID за 2026-11-20 нет. Есть за: 2026-11-18." in result.output
    assert marks(isolated) == ["2026-11-18"]


@pytest.mark.usefixtures("noon")
def test_undo_lists_all_other_days(isolated: Path) -> None:
    run("covid", "--date", "2026-11-17")
    run("covid", "--date", "2026-11-18")
    result = run("covid", "--undo")
    assert "Есть за: 2026-11-17, 2026-11-18." in result.output


@pytest.mark.usefixtures("noon")
def test_undo_with_no_marks_at_all(isolated: Path) -> None:
    result = run("covid", "--undo")
    assert result.exit_code == 1
    assert "Отметки COVID за 2026-11-20 нет." in result.output
    assert "Есть за" not in result.output
    assert result.output.strip().endswith("Отметки COVID за 2026-11-20 нет.")


@pytest.mark.usefixtures("noon")
def test_future_date_is_error(isolated: Path) -> None:
    result = run("covid", "--date", "2026-11-21")
    assert result.exit_code == 1
    assert "--date в будущем." in result.output
    assert result.output.strip().endswith("--date в будущем.")
    assert marks(isolated) == []


@pytest.mark.usefixtures("noon")
def test_bad_date_is_error_with_check_date_text(isolated: Path) -> None:
    result = run("covid", "--date", "20.11")
    assert result.exit_code == 1
    assert "Дата должна быть YYYY-MM-DD, получено: '20.11'" in result.output
    assert marks(isolated) == []


@pytest.mark.usefixtures("noon")
def test_undo_hint_ignores_marks_older_than_21_days(isolated: Path) -> None:
    run("covid", "--date", "2026-10-30")
    result = run("covid", "--undo")
    assert result.exit_code == 1
    assert "Отметки COVID за 2026-11-20 нет." in result.output
    assert "Есть за" not in result.output


@pytest.mark.usefixtures("noon")
def test_undo_hint_shows_mark_on_first_day_of_window(isolated: Path) -> None:
    run("covid", "--date", "2026-10-31")
    result = run("covid", "--undo")
    assert "Есть за: 2026-10-31." in result.output
