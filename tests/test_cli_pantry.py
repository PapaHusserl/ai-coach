import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from mcp_fakes import call
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """База и папка data — во временной папке; Garmin и сеть недоступны."""
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("pantry, shop и meal не должны ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def pantry_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = connect(db)
    try:
        return conn.execute("SELECT * FROM pantry_log ORDER BY id").fetchall()
    finally:
        conn.close()


def stock(db: Path) -> dict[str, float]:
    conn = connect(db)
    try:
        return {r["item"]: r["qty"] for r in call(conn, "get_pantry")["rows"]}
    finally:
        conn.close()


def snapshot_flag(db: Path, day: str) -> Any:
    conn = connect(db)
    try:
        return call(conn, "get_morning_snapshot", date=day)["meal_plan_today"]
    finally:
        conn.close()


def shopping_files(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "data" / "shopping").glob("*.md"))


def test_pantry_add_saves_entry(isolated: Path) -> None:
    result = runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    assert result.exit_code == 0
    row = pantry_rows(isolated)[0]
    assert (row["item"], row["qty"], row["unit"], row["op"]) == ("курица", 500, "g", "add")


def test_pantry_add_then_use_leaves_the_rest(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    runner.invoke(main.app, ["pantry", "use", "курица", "200", "g"])
    assert stock(isolated) == {"курица": 300}


def test_pantry_set_replaces_stock(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    runner.invoke(main.app, ["pantry", "set", "курица", "1000", "g"])
    assert stock(isolated) == {"курица": 1000}


def test_pantry_remove_clears_item(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    result = runner.invoke(main.app, ["pantry", "remove", "курица"])
    assert result.exit_code == 0
    assert stock(isolated) == {}


def test_pantry_item_with_spaces_is_normalized(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "Куриная грудка ", "500", "g"])
    assert pantry_rows(isolated)[0]["item"] == "куриная грудка"


def test_pantry_add_with_other_unit_is_an_error(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    result = runner.invoke(main.app, ["pantry", "add", "курица", "2", "pcs"])
    assert result.exit_code != 0
    assert len(pantry_rows(isolated)) == 1


@pytest.mark.parametrize("args", [["0", "g"], ["-5", "g"], ["abc", "g"], ["5", "kg"]])
def test_pantry_bad_input_is_an_error_and_writes_nothing(isolated: Path, args: list[str]) -> None:
    result = runner.invoke(main.app, ["pantry", "add", "курица", *args])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert pantry_rows(isolated) == []


def test_pantry_use_more_than_stock_warns_and_succeeds(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "100", "g"])
    result = runner.invoke(main.app, ["pantry", "use", "курица", "300", "g"])
    assert result.exit_code == 0
    assert stock(isolated) == {}


def test_pantry_list_shows_items(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    runner.invoke(main.app, ["pantry", "add", "рис", "1000", "g"])
    result = runner.invoke(main.app, ["pantry", "list"])
    assert result.exit_code == 0
    assert "курица" in result.output
    assert "500" in result.output
    assert "рис" in result.output


def test_pantry_list_on_empty_database_is_not_an_error(isolated: Path) -> None:
    result = runner.invoke(main.app, ["pantry", "list"])
    assert result.exit_code == 0


def test_shop_creates_file_prints_it_and_keeps_pantry(isolated: Path, tmp_path: Path) -> None:
    result = runner.invoke(main.app, ["shop", "курица 500 g", "рис 1000 g"])
    assert result.exit_code == 0
    files = shopping_files(tmp_path)
    assert [f.name for f in files] == [f"{date.today().isoformat()}.md"]
    text = files[0].read_text()
    assert "курица" in text
    assert "рис" in text
    assert "курица" in result.output
    assert "data/shopping" in result.output
    assert pantry_rows(isolated) == []


def test_shop_with_empty_list_is_an_error(isolated: Path, tmp_path: Path) -> None:
    result = runner.invoke(main.app, ["shop"])
    assert result.exit_code != 0
    assert shopping_files(tmp_path) == []


def test_shop_with_bad_line_is_an_error(isolated: Path, tmp_path: Path) -> None:
    result = runner.invoke(main.app, ["shop", "курица много"])
    assert result.exit_code != 0
    assert shopping_files(tmp_path) == []


def test_shop_done_adds_lines_to_pantry(isolated: Path, tmp_path: Path) -> None:
    runner.invoke(main.app, ["shop", "курица 500 g", "рис 1000 g"])
    path = shopping_files(tmp_path)[0]
    result = runner.invoke(main.app, ["shop", "done", str(path)])
    assert result.exit_code == 0
    assert stock(isolated) == {"курица": 500, "рис": 1000}


def test_shop_lists_only_what_is_missing_so_done_brings_stock_to_need(
    isolated: Path, tmp_path: Path
) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "200", "g"])
    runner.invoke(main.app, ["shop", "курица 500 g"])
    runner.invoke(main.app, ["shop", "done", str(shopping_files(tmp_path)[0])])
    assert stock(isolated) == {"курица": 500}


def test_shop_done_with_missing_file_is_an_error(isolated: Path, tmp_path: Path) -> None:
    result = runner.invoke(main.app, ["shop", "done", str(tmp_path / "нет.md")])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert pantry_rows(isolated) == []


def test_food_does_not_change_pantry(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    runner.invoke(main.app, ["food", "съел 200 г курицы"])
    assert stock(isolated) == {"курица": 500}
    assert len(pantry_rows(isolated)) == 1


def test_meal_flag_is_false_before_mark(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    assert snapshot_flag(isolated, date.today().isoformat()) is False


def test_meal_done_sets_flag_for_today(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    result = runner.invoke(main.app, ["meal", "done"])
    assert result.exit_code == 0
    assert snapshot_flag(isolated, date.today().isoformat()) is True


def test_meal_flag_is_false_on_another_day(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    runner.invoke(main.app, ["meal", "done"])
    today = date.today()
    assert snapshot_flag(isolated, (today + timedelta(days=1)).isoformat()) is False
    assert snapshot_flag(isolated, (today - timedelta(days=1)).isoformat()) is False


def test_meal_done_twice_is_not_an_error(isolated: Path) -> None:
    runner.invoke(main.app, ["meal", "done"])
    result = runner.invoke(main.app, ["meal", "done"])
    assert result.exit_code == 0
    assert snapshot_flag(isolated, date.today().isoformat()) is True


def test_meal_done_does_not_touch_pantry(isolated: Path) -> None:
    runner.invoke(main.app, ["meal", "done"])
    assert pantry_rows(isolated) == []


def test_shop_done_twice_is_refused_and_pantry_unchanged(isolated: Path, tmp_path: Path) -> None:
    runner.invoke(main.app, ["shop", "курица 500 g"])
    path = shopping_files(tmp_path)[0]
    runner.invoke(main.app, ["shop", "done", str(path)])
    result = runner.invoke(main.app, ["shop", "done", str(path)])
    assert result.exit_code != 0
    assert stock(isolated) == {"курица": 500}
    assert "Оприходовано" in path.read_text()


def test_shop_with_everything_at_home_writes_no_file(isolated: Path, tmp_path: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "курица", "500", "g"])
    result = runner.invoke(main.app, ["shop", "курица 300 g"])
    assert result.exit_code == 0
    assert "Всё есть" in result.output
    assert shopping_files(tmp_path) == []


def test_shop_appends_to_todays_file(isolated: Path, tmp_path: Path) -> None:
    runner.invoke(main.app, ["shop", "курица 500 g"])
    runner.invoke(main.app, ["shop", "рис 100 g"])
    text = shopping_files(tmp_path)[0].read_text()
    assert "курица" in text
    assert "рис" in text


def test_shop_path_does_not_depend_on_cwd(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    runner.invoke(main.app, ["shop", "курица 500 g"])
    assert len(shopping_files(tmp_path)) == 1
    assert not (other / "data").exists()


def test_shop_from_missing_file_is_an_error(isolated: Path, tmp_path: Path) -> None:
    result = runner.invoke(main.app, ["shop", "--from-file", str(tmp_path / "нет.txt")])
    assert result.exit_code != 0
    assert shopping_files(tmp_path) == []


def test_pantry_use_unknown_item_is_refused(isolated: Path) -> None:
    result = runner.invoke(main.app, ["pantry", "use", "курица", "100", "g"])
    assert result.exit_code != 0
    assert pantry_rows(isolated) == []


def test_meal_done_with_date(isolated: Path) -> None:
    result = runner.invoke(main.app, ["meal", "done", "--date", "2026-01-05"])
    assert result.exit_code == 0
    assert snapshot_flag(isolated, "2026-01-05") is True
    assert runner.invoke(main.app, ["meal", "done", "--date", "вчера"]).exit_code != 0
    assert runner.invoke(main.app, ["meal", "done", "--date", "20261007"]).exit_code != 0


@pytest.mark.parametrize("args", [["add", "молоко", "1", "pcs"], ["set", "молоко", "1", "pcs"]])
def test_pantry_until_must_be_iso_date(isolated: Path, args: list[str]) -> None:
    result = runner.invoke(main.app, ["pantry", *args, "--until", "20261007"])
    assert result.exit_code != 0
    assert pantry_rows(isolated) == []


def test_pantry_open_until_must_be_iso_date(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "молоко", "1", "pcs"])
    result = runner.invoke(main.app, ["pantry", "open", "молоко", "--until", "20261007"])
    assert result.exit_code != 0
    assert len(pantry_rows(isolated)) == 1
