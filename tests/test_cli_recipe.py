import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from mcp_fakes import call
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"
MACROS = ["--kcal", "150", "--protein", "8", "--fat", "5", "--carbs", "18"]


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("recipe не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def recipe_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM recipe ORDER BY id").fetchall()
    finally:
        conn.close()


def item_rows(db: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM recipe_ingredient ORDER BY rowid").fetchall()
    finally:
        conn.close()


def add(name: str = "плов", *extra: str) -> Any:
    return run("recipe", "add", name, *MACROS, *extra)


# --- add ---


def test_add_saves_recipe(isolated: Path) -> None:
    result = add("плов")
    assert result.exit_code == 0
    row = recipe_rows(isolated)[0]
    assert row["name"] == "плов"
    assert (row["kcal_100"], row["protein_100"], row["fat_100"], row["carbs_100"]) == (
        150,
        8,
        5,
        18,
    )
    assert row["yield_g"] is None
    assert row["deleted_at"] is None


def test_add_with_yield(isolated: Path) -> None:
    assert add("плов", "--yield", "1000").exit_code == 0
    assert recipe_rows(isolated)[0]["yield_g"] == 1000


def test_add_with_items(isolated: Path) -> None:
    result = add("плов", "--item", "курица 500 g", "--item", "рис 200 g", "--item", "яйца 2 pcs")
    assert result.exit_code == 0
    items = [(r["product"], r["qty"], r["unit"]) for r in item_rows(isolated)]
    assert items == [("курица", 500, "g"), ("рис", 200, "g"), ("яйца", 2, "pcs")]


def test_add_item_with_spaces_in_product(isolated: Path) -> None:
    assert add("суп", "--item", "куриная грудка 300 g").exit_code == 0
    assert item_rows(isolated)[0]["product"] == "куриная грудка"


def test_add_with_decimal_comma_macros(isolated: Path) -> None:
    result = run(
        "recipe", "add", "каша", "--kcal", "88,5", "--protein", "3", "--fat", "2", "--carbs", "14"
    )
    assert result.exit_code == 0
    assert recipe_rows(isolated)[0]["kcal_100"] == 88.5


def test_add_zero_macros_is_allowed(isolated: Path) -> None:
    result = run(
        "recipe", "add", "вода", "--kcal", "0", "--protein", "0", "--fat", "0", "--carbs", "0"
    )
    assert result.exit_code == 0


def test_add_900_kcal_is_allowed(isolated: Path) -> None:
    result = run(
        "recipe", "add", "масло", "--kcal", "900", "--protein", "0", "--fat", "100", "--carbs", "0"
    )
    assert result.exit_code == 0


def test_add_prints_id(isolated: Path) -> None:
    result = add("плов")
    assert str(recipe_rows(isolated)[0]["id"]) in result.output


@pytest.mark.parametrize("option", ["--kcal", "--protein", "--fat", "--carbs"])
def test_add_negative_macro_fails_with_code_1(isolated: Path, option: str) -> None:
    args = dict(
        zip(["--kcal", "--protein", "--fat", "--carbs"], ["150", "8", "5", "18"], strict=True)
    )
    args[option] = "-1"
    flat = [x for pair in args.items() for x in pair]
    result = run("recipe", "add", "плов", *flat)
    assert result.exit_code == 1
    assert recipe_rows(isolated) == []


def test_add_over_900_kcal_fails_with_code_1(isolated: Path) -> None:
    result = run(
        "recipe", "add", "плов", "--kcal", "901", "--protein", "8", "--fat", "5", "--carbs", "18"
    )
    assert result.exit_code == 1
    assert recipe_rows(isolated) == []


def test_add_garbage_macro_fails_with_code_1(isolated: Path) -> None:
    result = run(
        "recipe", "add", "плов", "--kcal", "много", "--protein", "8", "--fat", "5", "--carbs", "18"
    )
    assert result.exit_code == 1
    assert recipe_rows(isolated) == []


@pytest.mark.parametrize(
    "item",
    [
        "курица",
        "курица 500",
        "курица g 500",
        "курица 500 kg",
        "курица много g",
        "курица -5 g",
        "курица 0 g",
    ],
)
def test_add_bad_item_fails_and_saves_nothing(isolated: Path, item: str) -> None:
    result = add("плов", "--item", item)
    assert result.exit_code == 1
    assert recipe_rows(isolated) == []


@pytest.mark.parametrize("value", ["0", "-100", "много"])
def test_add_bad_yield_fails_with_code_1(isolated: Path, value: str) -> None:
    result = add("плов", "--yield", value)
    assert result.exit_code == 1
    assert recipe_rows(isolated) == []


def test_add_empty_name_fails(isolated: Path) -> None:
    assert add("  ").exit_code == 1
    assert recipe_rows(isolated) == []


def test_add_without_macros_fails(isolated: Path) -> None:
    assert run("recipe", "add", "плов").exit_code != 0
    assert recipe_rows(isolated) == []


def test_add_duplicate_name_fails_with_code_1(isolated: Path) -> None:
    add("плов")
    result = add("Плов")
    assert result.exit_code == 1
    assert len(recipe_rows(isolated)) == 1


# --- list / show ---


def test_list_on_empty_database(isolated: Path) -> None:
    result = run("recipe", "list")
    assert result.exit_code == 0


def test_list_shows_names_and_kcal(isolated: Path) -> None:
    add("плов")
    add("борщ")
    result = run("recipe", "list")
    assert result.exit_code == 0
    assert "плов" in result.output
    assert "борщ" in result.output
    assert "150" in result.output


def test_list_hides_deleted(isolated: Path) -> None:
    add("плов")
    add("борщ")
    run("recipe", "delete", str(recipe_rows(isolated)[1]["id"]))
    result = run("recipe", "list")
    assert "плов" in result.output
    assert "борщ" not in result.output


def test_show_by_id_prints_macros_and_items(isolated: Path) -> None:
    add("плов", "--yield", "1000", "--item", "курица 500 g")
    rid = str(recipe_rows(isolated)[0]["id"])
    result = run("recipe", "show", rid)
    assert result.exit_code == 0
    for part in ["плов", "150", "курица", "500", "1000"]:
        assert part in result.output


def test_show_by_name_ignores_case(isolated: Path) -> None:
    add("Плов", "--item", "курица 500 g")
    result = run("recipe", "show", "плов")
    assert result.exit_code == 0
    assert "курица" in result.output


def test_show_unknown_fails_with_code_1(isolated: Path) -> None:
    add("плов")
    assert run("recipe", "show", "борщ").exit_code == 1
    assert run("recipe", "show", "99").exit_code == 1


def test_show_deleted_fails(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    run("recipe", "delete", rid)
    assert run("recipe", "show", rid).exit_code == 1


@pytest.mark.parametrize("grams", ["0", "-5", "много"])
def test_show_bad_grams_fails_with_code_1(isolated: Path, grams: str) -> None:
    add("плов", "--yield", "1000", "--item", "курица 500 g")
    result = run("recipe", "show", "плов", "--grams", grams)
    assert result.exit_code == 1


def test_show_grams_prints_portion(isolated: Path) -> None:
    add("плов", "--yield", "1000", "--item", "курица 500 g")
    result = run("recipe", "show", "плов", "--grams", "250")
    assert result.exit_code == 0
    assert "списать: курица 125.0 g" in result.output


def test_add_name_of_digits_fails_with_code_1(isolated: Path) -> None:
    assert add("123").exit_code == 1
    assert recipe_rows(isolated) == []


def test_edit_name_of_digits_fails_with_code_1(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    assert run("recipe", "edit", rid, "--name", "42").exit_code == 1
    assert recipe_rows(isolated)[0]["name"] == "плов"


def test_options_with_equals_sign(isolated: Path) -> None:
    result = run("recipe", "add", "каша", "--kcal=88", "--protein=3", "--fat=2", "--carbs=14")
    assert result.exit_code == 0


def test_help_lists_macro_options() -> None:
    result = run("recipe", "add", "--help")
    assert "--kcal" in result.output
    assert "--carbs" in result.output


# --- edit ---


def test_edit_macros(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    assert run("recipe", "edit", rid, "--kcal", "170").exit_code == 0
    row = recipe_rows(isolated)[0]
    assert (row["kcal_100"], row["protein_100"]) == (170, 8)


def test_edit_yield_and_name(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    assert run("recipe", "edit", rid, "--yield", "800", "--name", "плов домашний").exit_code == 0
    row = recipe_rows(isolated)[0]
    assert (row["yield_g"], row["name"]) == (800, "плов домашний")


def test_edit_items_replace_wholly(isolated: Path) -> None:
    add("плов", "--item", "курица 500 g", "--item", "рис 200 g")
    rid = str(recipe_rows(isolated)[0]["id"])
    assert run("recipe", "edit", rid, "--item", "говядина 400 g").exit_code == 0
    assert [r["product"] for r in item_rows(isolated)] == ["говядина"]


def test_edit_without_items_keeps_items(isolated: Path) -> None:
    add("плов", "--item", "курица 500 g")
    rid = str(recipe_rows(isolated)[0]["id"])
    run("recipe", "edit", rid, "--kcal", "170")
    assert [r["product"] for r in item_rows(isolated)] == ["курица"]


def test_edit_unknown_fails_with_code_1(isolated: Path) -> None:
    assert run("recipe", "edit", "99", "--kcal", "170").exit_code == 1


def test_edit_deleted_fails(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    run("recipe", "delete", rid)
    assert run("recipe", "edit", rid, "--kcal", "170").exit_code == 1


def test_edit_over_900_kcal_fails_and_keeps_value(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    assert run("recipe", "edit", rid, "--kcal", "901").exit_code == 1
    assert recipe_rows(isolated)[0]["kcal_100"] == 150


def test_edit_negative_macro_fails(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    assert run("recipe", "edit", rid, "--protein", "-1").exit_code == 1
    assert recipe_rows(isolated)[0]["protein_100"] == 8


def test_edit_to_existing_name_fails(isolated: Path) -> None:
    add("плов")
    add("борщ")
    rid = str(recipe_rows(isolated)[1]["id"])
    assert run("recipe", "edit", rid, "--name", "Плов").exit_code == 1
    assert recipe_rows(isolated)[1]["name"] == "борщ"


# --- delete ---


def test_delete_marks_recipe(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    assert run("recipe", "delete", rid).exit_code == 0
    assert recipe_rows(isolated)[0]["deleted_at"] is not None


def test_delete_twice_fails_with_code_1(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    run("recipe", "delete", rid)
    assert run("recipe", "delete", rid).exit_code == 1


def test_delete_unknown_fails_with_code_1(isolated: Path) -> None:
    assert run("recipe", "delete", "99").exit_code == 1


def test_deleted_recipe_not_in_mcp(isolated: Path) -> None:
    add("плов")
    rid = str(recipe_rows(isolated)[0]["id"])
    run("recipe", "delete", rid)
    conn = sqlite3.connect(isolated)
    conn.row_factory = sqlite3.Row
    try:
        assert call(conn, "get_recipes")["rows"] == []
    finally:
        conn.close()


def test_name_can_be_reused_after_delete(isolated: Path) -> None:
    add("плов")
    run("recipe", "delete", str(recipe_rows(isolated)[0]["id"]))
    assert add("плов").exit_code == 0


# --- allow ---


def test_settings_allow_add_list_show_but_not_edit_delete() -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert "Bash(uv run coach recipe add:*)" in allow
    assert "Bash(uv run coach recipe list:*)" in allow
    assert "Bash(uv run coach recipe show:*)" in allow
    assert not [rule for rule in allow if "recipe edit" in rule or "recipe delete" in rule]
    assert "Bash(uv run coach recipe:*)" not in allow
    assert "Bash(uv run coach:*)" not in allow
