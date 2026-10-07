import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """База — во временной папке; Garmin и сеть недоступны."""
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("profile и goal не должны ходить в Garmin")

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


def profile_rows(db: Path) -> list[sqlite3.Row]:
    return query(db, "SELECT * FROM profile_log ORDER BY id")


def test_profile_set_saves_manual_value(isolated: Path) -> None:
    result = runner.invoke(main.app, ["profile", "set", "height_cm", "181"])
    assert result.exit_code == 0
    row = profile_rows(isolated)[0]
    assert (row["key"], row["value"], row["source"]) == ("height_cm", "181", "manual")


def test_profile_set_accepts_text_with_spaces(isolated: Path) -> None:
    runner.invoke(main.app, ["profile", "set", "injuries", "колено болит на спусках"])
    assert profile_rows(isolated)[0]["value"] == "колено болит на спусках"


def test_profile_set_twice_keeps_history(isolated: Path) -> None:
    runner.invoke(main.app, ["profile", "set", "height_cm", "180"])
    runner.invoke(main.app, ["profile", "set", "height_cm", "181"])
    assert [r["value"] for r in profile_rows(isolated)] == ["180", "181"]


@pytest.mark.parametrize(
    "args", [["sex", "x"], ["height_cm", "abc"], ["nonsense", "1"], ["weight_goal", "boom"]]
)
def test_profile_set_bad_input_is_an_error_and_writes_nothing(
    isolated: Path, args: list[str]
) -> None:
    result = runner.invoke(main.app, ["profile", "set", *args])
    assert result.exit_code != 0
    assert profile_rows(isolated) == []


def test_unknown_key_error_lists_known_keys(isolated: Path) -> None:
    result = runner.invoke(main.app, ["profile", "set", "nonsense", "1"])
    assert "height_cm" in result.output
    assert "sex" in result.output


def test_profile_show_on_empty_database_lists_missing(isolated: Path) -> None:
    result = runner.invoke(main.app, ["profile", "show"])
    assert result.exit_code == 0
    for key in ["sex", "birth_date", "height_cm", "activity_level", "injuries"]:
        assert key in result.output


def test_profile_show_has_current_value(isolated: Path) -> None:
    runner.invoke(main.app, ["profile", "set", "equipment", "гантели до 20 кг"])
    result = runner.invoke(main.app, ["profile", "show"])
    assert "гантели до 20 кг" in result.output


def test_profile_show_has_current_value_not_old_one(isolated: Path) -> None:
    runner.invoke(main.app, ["profile", "set", "equipment", "старый инвентарь"])
    runner.invoke(main.app, ["profile", "set", "equipment", "новый инвентарь"])
    result = runner.invoke(main.app, ["profile", "show"])
    assert "новый инвентарь" in result.output
    assert "старый инвентарь" not in result.output


def test_goal_add_creates_goal_and_event(isolated: Path) -> None:
    result = runner.invoke(main.app, ["goal", "add", "Полумарафон", "--date", "2027-04-01"])
    assert result.exit_code == 0
    goal = query(isolated, "SELECT * FROM goals")[0]
    assert (goal["title"], goal["target_date"], goal["status"]) == (
        "Полумарафон",
        "2027-04-01",
        "active",
    )
    events = query(isolated, "SELECT * FROM goal_events")
    assert [e["goal_id"] for e in events] == [goal["id"]]


def test_goal_add_with_options(isolated: Path) -> None:
    runner.invoke(
        main.app,
        ["goal", "add", "Марафон", "--kind", "run", "--target", "3:30", "--priority", "2"],
    )
    goal = query(isolated, "SELECT * FROM goals")[0]
    assert (goal["kind"], goal["target"], goal["priority"]) == ("run", "3:30", 2)


def test_goal_add_empty_title_is_an_error(isolated: Path) -> None:
    result = runner.invoke(main.app, ["goal", "add", ""])
    assert result.exit_code != 0
    assert query(isolated, "SELECT * FROM goals") == []


def test_goal_add_bad_date_is_an_error(isolated: Path) -> None:
    result = runner.invoke(main.app, ["goal", "add", "Марафон", "--date", "скоро"])
    assert result.exit_code != 0
    assert query(isolated, "SELECT * FROM goals") == []


def test_goal_add_compact_date_is_an_error(isolated: Path) -> None:
    result = runner.invoke(main.app, ["goal", "add", "Марафон", "--date", "20261007"])
    assert result.exit_code != 0
    assert query(isolated, "SELECT * FROM goals") == []


def test_goal_list_shows_goals_with_ids(isolated: Path) -> None:
    runner.invoke(main.app, ["goal", "add", "Полумарафон"])
    result = runner.invoke(main.app, ["goal", "list"])
    assert result.exit_code == 0
    assert "Полумарафон" in result.output
    assert "1" in result.output


def test_goal_done_marks_done_and_adds_event(isolated: Path) -> None:
    runner.invoke(main.app, ["goal", "add", "Полумарафон"])
    result = runner.invoke(main.app, ["goal", "done", "1"])
    assert result.exit_code == 0
    assert query(isolated, "SELECT status FROM goals")[0]["status"] == "done"
    assert len(query(isolated, "SELECT * FROM goal_events")) == 2


def test_goal_cancel_marks_cancelled_and_adds_event(isolated: Path) -> None:
    runner.invoke(main.app, ["goal", "add", "Полумарафон"])
    result = runner.invoke(main.app, ["goal", "cancel", "1"])
    assert result.exit_code == 0
    assert query(isolated, "SELECT status FROM goals")[0]["status"] == "cancelled"
    assert len(query(isolated, "SELECT * FROM goal_events")) == 2


@pytest.mark.parametrize("command", ["done", "cancel"])
def test_goal_unknown_id_is_an_error(isolated: Path, command: str) -> None:
    result = runner.invoke(main.app, ["goal", command, "42"])
    assert result.exit_code != 0


def test_goal_done_for_unknown_id_changes_nothing(isolated: Path) -> None:
    runner.invoke(main.app, ["goal", "add", "Полумарафон"])
    runner.invoke(main.app, ["goal", "done", "42"])
    assert query(isolated, "SELECT status FROM goals")[0]["status"] == "active"
