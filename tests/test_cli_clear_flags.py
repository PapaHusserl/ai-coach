import json
import sqlite3
import tomllib
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.cli import sport_nutrition as sport_cli

runner = CliRunner()
SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"
QLTY = Path(__file__).resolve().parent.parent / ".qlty" / "qlty.toml"
MED = ("--kind", "vitamin", "--dose", "25", "--unit", "mcg", "--schedule", "daily")
THREE_FILES = (
    "src/ai_coach/cli/recipes.py",
    "src/ai_coach/cli/sport_nutrition.py",
    "src/ai_coach/cli/meds.py",
)


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("clear-флаги не должны ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def first_row(db: Path, table: str) -> sqlite3.Row:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()[0]
    finally:
        conn.close()


def add_protocol() -> str:
    run(
        "protocol",
        "add",
        "гель",
        "--phase",
        "during",
        "--carbs",
        "60",
        "--sport",
        "run",
        "--note",
        "заметка",
    )
    return str(first_row(Path(".").resolve() / "coach.db", "nutrition_protocol")["id"])


def add_supplement() -> str:
    run(
        "supplement",
        "add",
        "креатин",
        "--dose",
        "5",
        "--unit",
        "g",
        "--schedule",
        "daily",
        "--time-note",
        "утром",
        "--note",
        "заметка",
    )
    return str(first_row(Path(".").resolve() / "coach.db", "supplement")["id"])


def add_med() -> str:
    run(
        "med",
        "add",
        "витамин D",
        *MED,
        "--start",
        "2026-10-01",
        "--time-note",
        "с едой",
        "--note",
        "заметка",
    )
    return str(first_row(Path(".").resolve() / "coach.db", "med_course")["id"])


# --- protocol edit ---


def test_protocol_clear_sport_sets_null(isolated: Path) -> None:
    rid = add_protocol()
    assert run("protocol", "edit", rid, "--clear-sport").exit_code == 0
    row = first_row(isolated, "nutrition_protocol")
    assert row["sport"] is None
    assert row["note"] == "заметка"


def test_protocol_clear_note_sets_null(isolated: Path) -> None:
    rid = add_protocol()
    assert run("protocol", "edit", rid, "--clear-note").exit_code == 0
    row = first_row(isolated, "nutrition_protocol")
    assert row["note"] is None
    assert row["sport"] == "run"


def test_protocol_clear_flags_with_other_option(isolated: Path) -> None:
    rid = add_protocol()
    result = run("protocol", "edit", rid, "--clear-sport", "--clear-note", "--carbs", "90")
    assert result.exit_code == 0
    row = first_row(isolated, "nutrition_protocol")
    assert (row["sport"], row["note"], row["carbs_g"]) == (None, None, 90)


def test_protocol_clear_sport_with_sport_fails(isolated: Path) -> None:
    rid = add_protocol()
    result = run("protocol", "edit", rid, "--sport", "bike", "--clear-sport")
    assert result.exit_code == 1
    assert "--sport и --clear-sport вместе нельзя." in result.output
    assert first_row(isolated, "nutrition_protocol")["sport"] == "run"


def test_protocol_clear_note_with_note_fails(isolated: Path) -> None:
    rid = add_protocol()
    result = run("protocol", "edit", rid, "--note", "новая", "--clear-note")
    assert result.exit_code == 1
    assert "--note и --clear-note вместе нельзя." in result.output
    assert first_row(isolated, "nutrition_protocol")["note"] == "заметка"


def test_protocol_clear_flag_alone_is_not_nothing_to_change(isolated: Path) -> None:
    rid = add_protocol()
    result = run("protocol", "edit", rid, "--clear-note")
    assert "Нечего менять" not in result.output
    assert result.exit_code == 0


def test_protocol_edit_without_options_still_fails(isolated: Path) -> None:
    rid = add_protocol()
    result = run("protocol", "edit", rid)
    assert result.exit_code == 1
    assert "Нечего менять" in result.output


def test_protocol_clear_unknown_fails_with_text(isolated: Path) -> None:
    result = run("protocol", "edit", "99", "--clear-sport")
    assert result.exit_code == 1
    assert "99" in result.output


def test_protocol_sport_help_mentions_clear_flag() -> None:
    assert "--clear-sport" in sport_cli.SPORT_EDIT_HELP
    assert "сбросить нельзя" not in sport_cli.SPORT_EDIT_HELP


# --- supplement edit ---


def test_supplement_clear_time_note_sets_null(isolated: Path) -> None:
    rid = add_supplement()
    assert run("supplement", "edit", rid, "--clear-time-note").exit_code == 0
    row = first_row(isolated, "supplement")
    assert row["time_note"] is None
    assert row["note"] == "заметка"


def test_supplement_clear_note_sets_null(isolated: Path) -> None:
    rid = add_supplement()
    assert run("supplement", "edit", rid, "--clear-note").exit_code == 0
    row = first_row(isolated, "supplement")
    assert row["note"] is None
    assert row["time_note"] == "утром"


def test_supplement_clear_time_note_with_time_note_fails(isolated: Path) -> None:
    rid = add_supplement()
    result = run("supplement", "edit", rid, "--time-note", "вечером", "--clear-time-note")
    assert result.exit_code == 1
    assert "--time-note и --clear-time-note вместе нельзя." in result.output
    assert first_row(isolated, "supplement")["time_note"] == "утром"


def test_supplement_clear_note_with_note_fails(isolated: Path) -> None:
    rid = add_supplement()
    result = run("supplement", "edit", rid, "--note", "новая", "--clear-note")
    assert result.exit_code == 1
    assert "--note и --clear-note вместе нельзя." in result.output


def test_supplement_clear_flag_alone_is_not_nothing_to_change(isolated: Path) -> None:
    rid = add_supplement()
    result = run("supplement", "edit", rid, "--clear-note")
    assert "Нечего менять" not in result.output
    assert result.exit_code == 0


def test_supplement_clear_unknown_fails_with_text(isolated: Path) -> None:
    result = run("supplement", "edit", "99", "--clear-note")
    assert result.exit_code == 1
    assert "99" in result.output


# --- med edit ---


def test_med_clear_time_note_sets_null(isolated: Path) -> None:
    rid = add_med()
    assert run("med", "edit", rid, "--clear-time-note").exit_code == 0
    row = first_row(isolated, "med_course")
    assert row["time_note"] is None
    assert row["note"] == "заметка"


def test_med_clear_note_sets_null(isolated: Path) -> None:
    rid = add_med()
    assert run("med", "edit", rid, "--clear-note").exit_code == 0
    row = first_row(isolated, "med_course")
    assert row["note"] is None
    assert row["time_note"] == "с едой"


def test_med_clear_time_note_with_time_note_fails(isolated: Path) -> None:
    rid = add_med()
    result = run("med", "edit", rid, "--time-note", "вечером", "--clear-time-note")
    assert result.exit_code == 1
    assert "--time-note и --clear-time-note вместе нельзя." in result.output
    assert first_row(isolated, "med_course")["time_note"] == "с едой"


def test_med_clear_note_with_note_fails(isolated: Path) -> None:
    rid = add_med()
    result = run("med", "edit", rid, "--note", "новая", "--clear-note")
    assert result.exit_code == 1
    assert "--note и --clear-note вместе нельзя." in result.output


def test_med_clear_flag_alone_is_not_nothing_to_change(isolated: Path) -> None:
    rid = add_med()
    result = run("med", "edit", rid, "--clear-time-note")
    assert "Нечего менять" not in result.output
    assert result.exit_code == 0


def test_med_clear_unknown_fails_with_text(isolated: Path) -> None:
    result = run("med", "edit", "99", "--clear-note")
    assert result.exit_code == 1
    assert "99" in result.output


# --- med edit --no-end ---


def test_med_no_end_sets_end_date_null(isolated: Path) -> None:
    run("med", "add", "витамин D", *MED, "--start", "2026-10-01", "--end", "2026-10-31")
    rid = str(first_row(isolated, "med_course")["id"])
    assert run("med", "edit", rid, "--no-end").exit_code == 0
    assert first_row(isolated, "med_course")["end_date"] is None


def test_med_no_end_course_is_visible_in_a_year(isolated: Path) -> None:
    run("med", "add", "витамин D", *MED, "--start", "2026-10-01", "--end", "2026-10-31")
    rid = str(first_row(isolated, "med_course")["id"])
    far = (date.today() + timedelta(days=365)).isoformat()
    assert "витамин D" not in run("med", "list", "--date", far).output
    run("med", "edit", rid, "--no-end")
    assert "витамин D" in run("med", "list", "--date", far).output


def test_med_no_end_with_end_fails(isolated: Path) -> None:
    run("med", "add", "витамин D", *MED, "--start", "2026-10-01", "--end", "2026-10-31")
    rid = str(first_row(isolated, "med_course")["id"])
    result = run("med", "edit", rid, "--end", "2026-11-30", "--no-end")
    assert result.exit_code == 1
    assert "--end и --no-end вместе нельзя." in result.output
    assert first_row(isolated, "med_course")["end_date"] == "2026-10-31"


def test_med_no_end_on_open_ended_course_is_fine(isolated: Path) -> None:
    rid = add_med()
    result = run("med", "edit", rid, "--no-end")
    assert result.exit_code == 0
    assert first_row(isolated, "med_course")["end_date"] is None


def test_med_no_end_unknown_fails_with_text(isolated: Path) -> None:
    result = run("med", "edit", "99", "--no-end")
    assert result.exit_code == 1
    assert "99" in result.output


# --- allow ---


@pytest.mark.parametrize("command", ["protocol", "supplement", "med"])
def test_edit_commands_are_not_in_allow(command: str) -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert not [r for r in allow if f"coach {command} edit" in r]


# --- qlty guard ---


@pytest.mark.parametrize("path", THREE_FILES)
def test_qlty_does_not_exclude_cli_file(path: str) -> None:
    config = tomllib.loads(QLTY.read_text())
    assert path not in config["exclude_patterns"]


def test_qlty_global_parameters_threshold_is_15() -> None:
    config = tomllib.loads(QLTY.read_text())
    assert config["smells"]["function_parameters"]["threshold"] == 15
