"""coach slip "текст" [--at HH:MM] и coach log slip: таблица slip_log."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
TODAY = "2026-10-14"
TOMORROW = "2026-10-15"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("slip не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


@pytest.fixture
def noon(monkeypatch: pytest.MonkeyPatch) -> None:
    # freeze не переживает повторного вызова в одном тесте: время задаётся один раз
    freeze(monkeypatch, f"{TODAY} 12:00:00")


def slip_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM slip_log ORDER BY id").fetchall()
    finally:
        conn.close()


@pytest.mark.usefixtures("noon")
def test_slip_writes_one_row(isolated: Path) -> None:
    result = runner.invoke(main.app, ["slip", "злюсь на переписку"])
    assert result.exit_code == 0
    assert "Срыв записан." in result.output
    (row,) = slip_rows(isolated)
    assert (row["date"], row["logged_at"]) == (TODAY, f"{TODAY} 12:00:00")
    assert row["text"] == "злюсь на переписку"


@pytest.mark.usefixtures("noon")
def test_slip_keeps_text_verbatim(isolated: Path) -> None:
    text = "Бесит!!! «опять» дёрнули,\nвторая строка?"
    runner.invoke(main.app, ["slip", text])
    assert slip_rows(isolated)[0]["text"] == text


@pytest.mark.usefixtures("noon")
def test_slip_without_quotes_joins_words(isolated: Path) -> None:
    runner.invoke(main.app, ["slip", "злюсь", "на", "переписку"])
    assert slip_rows(isolated)[0]["text"] == "злюсь на переписку"


@pytest.mark.usefixtures("noon")
def test_slip_long_text_is_written_whole(isolated: Path) -> None:
    text = "ы" * 2000
    runner.invoke(main.app, ["slip", text])
    assert slip_rows(isolated)[0]["text"] == text


@pytest.mark.usefixtures("noon")
def test_slip_digit_is_text_not_scale(isolated: Path) -> None:
    result = runner.invoke(main.app, ["slip", "3"])
    assert result.exit_code == 0
    assert slip_rows(isolated)[0]["text"] == "3"


@pytest.mark.usefixtures("noon")
@pytest.mark.parametrize("args", [["slip"], ["slip", ""], ["slip", "   "]])
def test_slip_empty_text_is_rejected(isolated: Path, args: list[str]) -> None:
    result = runner.invoke(main.app, args)
    assert result.exit_code != 0
    assert slip_rows(isolated) == []


def test_slip_at_0359_goes_to_yesterday(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{TOMORROW} 03:59:00")
    runner.invoke(main.app, ["slip", "ночью"])
    assert slip_rows(isolated)[0]["date"] == TODAY


def test_slip_at_0400_goes_to_today(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{TOMORROW} 04:00:00")
    runner.invoke(main.app, ["slip", "утром"])
    assert slip_rows(isolated)[0]["date"] == TOMORROW


@pytest.mark.usefixtures("noon")
def test_slip_entries_are_only_added(isolated: Path) -> None:
    runner.invoke(main.app, ["slip", "раз"])
    runner.invoke(main.app, ["slip", "два"])
    assert [r["text"] for r in slip_rows(isolated)] == ["раз", "два"]


@pytest.mark.usefixtures("noon")
def test_slip_at_sets_logged_at_today(isolated: Path) -> None:
    result = runner.invoke(main.app, ["slip", "созвон", "--at", "11:20"])
    assert result.exit_code == 0
    (row,) = slip_rows(isolated)
    assert (row["date"], row["logged_at"]) == (TODAY, f"{TODAY} 11:20:00")


@pytest.mark.usefixtures("noon")
@pytest.mark.parametrize("bad", ["1420", "25:00", "abc", "14:61"])
def test_slip_bad_at_is_rejected(isolated: Path, bad: str) -> None:
    result = runner.invoke(main.app, ["slip", "созвон", "--at", bad])
    assert result.exit_code != 0
    assert slip_rows(isolated) == []


@pytest.mark.usefixtures("noon")
def test_slip_at_in_future_is_rejected(isolated: Path) -> None:
    result = runner.invoke(main.app, ["slip", "созвон", "--at", "13:00"])
    assert result.exit_code != 0
    assert "--at в будущем." in result.output
    assert slip_rows(isolated) == []


def test_slip_at_evening_after_midnight_is_yesterday(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TOMORROW} 02:00:00")
    runner.invoke(main.app, ["slip", "вечером", "--at", "23:30"])
    (row,) = slip_rows(isolated)
    assert (row["date"], row["logged_at"]) == (TODAY, f"{TODAY} 23:30:00")


def test_slip_at_small_hours_is_today_calendar_day(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TOMORROW} 02:00:00")
    runner.invoke(main.app, ["slip", "ночью", "--at", "01:30"])
    (row,) = slip_rows(isolated)
    assert (row["date"], row["logged_at"]) == (TODAY, f"{TOMORROW} 01:30:00")


def test_slip_at_future_after_midnight_is_rejected(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{TOMORROW} 02:00:00")
    result = runner.invoke(main.app, ["slip", "позже", "--at", "03:00"])
    assert result.exit_code != 0
    assert slip_rows(isolated) == []


@pytest.mark.usefixtures("noon")
def test_slip_empty_text_message() -> None:
    result = runner.invoke(main.app, ["slip", "  "])
    assert result.output.strip() == "Текст пустой."


@pytest.mark.usefixtures("noon")
def test_slip_confirmation_is_exact() -> None:
    result = runner.invoke(main.app, ["slip", "раз"])
    assert result.output.strip() == "Срыв записан."


@pytest.mark.usefixtures("noon")
def test_slip_bad_at_message_names_format() -> None:
    result = runner.invoke(main.app, ["slip", "раз", "--at", "abc"])
    assert "--at должен быть HH:MM, получено: 'abc'" in result.output


@pytest.mark.usefixtures("noon")
def test_slip_future_message_is_exact() -> None:
    result = runner.invoke(main.app, ["slip", "раз", "--at", "13:00"])
    assert result.output.strip() == "--at в будущем."


@pytest.mark.usefixtures("noon")
def test_slip_at_equal_to_now_is_accepted(isolated: Path) -> None:
    result = runner.invoke(main.app, ["slip", "сейчас", "--at", "12:00"])
    assert result.exit_code == 0
    assert slip_rows(isolated)[0]["logged_at"] == f"{TODAY} 12:00:00"


@pytest.mark.usefixtures("noon")
def test_slip_at_0400_is_today_morning(isolated: Path) -> None:
    result = runner.invoke(main.app, ["slip", "утро", "--at", "04:00"])
    assert result.exit_code == 0
    (row,) = slip_rows(isolated)
    assert (row["date"], row["logged_at"]) == (TODAY, f"{TODAY} 04:00:00")


@pytest.mark.usefixtures("noon")
def test_log_slip_empty() -> None:
    result = runner.invoke(main.app, ["log", "slip"])
    assert result.exit_code == 0
    assert "Записей нет." in result.output


@pytest.mark.usefixtures("noon")
def test_log_slip_prints_id_time_text() -> None:
    runner.invoke(main.app, ["slip", "раз", "--at", "09:00"])
    runner.invoke(main.app, ["slip", "два"])
    lines = runner.invoke(main.app, ["log", "slip"]).output.strip().splitlines()
    assert lines == [f"1  {TODAY} 09:00:00  раз", f"2  {TODAY} 12:00:00  два"]


@pytest.mark.usefixtures("noon")
def test_log_slip_newline_shown_as_space() -> None:
    runner.invoke(main.app, ["slip", "строка\nвторая"])
    assert "строка вторая" in runner.invoke(main.app, ["log", "slip"]).output


@pytest.mark.usefixtures("noon")
def test_log_slip_filters_by_date() -> None:
    runner.invoke(main.app, ["slip", "сегодня"])
    other = runner.invoke(main.app, ["log", "slip", "--date", "2026-10-13"])
    assert "Записей нет." in other.output
    same = runner.invoke(main.app, ["log", "slip", "--date", TODAY])
    assert "сегодня" in same.output


@pytest.mark.usefixtures("noon")
def test_log_slip_bad_date_is_rejected() -> None:
    result = runner.invoke(main.app, ["log", "slip", "--date", "вчера"])
    assert result.exit_code != 0
