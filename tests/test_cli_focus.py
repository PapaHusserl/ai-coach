"""coach focus <фокус> <усталость> <усилие> ["текст"] и coach log focus: таблица focus_log."""

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
        raise AssertionError("focus не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


@pytest.fixture
def noon(monkeypatch: pytest.MonkeyPatch) -> None:
    # freeze не переживает повторного вызова в одном тесте: время задаётся один раз
    freeze(monkeypatch, f"{TODAY} 12:00:00")


def focus_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM focus_log ORDER BY id").fetchall()
    finally:
        conn.close()


@pytest.mark.usefixtures("noon")
def test_focus_writes_one_row(isolated: Path) -> None:
    result = runner.invoke(main.app, ["focus", "4", "2", "3"])
    assert result.exit_code == 0
    assert "Оценка записана" in result.output
    (row,) = focus_rows(isolated)
    assert (row["date"], row["logged_at"]) == (TODAY, f"{TODAY} 12:00:00")
    assert (row["focus"], row["fatigue"], row["effort"], row["text"]) == (4, 2, 3, None)


@pytest.mark.usefixtures("noon")
def test_focus_saves_text(isolated: Path) -> None:
    runner.invoke(main.app, ["focus", "4", "2", "3", "устал после созвона"])
    assert focus_rows(isolated)[0]["text"] == "устал после созвона"


def test_focus_at_0359_goes_to_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-15 03:59:00")
    runner.invoke(main.app, ["focus", "4", "2", "3"])
    assert focus_rows(isolated)[0]["date"] == TODAY


def test_focus_at_0400_goes_to_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-15 04:00:00")
    runner.invoke(main.app, ["focus", "4", "2", "3"])
    assert focus_rows(isolated)[0]["date"] == "2026-10-15"


def test_focus_entries_are_only_added(isolated: Path) -> None:
    runner.invoke(main.app, ["focus", "4", "2", "3"])
    runner.invoke(main.app, ["focus", "1", "5", "5"])
    assert [r["focus"] for r in focus_rows(isolated)] == [4, 1]


@pytest.mark.parametrize(
    "args",
    [
        ["0", "2", "3"],
        ["6", "2", "3"],
        ["4", "0", "3"],
        ["4", "6", "3"],
        ["4", "2", "0"],
        ["4", "2", "6"],
        ["abc", "2", "3"],
        ["3.5", "2", "3"],
        ["4", "2"],
    ],
)
def test_bad_values_are_rejected_and_nothing_saved(isolated: Path, args: list[str]) -> None:
    result = runner.invoke(main.app, ["focus", *args])
    assert result.exit_code != 0
    assert focus_rows(isolated) == []


@pytest.mark.parametrize("value", ["1", "5"])
def test_bounds_are_accepted(isolated: Path, value: str) -> None:
    assert runner.invoke(main.app, ["focus", value, value, value]).exit_code == 0
    assert len(focus_rows(isolated)) == 1


def test_log_focus_without_entries(isolated: Path) -> None:
    result = runner.invoke(main.app, ["log", "focus"])
    assert result.exit_code == 0
    assert "Записей нет." in result.output


@pytest.mark.usefixtures("noon")
def test_log_focus_shows_rows(isolated: Path) -> None:
    runner.invoke(main.app, ["focus", "4", "2", "3", "после созвона"])
    runner.invoke(main.app, ["focus", "2", "4", "5"])
    lines = runner.invoke(main.app, ["log", "focus"]).output.splitlines()
    assert lines == [
        f"1  {TODAY} 12:00:00  4/2/3  после созвона",
        f"2  {TODAY} 12:00:00  2/4/5",
    ]


@pytest.mark.usefixtures("noon")
def test_log_focus_filters_by_date(isolated: Path) -> None:
    runner.invoke(main.app, ["focus", "4", "2", "3"])
    conn = sqlite3.connect(isolated)
    conn.execute(
        "INSERT INTO focus_log (date, logged_at, focus, fatigue, effort) "
        "VALUES ('2026-10-15', '2026-10-15 12:00:00', 1, 1, 1)"
    )
    conn.commit()
    conn.close()
    result = runner.invoke(main.app, ["log", "focus", "--date", TODAY])
    assert "4/2/3" in result.output
    assert "1/1/1" not in result.output


def test_log_focus_bad_date_fails(isolated: Path) -> None:
    assert runner.invoke(main.app, ["log", "focus", "--date", "вчера"]).exit_code != 0
