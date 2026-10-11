import json
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TODAY = date.today().isoformat()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.setattr(time, "sleep", lambda _: None)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("журнал не должен ходить в Garmin")

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


def set_macros(db: Path, food_id: int) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE food_log SET kcal = 350, protein_g = 12, fat_g = 6, carbs_g = 60 WHERE id = ?",
        (food_id,),
    )
    conn.commit()
    conn.close()


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


# --- --at у weight / food ---


def test_weight_at_date_gives_noon(isolated: Path) -> None:
    assert run("weight", "81.7", "--at", "2026-10-05").exit_code == 0
    assert rows(isolated, "weight_log")[0]["measured_at"] == "2026-10-05 12:00:00"


def test_weight_at_date_and_time(isolated: Path) -> None:
    assert run("weight", "81.7", "--at", "2026-10-05 07:30").exit_code == 0
    assert rows(isolated, "weight_log")[0]["measured_at"] == "2026-10-05 07:30:00"


def test_food_at_date_gives_noon(isolated: Path) -> None:
    assert run("food", "борщ", "--at", "2026-10-05").exit_code == 0
    assert rows(isolated, "food_log")[0]["logged_at"] == "2026-10-05 12:00:00"


def test_food_at_date_and_time(isolated: Path) -> None:
    assert run("food", "борщ", "--at", "2026-10-05 19:15").exit_code == 0
    assert rows(isolated, "food_log")[0]["logged_at"] == "2026-10-05 19:15:00"


def test_weight_at_today_is_allowed(isolated: Path) -> None:
    assert run("weight", "81.7", "--at", TODAY).exit_code == 0


def test_food_at_today_is_allowed(isolated: Path) -> None:
    assert run("food", "борщ", "--at", TODAY).exit_code == 0


def test_at_today_is_never_in_future(isolated: Path) -> None:
    assert run("weight", "81.7", "--at", TODAY).exit_code == 0
    stored = datetime.fromisoformat(rows(isolated, "weight_log")[0]["measured_at"])
    assert stored <= datetime.now()
    assert stored <= datetime.fromisoformat(f"{TODAY} 12:00:00")


@pytest.mark.parametrize(
    "value",
    [
        "вчера",
        "2026-13-45",
        "2026-10-05 25:00",
        "2026-10-05 12:60",
        "05.10.2026",
        "20261007",
        "2026-10-5 12:00",
        "",
    ],
)
def test_garbage_at_is_rejected_and_not_saved(isolated: Path, value: str) -> None:
    assert run("weight", "81.7", "--at", value).exit_code != 0
    assert run("food", "борщ", "--at", value).exit_code != 0
    assert rows(isolated, "weight_log") == []
    assert rows(isolated, "food_log") == []


@pytest.mark.parametrize("value", [TOMORROW, "2999-01-01", f"{TOMORROW} 00:00"])
def test_future_at_is_rejected_and_not_saved(isolated: Path, value: str) -> None:
    assert run("weight", "81.7", "--at", value).exit_code != 0
    assert run("food", "борщ", "--at", value).exit_code != 0
    assert rows(isolated, "weight_log") == []
    assert rows(isolated, "food_log") == []


def test_future_time_today_is_rejected(isolated: Path) -> None:
    if time.strftime("%H:%M") >= "23:59":
        pytest.skip("слишком близко к полуночи")
    assert run("weight", "81.7", "--at", f"{TODAY} 23:59").exit_code != 0
    assert run("food", "борщ", "--at", f"{TODAY} 23:59").exit_code != 0
    assert rows(isolated, "weight_log") == []
    assert rows(isolated, "food_log") == []


def test_without_at_time_is_now(isolated: Path) -> None:
    run("weight", "81.7")
    assert rows(isolated, "weight_log")[0]["measured_at"].startswith(TODAY)


# --- coach edit weight ---


def test_edit_weight_value(isolated: Path) -> None:
    run("weight", "81.7")
    wid = rows(isolated, "weight_log")[0]["id"]
    before = rows(isolated, "weight_log")[0]["measured_at"]
    assert run("edit", "weight", str(wid), "80,4").exit_code == 0
    row = rows(isolated, "weight_log")[0]
    assert (row["weight_kg"], row["measured_at"]) == (80.4, before)


def test_edit_weight_time_only(isolated: Path) -> None:
    run("weight", "81.7")
    wid = rows(isolated, "weight_log")[0]["id"]
    assert run("edit", "weight", str(wid), "--at", "2026-10-01 06:45").exit_code == 0
    row = rows(isolated, "weight_log")[0]
    assert (row["weight_kg"], row["measured_at"]) == (81.7, "2026-10-01 06:45:00")


def test_edit_weight_value_and_time(isolated: Path) -> None:
    run("weight", "81.7")
    wid = rows(isolated, "weight_log")[0]["id"]
    assert run("edit", "weight", str(wid), "80.0", "--at", "2026-10-01").exit_code == 0
    row = rows(isolated, "weight_log")[0]
    assert (row["weight_kg"], row["measured_at"]) == (80.0, "2026-10-01 12:00:00")


def test_edit_weight_touches_only_that_row(isolated: Path) -> None:
    run("weight", "81.7")
    run("weight", "82.0")
    first, second = [r["id"] for r in rows(isolated, "weight_log")]
    run("edit", "weight", str(second), "79.0")
    assert [r["weight_kg"] for r in rows(isolated, "weight_log")] == [81.7, 79.0]
    assert first != second


def test_edit_weight_without_changes_is_rejected(isolated: Path) -> None:
    run("weight", "81.7")
    wid = rows(isolated, "weight_log")[0]["id"]
    assert run("edit", "weight", str(wid)).exit_code != 0


@pytest.mark.parametrize("value", ["abc", "19.9", "300.1", "nan", "inf"])
def test_edit_weight_bad_value_is_rejected(isolated: Path, value: str) -> None:
    run("weight", "81.7")
    wid = rows(isolated, "weight_log")[0]["id"]
    assert run("edit", "weight", str(wid), value).exit_code != 0
    assert rows(isolated, "weight_log")[0]["weight_kg"] == 81.7


@pytest.mark.parametrize("value", ["мусор", TOMORROW])
def test_edit_weight_bad_or_future_at_is_rejected(isolated: Path, value: str) -> None:
    run("weight", "81.7")
    row = rows(isolated, "weight_log")[0]
    assert run("edit", "weight", str(row["id"]), "--at", value).exit_code != 0
    assert rows(isolated, "weight_log")[0]["measured_at"] == row["measured_at"]


def test_edit_unknown_weight_is_error(isolated: Path) -> None:
    run("weight", "81.7")
    assert run("edit", "weight", "999", "80").exit_code != 0
    assert rows(isolated, "weight_log")[0]["weight_kg"] == 81.7


def test_edit_deleted_weight_is_rejected(isolated: Path) -> None:
    run("weight", "81.7")
    wid = rows(isolated, "weight_log")[0]["id"]
    run("delete", "weight", str(wid))
    assert run("edit", "weight", str(wid), "70").exit_code != 0
    assert rows(isolated, "weight_log")[0]["weight_kg"] == 81.7


# --- coach edit food ---


def test_edit_food_text_resets_macros(isolated: Path) -> None:
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    set_macros(isolated, fid)
    assert run("edit", "food", str(fid), "гречка с курицей").exit_code == 0
    row = rows(isolated, "food_log")[0]
    assert row["text"] == "гречка с курицей"
    assert (row["kcal"], row["protein_g"], row["fat_g"], row["carbs_g"]) == (None,) * 4


def test_edit_food_time_only_keeps_text(isolated: Path) -> None:
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    assert run("edit", "food", str(fid), "--at", "2026-10-01 08:10").exit_code == 0
    row = rows(isolated, "food_log")[0]
    assert (row["text"], row["logged_at"]) == ("каша", "2026-10-01 08:10:00")


def test_edit_food_text_and_time(isolated: Path) -> None:
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    assert run("edit", "food", str(fid), "борщ", "--at", "2026-10-01").exit_code == 0
    row = rows(isolated, "food_log")[0]
    assert (row["text"], row["logged_at"]) == ("борщ", "2026-10-01 12:00:00")


def test_edit_food_without_changes_is_rejected(isolated: Path) -> None:
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    assert run("edit", "food", str(fid)).exit_code != 0


@pytest.mark.parametrize("text", ["", "   "])
def test_edit_food_empty_text_is_rejected(isolated: Path, text: str) -> None:
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    assert run("edit", "food", str(fid), text).exit_code != 0
    assert rows(isolated, "food_log")[0]["text"] == "каша"


@pytest.mark.parametrize("value", ["мусор", TOMORROW])
def test_edit_food_bad_or_future_at_is_rejected(isolated: Path, value: str) -> None:
    run("food", "каша")
    row = rows(isolated, "food_log")[0]
    assert run("edit", "food", str(row["id"]), "--at", value).exit_code != 0
    assert rows(isolated, "food_log")[0]["logged_at"] == row["logged_at"]


def test_edit_unknown_food_is_error(isolated: Path) -> None:
    run("food", "каша")
    assert run("edit", "food", "999", "борщ").exit_code != 0
    assert rows(isolated, "food_log")[0]["text"] == "каша"


def test_edit_deleted_food_is_rejected(isolated: Path) -> None:
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    run("delete", "food", str(fid))
    assert run("edit", "food", str(fid), "борщ").exit_code != 0
    assert rows(isolated, "food_log")[0]["text"] == "каша"


def test_edit_food_does_not_touch_weight_with_same_id(isolated: Path) -> None:
    run("weight", "81.7")
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    run("edit", "food", str(fid), "борщ")
    assert rows(isolated, "weight_log")[0]["weight_kg"] == 81.7


# --- coach delete ---


def test_delete_weight_marks_row(isolated: Path) -> None:
    run("weight", "81.7")
    wid = rows(isolated, "weight_log")[0]["id"]
    assert run("delete", "weight", str(wid)).exit_code == 0
    row = rows(isolated, "weight_log")[0]
    assert row["deleted_at"] is not None
    assert row["weight_kg"] == 81.7


def test_delete_food_marks_row(isolated: Path) -> None:
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    assert run("delete", "food", str(fid)).exit_code == 0
    row = rows(isolated, "food_log")[0]
    assert row["deleted_at"] is not None
    assert row["text"] == "каша"


def test_delete_touches_only_that_row(isolated: Path) -> None:
    run("food", "каша")
    run("food", "суп")
    first = rows(isolated, "food_log")[0]["id"]
    run("delete", "food", str(first))
    assert [r["deleted_at"] is None for r in rows(isolated, "food_log")] == [False, True]


def test_delete_weight_does_not_touch_food(isolated: Path) -> None:
    run("weight", "81.7")
    run("food", "каша")
    wid = rows(isolated, "weight_log")[0]["id"]
    run("delete", "weight", str(wid))
    assert rows(isolated, "food_log")[0]["deleted_at"] is None


@pytest.mark.parametrize("kind", ["weight", "food"])
def test_delete_twice_is_error(isolated: Path, kind: str) -> None:
    if kind == "weight":
        run("weight", "81.7")
        entry = rows(isolated, "weight_log")[0]["id"]
    else:
        run("food", "каша")
        entry = rows(isolated, "food_log")[0]["id"]
    assert run("delete", kind, str(entry)).exit_code == 0
    assert run("delete", kind, str(entry)).exit_code != 0


@pytest.mark.parametrize("kind", ["weight", "food"])
def test_delete_unknown_is_error(isolated: Path, kind: str) -> None:
    assert run("delete", kind, "999").exit_code != 0


def test_delete_without_id_is_rejected(isolated: Path) -> None:
    assert run("delete", "weight").exit_code != 0
    assert run("delete", "food").exit_code != 0


def test_delete_with_non_number_id_is_rejected(isolated: Path) -> None:
    run("weight", "81.7")
    assert run("delete", "weight", "abc").exit_code != 0
    assert rows(isolated, "weight_log")[0]["deleted_at"] is None


# --- coach log ---


def test_log_weight_shows_id_and_value_for_today(isolated: Path) -> None:
    run("weight", "81.7")
    wid = rows(isolated, "weight_log")[0]["id"]
    result = run("log", "weight")
    assert result.exit_code == 0
    assert str(wid) in result.output
    assert "81.7" in result.output


def test_log_food_shows_id_and_text_for_today(isolated: Path) -> None:
    run("food", "овсянка с бананом")
    fid = rows(isolated, "food_log")[0]["id"]
    result = run("log", "food")
    assert result.exit_code == 0
    assert str(fid) in result.output
    assert "овсянка с бананом" in result.output


def test_log_default_is_today_only(isolated: Path) -> None:
    run("food", "вчерашний борщ", "--at", YESTERDAY)
    run("food", "сегодняшняя каша")
    output = run("log", "food").output
    assert "сегодняшняя каша" in output
    assert "вчерашний борщ" not in output


def test_log_with_date(isolated: Path) -> None:
    run("food", "вчерашний борщ", "--at", YESTERDAY)
    run("food", "сегодняшняя каша")
    output = run("log", "food", "--date", YESTERDAY).output
    assert "вчерашний борщ" in output
    assert "сегодняшняя каша" not in output


def test_log_weight_with_date(isolated: Path) -> None:
    run("weight", "79.1", "--at", YESTERDAY)
    run("weight", "81.7")
    output = run("log", "weight", "--date", YESTERDAY).output
    assert "79.1" in output
    assert "81.7" not in output


def test_log_hides_deleted(isolated: Path) -> None:
    run("food", "каша")
    run("food", "суп")
    first = rows(isolated, "food_log")[0]["id"]
    run("delete", "food", str(first))
    output = run("log", "food").output
    assert "каша" not in output
    assert "суп" in output


def test_log_shows_edited_text(isolated: Path) -> None:
    run("food", "каша")
    fid = rows(isolated, "food_log")[0]["id"]
    run("edit", "food", str(fid), "гречка")
    output = run("log", "food").output
    assert "гречка" in output
    assert "каша" not in output


def test_log_is_read_only(isolated: Path) -> None:
    run("weight", "81.7")
    run("food", "каша")
    before = (rows(isolated, "weight_log")[0]["weight_kg"], rows(isolated, "food_log")[0]["text"])
    run("log", "weight")
    run("log", "food")
    assert len(rows(isolated, "weight_log")) == 1
    assert len(rows(isolated, "food_log")) == 1
    assert before == (81.7, "каша")


def test_log_on_empty_day_is_not_an_error(isolated: Path) -> None:
    assert run("log", "weight").exit_code == 0
    assert run("log", "food").exit_code == 0


def test_log_bad_date_is_rejected(isolated: Path) -> None:
    assert run("log", "food", "--date", "вчера").exit_code != 0
    assert run("log", "weight", "--date", "2026-13-45").exit_code != 0


def test_log_unknown_kind_is_rejected(isolated: Path) -> None:
    assert run("log", "pantry").exit_code != 0


# --- allow ---


def allow() -> list[str]:
    return json.loads(SETTINGS.read_text())["permissions"]["allow"]


def test_edit_and_delete_are_not_in_allow() -> None:
    rules = allow()
    assert not [r for r in rules if "coach edit" in r]
    assert not [r for r in rules if "coach delete" in r]


def test_allow_has_no_wildcard_that_covers_edit_and_delete() -> None:
    rules = allow()
    assert "Bash(uv run coach:*)" not in rules
    assert "Bash(uv run coach *)" not in rules
    assert not [r for r in rules if r.startswith("Bash(uv run coach ed")]
    assert not [r for r in rules if r.startswith("Bash(uv run coach d") and "delete" in r]


def test_log_is_in_allow() -> None:
    assert [r for r in allow() if r.startswith("Bash(uv run coach log")]


def test_weight_and_food_stay_in_allow() -> None:
    rules = allow()
    assert "Bash(uv run coach weight:*)" in rules
    assert "Bash(uv run coach food:*)" in rules
