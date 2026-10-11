"""coach practice add/list/show: справочник практик (дыхание, пауза, прогулка, сон)."""

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("practice не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def practice_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM practice ORDER BY id").fetchall()
    finally:
        conn.close()


def add(name: str = "дыхание 4-7-8", *extra: str) -> Any:
    return run("practice", "add", name, "--kind", "breathing", *extra)


# --- add ---


def test_add_saves_practice(isolated: Path) -> None:
    result = add("дыхание 4-7-8")
    assert result.exit_code == 0
    row = practice_rows(isolated)[0]
    assert (row["name"], row["kind"]) == ("дыхание 4-7-8", "breathing")
    assert row["minutes"] is None
    assert row["deleted_at"] is None


def test_add_with_all_fields(isolated: Path) -> None:
    result = add(
        "дыхание 4-7-8",
        "--minutes",
        "5",
        "--trigger",
        "стресс 4 и выше",
        "--steps",
        "вдох 4, пауза 7, выдох 8",
    )
    assert result.exit_code == 0
    row = practice_rows(isolated)[0]
    assert row["minutes"] == 5
    assert row["trigger"] == "стресс 4 и выше"
    assert row["steps"] == "вдох 4, пауза 7, выдох 8"


@pytest.mark.parametrize("kind", ["breathing", "pause", "walk", "sleep"])
def test_add_every_kind(isolated: Path, kind: str) -> None:
    assert run("practice", "add", "практика", "--kind", kind).exit_code == 0
    assert practice_rows(isolated)[0]["kind"] == kind


def test_add_prints_id(isolated: Path) -> None:
    result = add()
    assert str(practice_rows(isolated)[0]["id"]) in result.output


def test_add_unknown_kind_fails_with_code_1(isolated: Path) -> None:
    result = run("practice", "add", "йога", "--kind", "yoga")
    assert result.exit_code == 1
    assert practice_rows(isolated) == []


@pytest.mark.parametrize("value", ["0", "-5", "много"])
def test_add_bad_minutes_fails_with_code_1(isolated: Path, value: str) -> None:
    result = add("дыхание", "--minutes", value)
    assert result.exit_code == 1
    assert practice_rows(isolated) == []


def test_add_empty_name_fails(isolated: Path) -> None:
    assert add("  ").exit_code == 1
    assert practice_rows(isolated) == []


def test_add_name_of_digits_fails(isolated: Path) -> None:
    assert add("123").exit_code == 1
    assert practice_rows(isolated) == []


def test_add_duplicate_name_ignoring_case_fails(isolated: Path) -> None:
    add("Прогулка")
    assert add("прогулка").exit_code == 1
    assert len(practice_rows(isolated)) == 1


# --- list / show ---


def test_list_on_empty_database(isolated: Path) -> None:
    assert run("practice", "list").exit_code == 0


def test_list_shows_names_and_kinds(isolated: Path) -> None:
    add("дыхание 4-7-8")
    run("practice", "add", "прогулка у воды", "--kind", "walk")
    result = run("practice", "list")
    assert result.exit_code == 0
    for part in ["дыхание 4-7-8", "прогулка у воды", "breathing", "walk"]:
        assert part in result.output


def test_list_hides_deleted(isolated: Path) -> None:
    add("дыхание")
    add("пауза у окна")
    conn = sqlite3.connect(isolated)
    conn.execute("UPDATE practice SET deleted_at = '2026-10-11 10:00:00' WHERE name = 'дыхание'")
    conn.commit()
    conn.close()
    result = run("practice", "list")
    assert "пауза у окна" in result.output
    assert "дыхание" not in result.output


def test_show_by_id_prints_all_fields(isolated: Path) -> None:
    add("дыхание 4-7-8", "--minutes", "5", "--trigger", "перед сном", "--steps", "вдох, выдох")
    pid = str(practice_rows(isolated)[0]["id"])
    result = run("practice", "show", pid)
    assert result.exit_code == 0
    for part in ["дыхание 4-7-8", "breathing", "5", "перед сном", "вдох, выдох"]:
        assert part in result.output


def test_show_by_name_ignores_case(isolated: Path) -> None:
    add("Дыхание", "--steps", "вдох, выдох")
    result = run("practice", "show", "дыхание")
    assert result.exit_code == 0
    assert "вдох, выдох" in result.output


def test_show_unknown_fails_with_code_1(isolated: Path) -> None:
    add("дыхание")
    assert run("practice", "show", "прогулка").exit_code == 1
    assert run("practice", "show", "99").exit_code == 1


# --- allow ---


def test_settings_allow_add_list_show_but_not_edit_delete() -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert "Bash(uv run coach practice add:*)" in allow
    assert "Bash(uv run coach practice list:*)" in allow
    assert "Bash(uv run coach practice show:*)" in allow
    assert not [rule for rule in allow if "practice edit" in rule or "practice delete" in rule]
    assert "Bash(uv run coach practice:*)" not in allow
