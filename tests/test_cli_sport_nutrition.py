import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"
CARBS = ["--carbs", "60"]


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("protocol/supplement не должны ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def table_rows(db: Path, table: str) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def protocol_rows(db: Path) -> list[sqlite3.Row]:
    return table_rows(db, "nutrition_protocol")


def supplement_rows(db: Path) -> list[sqlite3.Row]:
    return table_rows(db, "supplement")


def add_protocol(name: str = "гель", phase: str = "during", *extra: str) -> Any:
    return run("protocol", "add", name, "--phase", phase, *(extra or CARBS))


def add_supplement(name: str = "креатин", *extra: str) -> Any:
    return run(
        "supplement", "add", name, *(extra or ("--dose", "5", "--unit", "g", "--schedule", "daily"))
    )


# --- protocol add ---


def test_protocol_add_saves_row(isolated: Path) -> None:
    result = add_protocol("гель", "during")
    assert result.exit_code == 0
    row = protocol_rows(isolated)[0]
    assert (row["name"], row["phase"], row["sport"], row["carbs_g"]) == ("гель", "during", None, 60)
    assert row["deleted_at"] is None


def test_protocol_add_prints_id(isolated: Path) -> None:
    result = add_protocol()
    assert str(protocol_rows(isolated)[0]["id"]) in result.output


def test_protocol_add_with_all_options(isolated: Path) -> None:
    result = run(
        "protocol", "add", "бег до", "--phase", "before", "--sport", "run",
        "--min-duration", "45", "--offset", "60", "--carbs", "50", "--protein", "10",
        "--fluid", "400", "--sodium", "200", "--note", "за час",
    )  # fmt: skip
    assert result.exit_code == 0
    row = protocol_rows(isolated)[0]
    assert (row["sport"], row["min_duration_min"], row["offset_min"]) == ("run", 45, 60)
    assert (row["carbs_g"], row["protein_g"], row["fluid_ml"], row["sodium_mg"]) == (
        50,
        10,
        400,
        200,
    )
    assert row["note"] == "за час"


def test_protocol_add_with_decimal_comma(isolated: Path) -> None:
    assert add_protocol("гель", "during", "--carbs", "42,5").exit_code == 0
    assert protocol_rows(isolated)[0]["carbs_g"] == 42.5


def test_protocol_add_only_fluid_is_not_empty(isolated: Path) -> None:
    assert add_protocol("вода", "during", "--fluid", "500").exit_code == 0


@pytest.mark.parametrize("phase", ["always", "", "До"])
def test_protocol_add_bad_phase_fails_with_code_1(isolated: Path, phase: str) -> None:
    assert add_protocol("гель", phase).exit_code == 1
    assert protocol_rows(isolated) == []


def test_protocol_add_without_phase_fails(isolated: Path) -> None:
    assert run("protocol", "add", "гель", *CARBS).exit_code != 0
    assert protocol_rows(isolated) == []


def test_protocol_add_bad_sport_fails_with_code_1(isolated: Path) -> None:
    assert add_protocol("гель", "during", "--sport", "yoga", *CARBS).exit_code == 1
    assert protocol_rows(isolated) == []


@pytest.mark.parametrize("option", ["--carbs", "--protein", "--fluid", "--sodium"])
@pytest.mark.parametrize("value", ["-1", "много"])
def test_protocol_add_bad_amount_fails_with_code_1(isolated: Path, option: str, value: str) -> None:
    result = add_protocol("гель", "during", "--carbs", "60", option, value)
    assert result.exit_code == 1
    assert protocol_rows(isolated) == []


@pytest.mark.parametrize("option", ["--min-duration", "--offset"])
def test_protocol_add_bad_minutes_fails_with_code_1(isolated: Path, option: str) -> None:
    assert add_protocol("гель", "during", *CARBS, option, "много").exit_code == 1
    assert protocol_rows(isolated) == []


def test_protocol_add_empty_protocol_fails_with_code_1(isolated: Path) -> None:
    assert run("protocol", "add", "пустой", "--phase", "during").exit_code == 1
    assert add_protocol("нули", "during", "--carbs", "0", "--fluid", "0").exit_code == 1
    assert protocol_rows(isolated) == []


@pytest.mark.parametrize("name", ["  ", "123"])
def test_protocol_add_bad_name_fails_with_code_1(isolated: Path, name: str) -> None:
    assert add_protocol(name).exit_code == 1
    assert protocol_rows(isolated) == []


def test_protocol_add_duplicate_name_fails_with_code_1(isolated: Path) -> None:
    add_protocol("гель")
    assert add_protocol("Гель").exit_code == 1
    assert len(protocol_rows(isolated)) == 1


def test_protocol_add_options_with_equals_sign(isolated: Path) -> None:
    result = run("protocol", "add", "гель", "--phase=during", "--carbs=60")
    assert result.exit_code == 0


# --- protocol list / show ---


def test_protocol_list_on_empty_database(isolated: Path) -> None:
    assert run("protocol", "list").exit_code == 0


def test_protocol_list_shows_names_and_phase(isolated: Path) -> None:
    add_protocol("гель", "during")
    add_protocol("шейк", "after", "--protein", "25")
    result = run("protocol", "list")
    assert result.exit_code == 0
    for part in ["гель", "шейк", "during", "after"]:
        assert part in result.output


def test_protocol_show_by_id_and_by_name(isolated: Path) -> None:
    add_protocol("Гель", "during", "--carbs", "60", "--note", "заметка")
    rid = str(protocol_rows(isolated)[0]["id"])
    for key in (rid, "гель"):
        result = run("protocol", "show", key)
        assert result.exit_code == 0
        for part in ["Гель", "during", "60", "заметка"]:
            assert part in result.output


def test_protocol_show_unknown_fails_with_code_1(isolated: Path) -> None:
    add_protocol("гель")
    assert run("protocol", "show", "борщ").exit_code == 1
    assert run("protocol", "show", "99").exit_code == 1


# --- protocol edit / delete ---


def test_protocol_edit_changes_amount(isolated: Path) -> None:
    add_protocol("гель")
    rid = str(protocol_rows(isolated)[0]["id"])
    assert run("protocol", "edit", rid, "--carbs", "90").exit_code == 0
    assert protocol_rows(isolated)[0]["carbs_g"] == 90


def test_protocol_edit_bad_value_fails_and_keeps_data(isolated: Path) -> None:
    add_protocol("гель")
    rid = str(protocol_rows(isolated)[0]["id"])
    assert run("protocol", "edit", rid, "--carbs", "-5").exit_code == 1
    assert protocol_rows(isolated)[0]["carbs_g"] == 60


def test_protocol_edit_unknown_fails_with_code_1(isolated: Path) -> None:
    assert run("protocol", "edit", "99", "--carbs", "5").exit_code == 1


def test_protocol_delete_marks_row_and_hides_from_list(isolated: Path) -> None:
    add_protocol("гель")
    rid = str(protocol_rows(isolated)[0]["id"])
    assert run("protocol", "delete", rid).exit_code == 0
    assert protocol_rows(isolated)[0]["deleted_at"] is not None
    assert "гель" not in run("protocol", "list").output
    assert run("protocol", "show", rid).exit_code == 1


def test_protocol_delete_twice_or_unknown_fails_with_code_1(isolated: Path) -> None:
    add_protocol("гель")
    rid = str(protocol_rows(isolated)[0]["id"])
    run("protocol", "delete", rid)
    assert run("protocol", "delete", rid).exit_code == 1
    assert run("protocol", "delete", "99").exit_code == 1


# --- supplement ---


def test_supplement_add_saves_row(isolated: Path) -> None:
    result = run(
        "supplement", "add", "креатин", "--dose", "5", "--unit", "g", "--schedule", "daily",
        "--time-note", "утром", "--note", "с водой",
    )  # fmt: skip
    assert result.exit_code == 0
    row = supplement_rows(isolated)[0]
    assert (row["name"], row["dose"], row["unit"], row["schedule"]) == ("креатин", 5, "g", "daily")
    assert (row["time_note"], row["note"]) == ("утром", "с водой")
    assert str(row["id"]) in result.output


@pytest.mark.parametrize("schedule", ["daily", "training_day", "before", "after"])
def test_supplement_add_schedules(isolated: Path, schedule: str) -> None:
    result = add_supplement("добавка", "--dose", "1", "--unit", "mg", "--schedule", schedule)
    assert result.exit_code == 0


@pytest.mark.parametrize("dose", ["0", "-1", "много"])
def test_supplement_add_bad_dose_fails_with_code_1(isolated: Path, dose: str) -> None:
    result = add_supplement("креатин", "--dose", dose, "--unit", "g", "--schedule", "daily")
    assert result.exit_code == 1
    assert supplement_rows(isolated) == []


def test_supplement_add_bad_unit_fails_with_code_1(isolated: Path) -> None:
    result = add_supplement("креатин", "--dose", "5", "--unit", "kg", "--schedule", "daily")
    assert result.exit_code == 1
    assert supplement_rows(isolated) == []


def test_supplement_add_bad_schedule_fails_with_code_1(isolated: Path) -> None:
    result = add_supplement("креатин", "--dose", "5", "--unit", "g", "--schedule", "weekly")
    assert result.exit_code == 1
    assert supplement_rows(isolated) == []


@pytest.mark.parametrize("name", ["  ", "123"])
def test_supplement_add_bad_name_fails_with_code_1(isolated: Path, name: str) -> None:
    assert add_supplement(name).exit_code == 1
    assert supplement_rows(isolated) == []


def test_supplement_add_duplicate_name_fails_with_code_1(isolated: Path) -> None:
    add_supplement("креатин")
    assert add_supplement("Креатин").exit_code == 1
    assert len(supplement_rows(isolated)) == 1


def test_supplement_list_and_show(isolated: Path) -> None:
    add_supplement("креатин")
    rid = str(supplement_rows(isolated)[0]["id"])
    assert "креатин" in run("supplement", "list").output
    for key in (rid, "креатин"):
        result = run("supplement", "show", key)
        assert result.exit_code == 0
        assert "креатин" in result.output
    assert run("supplement", "show", "99").exit_code == 1


def test_supplement_list_on_empty_database(isolated: Path) -> None:
    assert run("supplement", "list").exit_code == 0


def test_supplement_edit_and_delete(isolated: Path) -> None:
    add_supplement("креатин")
    rid = str(supplement_rows(isolated)[0]["id"])
    assert run("supplement", "edit", rid, "--dose", "3").exit_code == 0
    assert supplement_rows(isolated)[0]["dose"] == 3
    assert run("supplement", "edit", rid, "--dose", "0").exit_code == 1
    assert run("supplement", "delete", rid).exit_code == 0
    assert supplement_rows(isolated)[0]["deleted_at"] is not None
    assert run("supplement", "delete", rid).exit_code == 1
    assert "креатин" not in run("supplement", "list").output


# --- allow ---


@pytest.mark.parametrize("command", ["protocol", "supplement"])
def test_settings_allow_add_list_show_but_not_edit_delete(command: str) -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    for sub in ("add", "list", "show"):
        assert f"Bash(uv run coach {command} {sub}:*)" in allow
    assert not [r for r in allow if f"{command} edit" in r or f"{command} delete" in r]
    assert f"Bash(uv run coach {command}:*)" not in allow
    assert "Bash(uv run coach:*)" not in allow
