import sqlite3
import time
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """База — во временной папке; Garmin и сеть недоступны: любая попытка войти — ошибка."""
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.setattr(time, "sleep", lambda _: None)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("weight/food не должны ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def rows(db: Path, table: str) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
    finally:
        conn.close()


def test_weight_is_saved(isolated: Path) -> None:
    result = runner.invoke(main.app, ["weight", "81.7"])
    assert result.exit_code == 0
    saved = rows(isolated, "weight_log")
    assert [r["weight_kg"] for r in saved] == [81.7]


def test_weight_is_saved_with_todays_date(isolated: Path) -> None:
    runner.invoke(main.app, ["weight", "81.7"])
    assert rows(isolated, "weight_log")[0]["measured_at"].startswith(date.today().isoformat())


def test_two_weights_in_a_day_are_two_rows(isolated: Path) -> None:
    runner.invoke(main.app, ["weight", "81.7"])
    runner.invoke(main.app, ["weight", "81.2"])
    assert [r["weight_kg"] for r in rows(isolated, "weight_log")] == [81.7, 81.2]


def test_integer_weight_is_accepted(isolated: Path) -> None:
    result = runner.invoke(main.app, ["weight", "82"])
    assert result.exit_code == 0
    assert [r["weight_kg"] for r in rows(isolated, "weight_log")] == [82.0]


@pytest.mark.parametrize(
    "value", ["abc", "0", "-5", "19.9", "300.1", "1000", "nan", "inf", "-inf", ""]
)
def test_bad_weight_is_rejected_and_not_saved(isolated: Path, value: str) -> None:
    result = runner.invoke(main.app, ["weight", value])
    assert result.exit_code != 0
    assert rows(isolated, "weight_log") == []


@pytest.mark.parametrize("value", ["81,7", "81.7"])
def test_weight_accepts_comma_and_dot(isolated: Path, value: str) -> None:
    result = runner.invoke(main.app, ["weight", value])
    assert result.exit_code == 0
    assert [r["weight_kg"] for r in rows(isolated, "weight_log")] == [81.7]


@pytest.mark.parametrize("value", ["20", "300"])
def test_weight_limits_are_inclusive(isolated: Path, value: str) -> None:
    assert runner.invoke(main.app, ["weight", value]).exit_code == 0


def test_weight_without_value_is_rejected(isolated: Path) -> None:
    result = runner.invoke(main.app, ["weight"])
    assert result.exit_code != 0
    assert rows(isolated, "weight_log") == []


def test_food_is_saved_as_raw_text_without_macros(isolated: Path) -> None:
    result = runner.invoke(main.app, ["food", "овсянка с бананом, 2 яйца"])
    assert result.exit_code == 0
    row = rows(isolated, "food_log")[0]
    assert row["text"] == "овсянка с бананом, 2 яйца"
    assert (row["kcal"], row["protein_g"], row["fat_g"], row["carbs_g"]) == (None,) * 4


def test_food_is_saved_with_todays_date(isolated: Path) -> None:
    runner.invoke(main.app, ["food", "борщ"])
    assert rows(isolated, "food_log")[0]["logged_at"].startswith(date.today().isoformat())


def test_several_food_entries_in_a_day_are_separate_rows(isolated: Path) -> None:
    runner.invoke(main.app, ["food", "завтрак: каша"])
    runner.invoke(main.app, ["food", "обед: борщ"])
    assert [r["text"] for r in rows(isolated, "food_log")] == ["завтрак: каша", "обед: борщ"]


def test_food_text_is_stored_as_is(isolated: Path) -> None:
    text = "  пицца; DROP TABLE food_log;--  'кола'\nещё строка  "
    runner.invoke(main.app, ["food", text])
    assert rows(isolated, "food_log")[0]["text"].strip() == text.strip()


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_food_is_rejected_and_not_saved(isolated: Path, text: str) -> None:
    result = runner.invoke(main.app, ["food", text])
    assert result.exit_code != 0
    assert rows(isolated, "food_log") == []


def test_food_without_text_is_rejected(isolated: Path) -> None:
    result = runner.invoke(main.app, ["food"])
    assert result.exit_code != 0
    assert rows(isolated, "food_log") == []


def test_weight_and_food_do_not_touch_each_other(isolated: Path) -> None:
    runner.invoke(main.app, ["weight", "81.7"])
    assert rows(isolated, "food_log") == []
    runner.invoke(main.app, ["food", "борщ"])
    assert len(rows(isolated, "weight_log")) == 1
