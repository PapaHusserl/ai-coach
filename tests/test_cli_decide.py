"""coach decide add | list | done | result: очередь решений на будущее (шаг Н29, партия 2)."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from test_plan_push import workout
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.decisions import track
from ai_coach.goals.service import propose_phase
from ai_coach.store.db import open_db

runner = CliRunner()
TODAY = "2026-11-12"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("decide не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


@pytest.fixture
def noon(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{TODAY} 12:00:00")


def run(*args: str) -> Any:
    return runner.invoke(main.app, ["decide", *args])


def rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM decision_log ORDER BY id").fetchall()
    finally:
        conn.close()


def add_text(text: str = "ехать ли в субботу", *flags: str) -> None:
    assert run("add", text, *flags).exit_code == 0


def seed_phase(db: Path) -> int:
    conn = open_db(db)
    try:
        phase_id = propose_phase(conn, "База", start_date="2026-11-16")
        track(conn, "phase", phase_id, "База", "2026-11-16")
        conn.commit()
        return phase_id
    finally:
        conn.close()


def seed_workout(db: Path) -> int:
    wid = workout(db, "draft", date="2026-11-14", name="Бег лёгкий")
    conn = open_db(db)
    try:
        track(conn, "workout", wid, "Бег лёгкий", "2026-11-14")
        conn.commit()
    finally:
        conn.close()
    return wid


def phase_status(db: Path, phase_id: int) -> str:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT status FROM phases WHERE id = ?", (phase_id,)).fetchone()[0]
    finally:
        conn.close()


def workout_status(db: Path, wid: int) -> str:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT status FROM planned_workouts WHERE id = ?", (wid,)).fetchone()[
            0
        ]
    finally:
        conn.close()


# add


@pytest.mark.usefixtures("noon")
def test_add_writes_open_text_item(isolated: Path) -> None:
    result = run("add", "ехать ли в субботу")
    assert result.exit_code == 0
    found = rows(isolated)
    assert [(r["text"], r["kind"], r["status"], r["ref_id"]) for r in found] == [
        ("ехать ли в субботу", "text", "open", None)
    ]
    assert found[0]["created_at"].startswith(TODAY)


def test_add_output_names_id(isolated: Path) -> None:
    result = run("add", "решить")
    assert f"{rows(isolated)[0]['id']}" in result.output


def test_add_for_sets_target_date(isolated: Path) -> None:
    add_text("ехать", "--for", "2026-11-14")
    assert rows(isolated)[0]["target_date"] == "2026-11-14"


def test_add_without_for_has_no_target_date(isolated: Path) -> None:
    add_text()
    assert rows(isolated)[0]["target_date"] is None


def test_add_bad_date_is_error(isolated: Path) -> None:
    result = run("add", "ехать", "--for", "2026-13-01")
    assert result.exit_code == 1
    assert rows(isolated) == []


@pytest.mark.parametrize("text", ["", "   "])
def test_add_empty_text_is_error(isolated: Path, text: str) -> None:
    result = run("add", text)
    assert result.exit_code != 0
    assert rows(isolated) == []


# list


def test_list_empty(isolated: Path) -> None:
    result = run("list")
    assert result.exit_code == 0
    assert "Отложенных решений нет." in result.output


def test_list_shows_open_with_target_day_and_text(isolated: Path) -> None:
    add_text("ехать ли в субботу", "--for", "2026-11-14")
    result = run("list")
    assert "ехать ли в субботу" in result.output
    assert "2026-11-14" in result.output
    assert str(rows(isolated)[0]["id"]) in result.output


def test_list_hides_closed_without_all(isolated: Path) -> None:
    add_text("закрытое")
    run("done", "1")
    result = run("list")
    assert "закрытое" not in result.output
    assert "Отложенных решений нет." in result.output


def test_list_all_shows_closed_with_status(isolated: Path) -> None:
    add_text("закрытое")
    run("done", "1", "--no")
    result = run("list", "--all")
    assert "закрытое" in result.output
    assert "no" in result.output


def test_list_names_kind_and_object_id_for_workout_and_phase(isolated: Path) -> None:
    wid = seed_workout(isolated)
    phase_id = seed_phase(isolated)
    output = run("list").output
    assert "workout" in output
    assert "phase" in output
    assert str(wid) in output
    assert str(phase_id) in output


# done


def test_done_means_yes(isolated: Path) -> None:
    add_text()
    result = run("done", "1")
    assert result.exit_code == 0
    row = rows(isolated)[0]
    assert (row["status"], bool(row["decided_at"])) == ("yes", True)


def test_done_no_flag(isolated: Path) -> None:
    add_text()
    assert run("done", "1", "--no").exit_code == 0
    assert rows(isolated)[0]["status"] == "no"


def test_done_drop_flag(isolated: Path) -> None:
    add_text()
    assert run("done", "1", "--drop").exit_code == 0
    assert rows(isolated)[0]["status"] == "dropped"


def test_done_both_flags_is_error(isolated: Path) -> None:
    add_text()
    result = run("done", "1", "--no", "--drop")
    assert result.exit_code == 1
    assert rows(isolated)[0]["status"] == "open"


def test_done_unknown_id_is_error(isolated: Path) -> None:
    add_text()
    result = run("done", "999")
    assert result.exit_code == 1
    assert rows(isolated)[0]["status"] == "open"


def test_done_twice_says_already_decided(isolated: Path) -> None:
    add_text()
    run("done", "1")
    result = run("done", "1", "--no")
    assert result.exit_code == 1
    assert "уже решено" in result.output
    assert rows(isolated)[0]["status"] == "yes"


def test_done_phase_accepts_it(isolated: Path) -> None:
    phase_id = seed_phase(isolated)
    result = run("done", "1")
    assert result.exit_code == 0
    assert phase_status(isolated, phase_id) == "accepted"
    assert rows(isolated)[0]["status"] == "yes"


def test_done_phase_no_rejects_it(isolated: Path) -> None:
    phase_id = seed_phase(isolated)
    assert run("done", "1", "--no").exit_code == 0
    assert phase_status(isolated, phase_id) == "rejected"
    assert rows(isolated)[0]["status"] == "no"


def test_done_phase_drop_is_error_and_changes_nothing(isolated: Path) -> None:
    phase_id = seed_phase(isolated)
    result = run("done", "1", "--drop")
    assert result.exit_code == 1
    assert "принять или отклонить" in result.output
    assert phase_status(isolated, phase_id) == "proposed"
    assert rows(isolated)[0]["status"] == "open"


def test_done_phase_failed_accept_keeps_item_open(isolated: Path) -> None:
    phase_id = seed_phase(isolated)
    conn = sqlite3.connect(isolated)
    conn.execute("UPDATE phases SET status = 'rejected' WHERE id = ?", (phase_id,))
    conn.commit()
    conn.close()
    result = run("done", "1")
    assert result.exit_code == 1
    assert rows(isolated)[0]["status"] == "open"


@pytest.mark.parametrize("flags", [[], ["--no"], ["--drop"]])
def test_done_workout_is_error_with_hint_and_changes_nothing(
    isolated: Path, flags: list[str]
) -> None:
    wid = seed_workout(isolated)
    result = run("done", "1", *flags)
    assert result.exit_code == 1
    assert f"coach approve {wid}" in result.output
    assert f"coach cancel {wid}" in result.output
    assert workout_status(isolated, wid) == "draft"
    assert rows(isolated)[0]["status"] == "open"


# result


def test_result_default_is_kept(isolated: Path) -> None:
    add_text()
    run("done", "1")
    result = run("result", "1")
    assert result.exit_code == 0
    row = rows(isolated)[0]
    assert (row["result"], bool(row["result_at"])) == ("kept", True)


def test_result_missed_flag(isolated: Path) -> None:
    add_text()
    run("done", "1")
    assert run("result", "1", "--missed").exit_code == 0
    assert rows(isolated)[0]["result"] == "missed"


@pytest.mark.parametrize("closing", [["--no"], ["--drop"], None])
def test_result_not_on_yes_is_error(isolated: Path, closing: list[str] | None) -> None:
    add_text()
    if closing is not None:
        run("done", "1", *closing)
    result = run("result", "1")
    assert result.exit_code == 1
    assert rows(isolated)[0]["result"] is None


def test_result_second_time_is_error_and_keeps_first(isolated: Path) -> None:
    add_text()
    run("done", "1")
    run("result", "1")
    result = run("result", "1", "--missed")
    assert result.exit_code == 1
    assert rows(isolated)[0]["result"] == "kept"


def test_result_unknown_id_is_error(isolated: Path) -> None:
    assert run("result", "999").exit_code == 1


def test_result_on_phase_is_error(isolated: Path) -> None:
    seed_phase(isolated)
    run("done", "1")
    result = run("result", "1")
    assert result.exit_code == 1
    assert rows(isolated)[0]["result"] is None


def test_result_on_workout_is_error(isolated: Path) -> None:
    wid = seed_workout(isolated)
    conn = sqlite3.connect(isolated)
    conn.execute("UPDATE decision_log SET status = 'yes'")
    conn.commit()
    conn.close()
    result = run("result", "1")
    assert result.exit_code == 1
    assert rows(isolated)[0]["result"] is None
    assert workout_status(isolated, wid) == "draft"


def test_add_creates_only_text_kind(isolated: Path) -> None:
    add_text()
    assert {r["kind"] for r in rows(isolated)} == {"text"}


def put_row(db: Path, text: str, created_at: str, target_date: str | None) -> None:
    conn = open_db(db)
    try:
        conn.execute(
            "INSERT INTO decision_log (text, created_at, target_date) VALUES (?, ?, ?)",
            (text, created_at, target_date),
        )
        conn.commit()
    finally:
        conn.close()


# list --all: давность, порядок, статус у открытого


@pytest.mark.usefixtures("noon")
def test_list_all_shows_year_old_item(isolated: Path) -> None:
    put_row(isolated, "прошлогоднее", "2025-11-12 10:00:00", None)
    assert "прошлогоднее" in run("list", "--all").output


def test_list_all_orders_by_created_not_target_date(isolated: Path) -> None:
    put_row(isolated, "создано первым, цель поздно", "2026-11-01 10:00:00", "2026-12-31")
    put_row(isolated, "создано вторым, цель рано", "2026-11-02 10:00:00", "2026-11-05")
    output = run("list", "--all").output
    assert output.index("создано первым") < output.index("создано вторым")


def test_list_all_marks_open_item_with_status(isolated: Path) -> None:
    add_text("открытое")
    assert "[open]" in run("list", "--all").output


# done: время и одна транзакция


def test_done_writes_frozen_clock_to_decided_at(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_text()
    freeze(monkeypatch, "2026-11-12 08:45:30")
    assert run("done", "1").exit_code == 0
    assert rows(isolated)[0]["decided_at"] == "2026-11-12 08:45:30"


def test_done_phase_failing_close_rolls_back_accept(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase_id = seed_phase(isolated)

    def broken(*args: Any, **kwargs: Any) -> bool:
        raise ValueError("сломано")

    monkeypatch.setattr("ai_coach.cli.decide.close_decision", broken)
    result = run("done", "1")
    assert result.exit_code == 1
    assert phase_status(isolated, phase_id) == "proposed"
    assert rows(isolated)[0]["status"] == "open"
