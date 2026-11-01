"""coach who5 <5 ответов 0-5> ["текст"] и coach log who5: таблица who5_log (план Н12)."""

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
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("who5 не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


@pytest.fixture
def noon(monkeypatch: pytest.MonkeyPatch) -> None:
    # freeze не переживает повторного вызова в одном тесте: время задаётся один раз
    freeze(monkeypatch, f"{TODAY} 12:00:00")


def who5_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM who5_log ORDER BY id").fetchall()
    finally:
        conn.close()


def run(*args: str) -> Any:
    return runner.invoke(main.app, ["who5", *args])


@pytest.mark.usefixtures("noon")
def test_who5_writes_one_row(isolated: Path) -> None:
    result = run("5", "4", "3", "4", "5")
    assert result.exit_code == 0
    assert "WHO-5: 84 из 100 - записано." in result.output
    (row,) = who5_rows(isolated)
    assert (row["date"], row["logged_at"]) == (TODAY, f"{TODAY} 12:00:00")
    assert [row[f"q{n}"] for n in range(1, 6)] == [5, 4, 3, 4, 5]
    assert (row["score"], row["text"]) == (84, None)


@pytest.mark.usefixtures("noon")
def test_who5_first_entry_has_no_previous_and_no_signal(isolated: Path) -> None:
    result = run("5", "4", "3", "4", "5")
    assert "прошлый" not in result.output
    assert "Сигнал" not in result.output


@pytest.mark.usefixtures("noon")
def test_who5_saves_text(isolated: Path) -> None:
    run("5", "4", "3", "4", "5", "тяжёлая неделя")
    assert who5_rows(isolated)[0]["text"] == "тяжёлая неделя"


@pytest.mark.usefixtures("noon")
def test_who5_second_entry_shows_previous_and_drop(isolated: Path) -> None:
    run("5", "4", "3", "4", "5")
    result = run("4", "3", "2", "3", "5")
    assert "WHO-5: 68 из 100 (прошлый 84, -16) - записано." in result.output
    assert "Сигнал: who5_drop" in result.output


@pytest.mark.usefixtures("noon")
def test_who5_rise_shows_plus_sign_and_no_signal(isolated: Path) -> None:
    run("2", "2", "2", "2", "2")
    result = run("4", "4", "4", "4", "4")
    assert "(прошлый 40, +40)" in result.output
    assert "Сигнал" not in result.output


@pytest.mark.usefixtures("noon")
def test_who5_all_zeros_gives_low_signal(isolated: Path) -> None:
    result = run("0", "0", "0", "0", "0")
    assert result.exit_code == 0
    assert "WHO-5: 0 из 100 - записано." in result.output
    assert "Сигнал: who5_low" in result.output
    assert who5_rows(isolated)[0]["score"] == 0


@pytest.mark.usefixtures("noon")
def test_who5_reduced_score_gives_reduced_signal(isolated: Path) -> None:
    result = run("2", "2", "2", "2", "3")
    assert "Сигнал: who5_reduced" in result.output
    assert "who5_low" not in result.output


@pytest.mark.parametrize("args", [["5", "4", "6", "4", "5"], ["--", "5", "4", "-1", "4", "5"]])
def test_who5_out_of_range_is_rejected_and_nothing_saved(isolated: Path, args: list[str]) -> None:
    # «-1» typer принимает за опцию, поэтому отрицательное передаётся после «--»
    result = run(*args)
    assert result.exit_code == 1
    assert "от 0 до 5" in result.output
    assert who5_rows(isolated) == []


def test_who5_four_arguments_is_an_error(isolated: Path) -> None:
    result = run("5", "4", "3", "4")
    assert result.exit_code != 0
    assert who5_rows(isolated) == []


@pytest.mark.parametrize("args", [["abc", "1", "1", "1", "1"], ["3.5", "1", "1", "1", "1"]])
def test_who5_non_integer_is_rejected(isolated: Path, args: list[str]) -> None:
    assert run(*args).exit_code != 0
    assert who5_rows(isolated) == []


def test_who5_at_0359_goes_to_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-15 03:59:00")
    run("5", "4", "3", "4", "5")
    assert who5_rows(isolated)[0]["date"] == TODAY


def test_who5_at_0400_goes_to_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-15 04:00:00")
    run("5", "4", "3", "4", "5")
    assert who5_rows(isolated)[0]["date"] == "2026-10-15"


def test_who5_entries_are_only_added(isolated: Path) -> None:
    run("5", "4", "3", "4", "5")
    run("1", "1", "1", "1", "1")
    assert [r["score"] for r in who5_rows(isolated)] == [84, 20]


@pytest.mark.parametrize("value", ["0", "5"])
def test_who5_bounds_are_accepted(isolated: Path, value: str) -> None:
    assert run(*[value] * 5).exit_code == 0
    assert len(who5_rows(isolated)) == 1


def test_log_who5_without_entries(isolated: Path) -> None:
    result = runner.invoke(main.app, ["log", "who5"])
    assert result.exit_code == 0
    assert "Записей нет." in result.output


@pytest.mark.usefixtures("noon")
def test_log_who5_shows_rows(isolated: Path) -> None:
    run("5", "4", "3", "4", "5", "после отпуска")
    run("1", "1", "1", "1", "3")
    lines = runner.invoke(main.app, ["log", "who5"]).output.splitlines()
    assert lines == [
        f"1  {TODAY} 12:00:00  84  5 4 3 4 5  после отпуска",
        f"2  {TODAY} 12:00:00  28  1 1 1 1 3",
    ]


@pytest.mark.usefixtures("noon")
def test_log_who5_filters_by_date(isolated: Path) -> None:
    run("5", "4", "3", "4", "5")
    conn = sqlite3.connect(isolated)
    conn.execute(
        "INSERT INTO who5_log (date, logged_at, q1, q2, q3, q4, q5, score) "
        "VALUES ('2026-10-15', '2026-10-15 12:00:00', 1, 1, 1, 1, 1, 20)"
    )
    conn.commit()
    conn.close()
    result = runner.invoke(main.app, ["log", "who5", "--date", TODAY])
    assert "5 4 3 4 5" in result.output
    assert "1 1 1 1 1" not in result.output


def test_log_who5_bad_date_fails(isolated: Path) -> None:
    result = runner.invoke(main.app, ["log", "who5", "--date", "вчера"])
    assert result.exit_code == 1
