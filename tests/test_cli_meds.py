import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"
TODAY = date.today()
DOSE = ("--kind", "vitamin", "--dose", "25", "--unit", "mcg", "--schedule", "daily")


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("med не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def med_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM med_course ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def add_med(name: str = "витамин D", *extra: str) -> Any:
    args = extra or DOSE
    if "--start" not in args:
        args = (*args, "--start", "2026-10-01")
    return run("med", "add", name, *args)


def day(shift: int) -> str:
    return (TODAY + timedelta(days=shift)).isoformat()


# --- add ---


def test_add_saves_row_and_prints_id(isolated: Path) -> None:
    result = run(
        "med", "add", "витамин D", *DOSE, "--start", "2026-10-01", "--end", "2026-10-31",
        "--time-note", "с едой", "--note", "по инструкции",
    )  # fmt: skip
    assert result.exit_code == 0
    row = med_rows(isolated)[0]
    assert (row["name"], row["kind"], row["dose"], row["unit"]) == (
        "витамин D",
        "vitamin",
        25,
        "mcg",
    )
    assert (row["schedule"], row["start_date"], row["end_date"]) == (
        "daily",
        "2026-10-01",
        "2026-10-31",
    )
    assert (row["time_note"], row["note"], row["deleted_at"]) == ("с едой", "по инструкции", None)
    assert str(row["id"]) in result.output


def test_add_without_end_is_open_ended(isolated: Path) -> None:
    assert add_med("витамин D", *DOSE, "--start", "2026-10-01").exit_code == 0
    assert med_rows(isolated)[0]["end_date"] is None


def test_add_without_start_fails_with_text(isolated: Path) -> None:
    result = run("med", "add", "витамин D", *DOSE)
    assert result.exit_code == 1
    assert "--start обязателен" in result.output
    assert med_rows(isolated) == []


@pytest.mark.parametrize("kind", ["vitamin", "mineral", "electrolyte", "otc"])
def test_add_kinds(isolated: Path, kind: str) -> None:
    result = add_med(
        "средство", "--kind", kind, "--dose", "1", "--unit", "mg", "--schedule", "daily"
    )
    assert result.exit_code == 0


@pytest.mark.parametrize("unit", ["mg", "mcg", "iu", "g", "ml", "pcs"])
def test_add_units(isolated: Path, unit: str) -> None:
    result = add_med(
        "средство", "--kind", "otc", "--dose", "1", "--unit", unit, "--schedule", "daily"
    )
    assert result.exit_code == 0


@pytest.mark.parametrize("schedule", ["daily", "training_day", "before", "after"])
def test_add_schedules(isolated: Path, schedule: str) -> None:
    result = add_med(
        "средство", "--kind", "otc", "--dose", "1", "--unit", "mg", "--schedule", schedule
    )
    assert result.exit_code == 0


def test_add_with_decimal_comma(isolated: Path) -> None:
    result = add_med(
        "витамин D", "--kind", "vitamin", "--dose", "0,5", "--unit", "mg", "--schedule", "daily"
    )
    assert result.exit_code == 0
    assert med_rows(isolated)[0]["dose"] == 0.5


@pytest.mark.parametrize("kind", ["prescription", "rx", "herb", ""])
def test_add_bad_kind_fails_with_text(isolated: Path, kind: str) -> None:
    result = add_med(
        "антибиотик", "--kind", kind, "--dose", "1", "--unit", "g", "--schedule", "daily"
    )
    assert result.exit_code == 1
    assert "--kind должен быть из ['vitamin', 'mineral', 'electrolyte', 'otc']" in result.output
    assert med_rows(isolated) == []


def test_add_without_kind_fails(isolated: Path) -> None:
    result = run("med", "add", "витамин D", "--dose", "1", "--unit", "mg", "--schedule", "daily")
    assert result.exit_code != 0
    assert med_rows(isolated) == []


@pytest.mark.parametrize("dose", ["0", "-1"])
def test_add_bad_dose_fails_with_text(isolated: Path, dose: str) -> None:
    result = add_med(
        "витамин D", "--kind", "vitamin", "--dose", dose, "--unit", "mg", "--schedule", "daily"
    )
    assert result.exit_code == 1
    assert med_rows(isolated) == []
    assert "--dose" in result.output


def test_add_zero_dose_text(isolated: Path) -> None:
    result = add_med(
        "витамин D", "--kind", "vitamin", "--dose", "0", "--unit", "mg", "--schedule", "daily"
    )
    assert "--dose должна быть больше 0." in result.output


def test_add_text_dose_fails(isolated: Path) -> None:
    result = add_med(
        "витамин D", "--kind", "vitamin", "--dose", "много", "--unit", "mg", "--schedule", "daily"
    )
    assert result.exit_code == 1
    assert med_rows(isolated) == []


def test_add_bad_unit_fails_with_text(isolated: Path) -> None:
    result = add_med(
        "витамин D", "--kind", "vitamin", "--dose", "1", "--unit", "kg", "--schedule", "daily"
    )
    assert result.exit_code == 1
    assert "--unit должен быть из ['mg', 'mcg', 'iu', 'g', 'ml', 'pcs']" in result.output
    assert med_rows(isolated) == []


def test_add_bad_schedule_fails_with_text(isolated: Path) -> None:
    result = add_med(
        "витамин D", "--kind", "vitamin", "--dose", "1", "--unit", "mg", "--schedule", "weekly"
    )
    assert result.exit_code == 1
    assert "--schedule должен быть из ['daily', 'training_day', 'before', 'after']" in result.output
    assert med_rows(isolated) == []


@pytest.mark.parametrize("option", ["--start", "--end"])
@pytest.mark.parametrize("value", ["08.10.2026", "2026-13-01", "2026-1-1", "завтра"])
def test_add_bad_date_fails_with_text(isolated: Path, option: str, value: str) -> None:
    result = add_med("витамин D", *DOSE, option, value)
    assert result.exit_code == 1
    assert "Дата должна быть YYYY-MM-DD" in result.output
    assert med_rows(isolated) == []


def test_add_end_before_start_fails(isolated: Path) -> None:
    result = add_med("витамин D", *DOSE, "--start", "2026-10-10", "--end", "2026-10-09")
    assert result.exit_code == 1
    assert med_rows(isolated) == []


def test_add_end_equal_to_start_is_allowed(isolated: Path) -> None:
    result = add_med("витамин D", *DOSE, "--start", "2026-10-10", "--end", "2026-10-10")
    assert result.exit_code == 0


@pytest.mark.parametrize("name", ["  ", "123"])
def test_add_bad_name_fails_with_code_1(isolated: Path, name: str) -> None:
    assert add_med(name).exit_code == 1
    assert med_rows(isolated) == []


def test_add_duplicate_name_fails_with_text(isolated: Path) -> None:
    add_med("витамин D")
    result = add_med("Витамин d")
    assert result.exit_code == 1
    assert "уже есть" in result.output
    assert len(med_rows(isolated)) == 1


def test_add_options_with_equals_sign(isolated: Path) -> None:
    result = run(
        "med",
        "add",
        "витамин D",
        "--kind=vitamin",
        "--dose=25",
        "--unit=mcg",
        "--schedule=daily",
        "--start=2026-10-01",
    )
    assert result.exit_code == 0


# --- list ---


def test_list_on_empty_database(isolated: Path) -> None:
    assert run("med", "list").exit_code == 0


def test_list_default_shows_only_courses_of_today(isolated: Path) -> None:
    add_med("текущий", *DOSE, "--start", day(-5), "--end", day(5))
    add_med("бессрочный", *DOSE, "--start", day(-5))
    add_med("закончен", *DOSE, "--start", day(-20), "--end", day(-1))
    add_med("будущий", *DOSE, "--start", day(1))
    out = run("med", "list").output
    assert "текущий" in out
    assert "бессрочный" in out
    assert "закончен" not in out
    assert "будущий" not in out


def test_list_all_shows_every_alive_course(isolated: Path) -> None:
    add_med("текущий", *DOSE, "--start", day(-5), "--end", day(5))
    add_med("закончен", *DOSE, "--start", day(-20), "--end", day(-1))
    add_med("будущий", *DOSE, "--start", day(1))
    add_med("удалённый", *DOSE)
    run("med", "delete", str(med_rows(isolated)[-1]["id"]))
    result = run("med", "list", "--all")
    assert result.exit_code == 0
    for part in ["текущий", "закончен", "будущий"]:
        assert part in result.output
    assert "удалённый" not in result.output


def test_list_date_uses_given_day_with_borders(isolated: Path) -> None:
    add_med("курс", *DOSE, "--start", "2026-10-05", "--end", "2026-10-10")
    assert "курс" in run("med", "list", "--date", "2026-10-05").output
    assert "курс" in run("med", "list", "--date", "2026-10-10").output
    assert "курс" not in run("med", "list", "--date", "2026-10-04").output
    assert "курс" not in run("med", "list", "--date", "2026-10-11").output


def test_list_bad_date_fails_with_text(isolated: Path) -> None:
    result = run("med", "list", "--date", "08.10.2026")
    assert result.exit_code == 1
    assert "Дата должна быть YYYY-MM-DD" in result.output


def test_list_date_and_all_together_fails(isolated: Path) -> None:
    assert run("med", "list", "--date", "2026-10-08", "--all").exit_code == 1


def test_list_shows_dose_and_unit(isolated: Path) -> None:
    add_med("витамин D")
    out = run("med", "list").output
    assert "25" in out
    assert "mcg" in out


# --- show ---


def test_show_by_id_and_by_name(isolated: Path) -> None:
    add_med("Витамин D", *DOSE, "--note", "заметка", "--time-note", "с едой")
    rid = str(med_rows(isolated)[0]["id"])
    for key in (rid, "витамин d"):
        result = run("med", "show", key)
        assert result.exit_code == 0
        for part in ["Витамин D", "vitamin", "25", "mcg", "daily", "заметка", "с едой"]:
            assert part in result.output


def test_show_finished_course_still_shows(isolated: Path) -> None:
    add_med("закончен", *DOSE, "--start", day(-20), "--end", day(-1))
    assert run("med", "show", "закончен").exit_code == 0


def test_show_unknown_fails_with_text(isolated: Path) -> None:
    add_med("витамин D")
    result = run("med", "show", "борщ")
    assert result.exit_code == 1
    assert "'борщ' нет" in result.output
    assert run("med", "show", "99").exit_code == 1


# --- edit / delete ---


def test_edit_changes_dose(isolated: Path) -> None:
    add_med("витамин D")
    rid = str(med_rows(isolated)[0]["id"])
    assert run("med", "edit", rid, "--dose", "50").exit_code == 0
    assert med_rows(isolated)[0]["dose"] == 50


def test_edit_sets_end_date(isolated: Path) -> None:
    add_med("витамин D", *DOSE, "--start", "2026-10-01")
    rid = str(med_rows(isolated)[0]["id"])
    assert run("med", "edit", rid, "--end", "2026-10-31").exit_code == 0
    assert med_rows(isolated)[0]["end_date"] == "2026-10-31"


def test_edit_bad_value_fails_and_keeps_data(isolated: Path) -> None:
    add_med("витамин D")
    rid = str(med_rows(isolated)[0]["id"])
    assert run("med", "edit", rid, "--dose", "0").exit_code == 1
    assert run("med", "edit", rid, "--kind", "rx").exit_code == 1
    assert run("med", "edit", rid, "--end", "завтра").exit_code == 1
    assert med_rows(isolated)[0]["dose"] == 25


def test_edit_end_before_start_fails(isolated: Path) -> None:
    add_med("витамин D", *DOSE, "--start", "2026-10-10")
    rid = str(med_rows(isolated)[0]["id"])
    assert run("med", "edit", rid, "--end", "2026-10-01").exit_code == 1
    assert med_rows(isolated)[0]["end_date"] is None


def test_edit_without_options_fails(isolated: Path) -> None:
    add_med("витамин D")
    rid = str(med_rows(isolated)[0]["id"])
    assert run("med", "edit", rid).exit_code == 1


def test_edit_unknown_fails_with_text(isolated: Path) -> None:
    result = run("med", "edit", "99", "--dose", "5")
    assert result.exit_code == 1
    assert "99" in result.output


def test_edit_name_to_taken_fails(isolated: Path) -> None:
    add_med("цинк")
    add_med("железо")
    rid = str(med_rows(isolated)[1]["id"])
    assert run("med", "edit", rid, "--name", "Цинк").exit_code == 1


def test_delete_marks_row_and_hides_it(isolated: Path) -> None:
    add_med("витамин D")
    rid = str(med_rows(isolated)[0]["id"])
    assert run("med", "delete", rid).exit_code == 0
    assert med_rows(isolated)[0]["deleted_at"] is not None
    assert "витамин D" not in run("med", "list", "--all").output
    assert run("med", "show", rid).exit_code == 1


def test_delete_twice_or_unknown_fails_with_text(isolated: Path) -> None:
    add_med("витамин D")
    rid = str(med_rows(isolated)[0]["id"])
    run("med", "delete", rid)
    result = run("med", "delete", rid)
    assert result.exit_code == 1
    assert "уже удал" in result.output
    assert run("med", "delete", "99").exit_code == 1


# --- allow ---


@pytest.mark.parametrize("sub", ["add", "list", "show"])
def test_settings_allow_add_list_show(sub: str) -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert f"Bash(uv run coach med {sub}:*)" in allow


def test_settings_allow_has_no_edit_delete_or_wildcard() -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert not [r for r in allow if "med edit" in r or "med delete" in r]
    assert "Bash(uv run coach med:*)" not in allow
    assert "Bash(uv run coach:*)" not in allow
    assert not [r for r in allow if r.startswith("Bash(uv run coach med") and ":*" not in r]


def test_settings_allow_keeps_step_17_rules() -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert "Bash(uv run coach supplement add:*)" in allow
    assert "Bash(uv run coach protocol show:*)" in allow
