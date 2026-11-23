"""coach report add | list | done: очередь отчётов тренера (шаг Н34, партия 1)."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
TODAY = "2026-11-24"
NO_NUMBERS = "В отчёте не должно быть чисел: опиши случай без значений."


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("report не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


@pytest.fixture
def noon(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")


def run(*args: str) -> Any:
    return runner.invoke(main.app, ["report", *args])


def rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM system_report ORDER BY id").fetchall()
    finally:
        conn.close()


def add_text(text: str = "справка не знает про индекс бурь") -> None:
    assert run("add", text).exit_code == 0


# add


@pytest.mark.usefixtures("noon")
def test_add_writes_open_report(isolated: Path) -> None:
    text = "утром сигнала болезни нет, хотя пульс покоя выше нормы"
    result = run("add", text)
    assert result.exit_code == 0
    assert result.output.strip() == "Отчёт 1 записан."
    [row] = rows(isolated)
    assert (row["text"], row["status"], row["backlog"], row["closed_at"]) == (
        text,
        "open",
        None,
        None,
    )
    assert row["created_at"].startswith(TODAY)


@pytest.mark.parametrize("text", ["", "  "])
def test_add_empty_text_is_error(isolated: Path, text: str) -> None:
    result = run("add", text)
    assert result.exit_code == 1
    assert "Текст отчёта не должен быть пустым." in result.output
    assert rows(isolated) == []


@pytest.mark.parametrize(
    "text",
    [
        "пульс покоя 50",
        "HRV=40",
        "вес 70,5",
        "оценка 2 из 5",
        "точка 10.5 20.5",
        "13 ноября",
        "пульс50",
    ],
)
def test_add_with_number_is_refused(isolated: Path, text: str) -> None:
    result = run("add", text)
    assert result.exit_code == 1
    assert NO_NUMBERS in result.output
    assert rows(isolated) == []


@pytest.mark.parametrize("text", ["get_who5 не отдаёт дату", "coach log who5 пуст"])
def test_add_names_with_digit_are_allowed(isolated: Path, text: str) -> None:
    result = run("add", text)
    assert result.exit_code == 0
    assert [r["text"] for r in rows(isolated)] == [text]


def test_add_600_chars_is_written(isolated: Path) -> None:
    text = "а" * 600
    assert run("add", text).exit_code == 0
    assert [r["text"] for r in rows(isolated)] == [text]


def test_add_601_chars_is_refused(isolated: Path) -> None:
    result = run("add", "а" * 601)
    assert result.exit_code == 1
    assert "Отчёт длиннее 600 символов: сократи до сути." in result.output
    assert rows(isolated) == []


# list


def test_list_empty(isolated: Path) -> None:
    result = run("list")
    assert result.exit_code == 0
    assert result.output.strip() == "Открытых отчётов нет."


@pytest.mark.usefixtures("noon")
def test_list_shows_open_in_id_order(isolated: Path) -> None:
    add_text("первый случай")
    add_text("второй случай")
    result = run("list")
    assert result.exit_code == 0
    assert result.output.splitlines() == [
        f"1  {TODAY} 12:00:00  первый случай",
        f"2  {TODAY} 12:00:00  второй случай",
    ]


def test_list_hides_closed_without_all(isolated: Path) -> None:
    add_text("первый случай")
    add_text("второй случай")
    assert run("done", "1", "--backlog", "170").exit_code == 0
    result = run("list")
    assert "второй случай" in result.output
    assert "первый случай" not in result.output


@pytest.mark.usefixtures("noon")
def test_list_all_marks_status(isolated: Path) -> None:
    add_text("первый случай")
    add_text("второй случай")
    add_text("третий случай")
    assert run("done", "1", "--backlog", "170").exit_code == 0
    assert run("done", "2", "--drop").exit_code == 0
    result = run("list", "--all")
    assert result.output.splitlines() == [
        f"1  {TODAY} 12:00:00  первый случай  [done BACKLOG 170]",
        f"2  {TODAY} 12:00:00  второй случай  [dropped]",
        f"3  {TODAY} 12:00:00  третий случай  [open]",
    ]


# done


@pytest.mark.usefixtures("noon")
def test_done_backlog_closes_with_number(isolated: Path) -> None:
    add_text()
    result = run("done", "1", "--backlog", "170")
    assert result.exit_code == 0
    assert result.output.strip() == "Отчёт 1: в беклоге, пункт 170."
    [row] = rows(isolated)
    assert (row["status"], row["backlog"]) == ("done", 170)
    assert row["closed_at"].startswith(TODAY)


@pytest.mark.usefixtures("noon")
def test_done_drop_closes_without_number(isolated: Path) -> None:
    add_text()
    add_text("другой случай")
    result = run("done", "2", "--drop")
    assert result.exit_code == 0
    assert result.output.strip() == "Отчёт 2: снят."
    first, second = rows(isolated)
    assert (second["status"], second["backlog"]) == ("dropped", None)
    assert second["closed_at"].startswith(TODAY)
    assert (first["status"], first["closed_at"]) == ("open", None)


def test_done_without_flags_is_error(isolated: Path) -> None:
    add_text()
    result = run("done", "1")
    assert result.exit_code == 1
    assert "Нужен --backlog <номер пункта> или --drop." in result.output
    assert rows(isolated)[0]["status"] == "open"


def test_done_both_flags_is_error(isolated: Path) -> None:
    add_text()
    result = run("done", "1", "--backlog", "170", "--drop")
    assert result.exit_code == 1
    assert "--backlog и --drop вместе нельзя." in result.output
    assert rows(isolated)[0]["status"] == "open"


def test_done_unknown_id(isolated: Path) -> None:
    result = run("done", "99", "--drop")
    assert result.exit_code == 1
    assert "Отчёта 99 нет." in result.output


def test_done_twice_keeps_first_result(isolated: Path) -> None:
    add_text()
    assert run("done", "1", "--backlog", "170").exit_code == 0
    result = run("done", "1", "--drop")
    assert result.exit_code == 1
    assert "Отчёт 1: уже закрыт (done)." in result.output
    [row] = rows(isolated)
    assert (row["status"], row["backlog"]) == ("done", 170)


def test_done_after_drop_names_dropped(isolated: Path) -> None:
    add_text()
    assert run("done", "1", "--drop").exit_code == 0
    result = run("done", "1", "--backlog", "170")
    assert result.exit_code == 1
    assert "Отчёт 1: уже закрыт (dropped)." in result.output
    assert rows(isolated)[0]["status"] == "dropped"
