"""coach habit add/list/done/undo/edit/delete: привычка - да/нет за день и необязательное число.
Допущения интерфейса: `habit done <id|имя> [число]`, `habit undo <id|имя>`,
`habit edit <id|имя> [--name] [--unit]`, `habit add <имя> [--unit ед]`."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
DAY = "2026-10-11"
NOON = f"{DAY} 12:00:00"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("habit не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    freeze(monkeypatch, NOON)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def query(db: Path, sql: str) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def habits(db: Path) -> list[sqlite3.Row]:
    return query(db, "SELECT * FROM habit ORDER BY id")


def logs(db: Path) -> list[sqlite3.Row]:
    return query(db, "SELECT * FROM habit_log ORDER BY date, habit_id")


def hid(db: Path, index: int = 0) -> str:
    return str(habits(db)[index]["id"])


# --- add ---


def test_add_saves_habit(isolated: Path) -> None:
    result = run("habit", "add", "зарядка")
    assert result.exit_code == 0
    row = habits(isolated)[0]
    assert (row["name"], row["unit"], row["deleted_at"]) == ("зарядка", None, None)


def test_add_with_unit(isolated: Path) -> None:
    assert run("habit", "add", "вода", "--unit", "стаканов").exit_code == 0
    assert habits(isolated)[0]["unit"] == "стаканов"


def test_add_prints_id(isolated: Path) -> None:
    result = run("habit", "add", "зарядка")
    assert hid(isolated) in result.output


def test_add_empty_name_fails(isolated: Path) -> None:
    assert run("habit", "add", "  ").exit_code == 1
    assert habits(isolated) == []


def test_add_name_of_digits_fails(isolated: Path) -> None:
    assert run("habit", "add", "123").exit_code == 1
    assert habits(isolated) == []


def test_add_duplicate_name_ignoring_case_fails(isolated: Path) -> None:
    run("habit", "add", "Зарядка")
    assert run("habit", "add", "зарядка").exit_code == 1
    assert len(habits(isolated)) == 1


# --- list ---


def test_list_on_empty_database(isolated: Path) -> None:
    assert run("habit", "list").exit_code == 0


def test_list_shows_names_and_units(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "стаканов")
    run("habit", "add", "зарядка")
    result = run("habit", "list")
    assert result.exit_code == 0
    for part in ["вода", "стаканов", "зарядка"]:
        assert part in result.output


def test_list_hides_deleted(isolated: Path) -> None:
    run("habit", "add", "вода")
    run("habit", "add", "зарядка")
    run("habit", "delete", hid(isolated, 1))
    result = run("habit", "list")
    assert "вода" in result.output
    assert "зарядка" not in result.output


# --- done ---


def test_done_marks_today_by_id(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    assert run("habit", "done", hid(isolated)).exit_code == 0
    row = logs(isolated)[0]
    assert (row["date"], row["done"], row["amount"]) == (DAY, 1, None)


def test_done_by_name_ignores_case(isolated: Path) -> None:
    run("habit", "add", "Зарядка")
    assert run("habit", "done", "зарядка").exit_code == 0
    assert len(logs(isolated)) == 1


def test_done_with_amount(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "стаканов")
    assert run("habit", "done", "вода", "6").exit_code == 0
    assert logs(isolated)[0]["amount"] == 6


def test_done_amount_with_decimal_comma(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "л")
    assert run("habit", "done", "вода", "1,5").exit_code == 0
    assert logs(isolated)[0]["amount"] == 1.5


def test_done_amount_zero_is_allowed(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "л")
    assert run("habit", "done", "вода", "0").exit_code == 0


@pytest.mark.parametrize("value", ["много", "1.2.3"])
def test_done_bad_amount_fails_and_saves_nothing(isolated: Path, value: str) -> None:
    run("habit", "add", "вода", "--unit", "стаканов")
    assert run("habit", "done", "вода", value).exit_code == 1
    assert logs(isolated) == []


def test_done_twice_keeps_one_row_and_updates_amount(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "стаканов")
    run("habit", "done", "вода", "2")
    assert run("habit", "done", "вода", "5").exit_code == 0
    rows = logs(isolated)
    assert len(rows) == 1
    assert (rows[0]["done"], rows[0]["amount"]) == (1, 5)


def test_done_twice_without_amount_does_not_fail(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    run("habit", "done", "зарядка")
    assert run("habit", "done", "зарядка").exit_code == 0
    assert len(logs(isolated)) == 1


def test_done_marks_only_that_habit(isolated: Path) -> None:
    run("habit", "add", "вода")
    run("habit", "add", "зарядка")
    run("habit", "done", "вода")
    assert [r["habit_id"] for r in logs(isolated)] == [habits(isolated)[0]["id"]]


def test_done_unknown_fails_with_code_1(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    assert run("habit", "done", "бег").exit_code == 1
    assert run("habit", "done", "99").exit_code == 1
    assert logs(isolated) == []


def test_done_deleted_habit_fails(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    run("habit", "delete", hid(isolated))
    assert run("habit", "done", "зарядка").exit_code == 1
    assert logs(isolated) == []


def test_done_amount_without_unit_fails_and_saves_nothing(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    assert run("habit", "done", "зарядка", "3").exit_code == 1
    assert logs(isolated) == []


def test_done_without_amount_is_fine_for_habit_without_unit(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    assert run("habit", "done", "зарядка").exit_code == 0


# --- done --no ---


def test_no_writes_done_zero(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    assert run("habit", "done", "зарядка", "--no").exit_code == 0
    row = logs(isolated)[0]
    assert (row["date"], row["done"], row["amount"]) == (DAY, 0, None)


def test_no_by_id(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    assert run("habit", "done", hid(isolated), "--no").exit_code == 0
    assert logs(isolated)[0]["done"] == 0


def test_no_with_amount_fails_and_saves_nothing(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "стаканов")
    assert run("habit", "done", "вода", "2", "--no").exit_code == 1
    assert logs(isolated) == []


def test_no_after_done_overwrites_to_zero_and_clears_amount(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "стаканов")
    run("habit", "done", "вода", "5")
    assert run("habit", "done", "вода", "--no").exit_code == 0
    rows = logs(isolated)
    assert len(rows) == 1
    assert (rows[0]["done"], rows[0]["amount"]) == (0, None)


def test_done_after_no_overwrites_to_one(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    run("habit", "done", "зарядка", "--no")
    assert run("habit", "done", "зарядка").exit_code == 0
    rows = logs(isolated)
    assert len(rows) == 1
    assert rows[0]["done"] == 1


def test_no_twice_keeps_one_row(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    run("habit", "done", "зарядка", "--no")
    assert run("habit", "done", "зарядка", "--no").exit_code == 0
    assert [r["done"] for r in logs(isolated)] == [0]


def test_no_on_deleted_habit_fails(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    run("habit", "delete", hid(isolated))
    assert run("habit", "done", "зарядка", "--no").exit_code == 1
    assert logs(isolated) == []


# --- undo ---


def test_undo_removes_todays_mark(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    run("habit", "done", "зарядка")
    assert run("habit", "undo", "зарядка").exit_code == 0
    assert [r for r in logs(isolated) if r["done"] == 1] == []


def test_undo_keeps_other_days(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run("habit", "add", "зарядка")
    run("habit", "done", "зарядка", "--date", "2026-10-10")
    run("habit", "done", "зарядка")
    run("habit", "undo", "зарядка")
    assert [(r["date"], r["done"]) for r in logs(isolated)] == [("2026-10-10", 1)]


def test_undo_keeps_other_habits(isolated: Path) -> None:
    run("habit", "add", "вода")
    run("habit", "add", "зарядка")
    run("habit", "done", "вода")
    run("habit", "done", "зарядка")
    run("habit", "undo", "зарядка")
    done = [r["habit_id"] for r in logs(isolated) if r["done"] == 1]
    assert done == [habits(isolated)[0]["id"]]


def test_undo_without_mark_fails_with_code_1(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    assert run("habit", "undo", "зарядка").exit_code == 1


def test_undo_unknown_fails_with_code_1(isolated: Path) -> None:
    assert run("habit", "undo", "99").exit_code == 1


def test_done_works_again_after_undo(isolated: Path) -> None:
    run("habit", "add", "зарядка")
    run("habit", "done", "зарядка")
    run("habit", "undo", "зарядка")
    assert run("habit", "done", "зарядка").exit_code == 0
    assert [r["done"] for r in logs(isolated)] == [1]


# --- edit ---


def test_edit_name_and_unit(isolated: Path) -> None:
    run("habit", "add", "вода")
    result = run("habit", "edit", hid(isolated), "--name", "питьё", "--unit", "л")
    assert result.exit_code == 0
    row = habits(isolated)[0]
    assert (row["name"], row["unit"]) == ("питьё", "л")


def test_edit_keeps_history(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "стаканов")
    run("habit", "done", "вода", "3")
    run("habit", "edit", hid(isolated), "--name", "питьё")
    assert logs(isolated)[0]["amount"] == 3


def test_edit_to_existing_name_fails(isolated: Path) -> None:
    run("habit", "add", "вода")
    run("habit", "add", "зарядка")
    assert run("habit", "edit", hid(isolated, 1), "--name", "Вода").exit_code == 1
    assert habits(isolated)[1]["name"] == "зарядка"


def test_edit_name_of_digits_fails(isolated: Path) -> None:
    run("habit", "add", "вода")
    assert run("habit", "edit", hid(isolated), "--name", "42").exit_code == 1
    assert habits(isolated)[0]["name"] == "вода"


def test_edit_unknown_fails_with_code_1(isolated: Path) -> None:
    assert run("habit", "edit", "99", "--name", "бег").exit_code == 1


def test_edit_deleted_fails(isolated: Path) -> None:
    run("habit", "add", "вода")
    run("habit", "delete", hid(isolated))
    assert run("habit", "edit", hid(isolated), "--name", "питьё").exit_code == 1


# --- delete (мягкое) ---


def test_delete_marks_habit_and_keeps_row(isolated: Path) -> None:
    run("habit", "add", "вода")
    assert run("habit", "delete", hid(isolated)).exit_code == 0
    rows = habits(isolated)
    assert len(rows) == 1
    assert rows[0]["deleted_at"] is not None


def test_delete_keeps_history(isolated: Path) -> None:
    run("habit", "add", "вода", "--unit", "стаканов")
    run("habit", "done", "вода", "4")
    run("habit", "delete", hid(isolated))
    rows = logs(isolated)
    assert len(rows) == 1
    assert (rows[0]["done"], rows[0]["amount"]) == (1, 4)


def test_delete_by_name(isolated: Path) -> None:
    run("habit", "add", "вода")
    assert run("habit", "delete", "вода").exit_code == 0
    assert habits(isolated)[0]["deleted_at"] is not None


def test_delete_twice_fails_with_code_1(isolated: Path) -> None:
    run("habit", "add", "вода")
    run("habit", "delete", hid(isolated))
    assert run("habit", "delete", hid(isolated)).exit_code == 1


def test_delete_unknown_fails_with_code_1(isolated: Path) -> None:
    assert run("habit", "delete", "99").exit_code == 1


def test_name_can_be_reused_after_delete(isolated: Path) -> None:
    run("habit", "add", "вода")
    run("habit", "delete", hid(isolated))
    assert run("habit", "add", "вода").exit_code == 0
    assert len(habits(isolated)) == 2
