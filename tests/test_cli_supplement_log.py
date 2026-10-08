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
TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("журнал приёма не должен ходить в Garmin")

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


def intake_rows(db: Path) -> list[sqlite3.Row]:
    return table_rows(db, "intake_log")


def add_supplement(name: str = "креатин") -> Any:
    return run("supplement", "add", name, "--dose", "5", "--unit", "g", "--schedule", "daily")


def supplement_id(db: Path, index: int = 0) -> str:
    return str(table_rows(db, "supplement")[index]["id"])


# --- take ---


def test_take_by_name_saves_row_for_today(isolated: Path) -> None:
    add_supplement()
    result = run("supplement", "take", "креатин")
    assert result.exit_code == 0
    row = intake_rows(isolated)[0]
    assert (row["kind"], row["item_id"], row["date"]) == ("supplement", 1, TODAY)
    assert (row["dose"], row["note"], row["deleted_at"]) == (None, None, None)
    assert row["taken_at"].startswith(TODAY)


def test_take_prints_log_id(isolated: Path) -> None:
    add_supplement()
    result = run("supplement", "take", "креатин")
    assert str(intake_rows(isolated)[0]["id"]) in result.output


def test_take_by_id(isolated: Path) -> None:
    add_supplement()
    assert run("supplement", "take", supplement_id(isolated)).exit_code == 0
    assert intake_rows(isolated)[0]["item_id"] == int(supplement_id(isolated))


def test_take_name_ignores_case(isolated: Path) -> None:
    add_supplement("креатин")
    assert run("supplement", "take", "КРЕАТИН").exit_code == 0
    assert len(intake_rows(isolated)) == 1


def test_take_with_dose_and_note(isolated: Path) -> None:
    add_supplement()
    result = run("supplement", "take", "креатин", "--dose", "3", "--note", "с водой")
    assert result.exit_code == 0
    row = intake_rows(isolated)[0]
    assert (row["dose"], row["note"]) == (3, "с водой")


def test_take_dose_with_decimal_comma(isolated: Path) -> None:
    add_supplement()
    assert run("supplement", "take", "креатин", "--dose", "2,5").exit_code == 0
    assert intake_rows(isolated)[0]["dose"] == 2.5


def test_take_backdated(isolated: Path) -> None:
    add_supplement()
    assert run("supplement", "take", "креатин", "--date", YESTERDAY).exit_code == 0
    assert intake_rows(isolated)[0]["date"] == YESTERDAY


def test_take_several_times_a_day_is_allowed(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин")
    assert run("supplement", "take", "креатин").exit_code == 0
    assert len(intake_rows(isolated)) == 2


def test_take_does_not_change_the_supplement(isolated: Path) -> None:
    add_supplement()
    before = dict(table_rows(isolated, "supplement")[0])
    run("supplement", "take", "креатин")
    assert dict(table_rows(isolated, "supplement")[0]) == before


def test_take_unknown_name_fails_with_text(isolated: Path) -> None:
    add_supplement()
    result = run("supplement", "take", "борщ")
    assert result.exit_code == 1
    assert "'борщ' нет" in result.output
    assert intake_rows(isolated) == []


def test_take_unknown_id_fails(isolated: Path) -> None:
    add_supplement()
    result = run("supplement", "take", "99")
    assert result.exit_code == 1
    assert "99" in result.output
    assert intake_rows(isolated) == []


def test_take_deleted_supplement_fails(isolated: Path) -> None:
    add_supplement()
    run("supplement", "delete", supplement_id(isolated))
    result = run("supplement", "take", "креатин")
    assert result.exit_code == 1
    assert "'креатин' нет" in result.output
    assert intake_rows(isolated) == []


def test_take_on_empty_database_fails(isolated: Path) -> None:
    assert run("supplement", "take", "креатин").exit_code == 1


@pytest.mark.parametrize("value", ["0", "-1", "много"])
def test_take_bad_dose_fails_and_saves_nothing(isolated: Path, value: str) -> None:
    add_supplement()
    result = run("supplement", "take", "креатин", "--dose", value)
    assert result.exit_code == 1
    assert "--dose" in result.output
    assert intake_rows(isolated) == []


def test_take_zero_dose_has_text(isolated: Path) -> None:
    add_supplement()
    result = run("supplement", "take", "креатин", "--dose", "0")
    assert "--dose должна быть больше 0." in result.output


@pytest.mark.parametrize("value", ["08.10.2026", "вчера", "2026-13-01", "2026-1-5"])
def test_take_bad_date_fails_with_text(isolated: Path, value: str) -> None:
    add_supplement()
    result = run("supplement", "take", "креатин", "--date", value)
    assert result.exit_code == 1
    assert "Дата должна быть YYYY-MM-DD" in result.output
    assert intake_rows(isolated) == []


def test_take_without_key_fails(isolated: Path) -> None:
    assert run("supplement", "take").exit_code != 0


def test_take_keeps_supplement_commands_working(isolated: Path) -> None:
    add_supplement()
    assert "креатин" in run("supplement", "list").output
    assert run("supplement", "show", "креатин").exit_code == 0


def test_take_future_date_fails(isolated: Path) -> None:
    add_supplement()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    result = run("supplement", "take", "креатин", "--date", tomorrow)
    assert result.exit_code == 1
    assert "--date в будущем." in result.output
    assert intake_rows(isolated) == []


def test_take_today_is_not_future(isolated: Path) -> None:
    add_supplement()
    assert run("supplement", "take", "креатин", "--date", TODAY).exit_code == 0


# --- log ---


def test_log_shows_time_of_intake(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин")
    stamp = intake_rows(isolated)[0]["taken_at"]
    assert stamp[11:16] in run("supplement", "log").output


def test_log_empty_says_no_intakes(isolated: Path) -> None:
    result = run("supplement", "log")
    assert result.exit_code == 0
    assert "Приёмов нет." in result.output


def test_log_without_options_shows_today(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин", "--dose", "3")
    run("supplement", "take", "креатин", "--date", YESTERDAY, "--note", "вчерашний")
    result = run("supplement", "log")
    assert result.exit_code == 0
    assert "креатин" in result.output
    assert "вчерашний" not in result.output
    assert "Приёмов нет." not in result.output


def test_log_shows_id_dose_and_note(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин", "--dose", "3", "--note", "с водой")
    result = run("supplement", "log")
    for part in [str(intake_rows(isolated)[0]["id"]), "креатин", "3", "с водой"]:
        assert part in result.output


def test_log_by_date(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин", "--date", YESTERDAY, "--note", "вчерашний")
    assert "вчерашний" in run("supplement", "log", "--date", YESTERDAY).output
    assert "Приёмов нет." in run("supplement", "log").output


def test_log_day_without_intakes_says_no_intakes(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин")
    assert "Приёмов нет." in run("supplement", "log", "--date", "2026-01-01").output


def test_log_by_range_is_inclusive(isolated: Path) -> None:
    add_supplement()
    for day, note in [("2026-10-05", "n5"), ("2026-10-06", "n6"), ("2026-10-08", "n8")]:
        run("supplement", "take", "креатин", "--date", day, "--note", note)
    run("supplement", "take", "креатин", "--date", "2026-10-09", "--note", "n9")
    out = run("supplement", "log", "--from", "2026-10-06", "--to", "2026-10-08").output
    assert "n6" in out
    assert "n8" in out
    assert "n5" not in out
    assert "n9" not in out


def test_log_shows_several_supplements(isolated: Path) -> None:
    add_supplement("креатин")
    add_supplement("магний")
    run("supplement", "take", "креатин")
    run("supplement", "take", "магний")
    out = run("supplement", "log").output
    assert "креатин" in out
    assert "магний" in out


def test_log_shows_name_of_deleted_supplement(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин")
    run("supplement", "delete", supplement_id(isolated))
    assert "креатин" in run("supplement", "log").output


@pytest.mark.parametrize("option", ["--date", "--from", "--to"])
def test_log_bad_date_fails_with_text(isolated: Path, option: str) -> None:
    args = ["supplement", "log", option, "08.10.2026"]
    if option == "--from":
        args += ["--to", TODAY]
    if option == "--to":
        args = ["supplement", "log", "--from", TODAY, "--to", "08.10.2026"]
    result = run(*args)
    assert result.exit_code == 1
    assert "Дата должна быть YYYY-MM-DD" in result.output


# --- untake ---


def test_untake_marks_row_and_hides_from_log(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин", "--note", "лишний")
    lid = str(intake_rows(isolated)[0]["id"])
    result = run("supplement", "untake", lid)
    assert result.exit_code == 0
    assert intake_rows(isolated)[0]["deleted_at"] is not None
    assert "лишний" not in run("supplement", "log").output
    assert "Приёмов нет." in run("supplement", "log").output


def test_untake_keeps_other_intakes(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин", "--note", "первый")
    run("supplement", "take", "креатин", "--note", "второй")
    run("supplement", "untake", str(intake_rows(isolated)[0]["id"]))
    out = run("supplement", "log").output
    assert "первый" not in out
    assert "второй" in out
    assert intake_rows(isolated)[1]["deleted_at"] is None


def test_untake_twice_fails_with_text(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин")
    lid = str(intake_rows(isolated)[0]["id"])
    run("supplement", "untake", lid)
    result = run("supplement", "untake", lid)
    assert result.exit_code == 1
    assert f"Приёма {lid} нет или он уже удалён." in result.output


def test_untake_unknown_fails_with_text(isolated: Path) -> None:
    result = run("supplement", "untake", "99")
    assert result.exit_code == 1
    assert "Приёма 99 нет или он уже удалён." in result.output


def test_untake_does_not_change_supplement(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин")
    run("supplement", "untake", str(intake_rows(isolated)[0]["id"]))
    assert table_rows(isolated, "supplement")[0]["deleted_at"] is None


def test_untake_takes_log_id_not_name(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин")
    assert run("supplement", "untake", "креатин").exit_code != 0
    assert intake_rows(isolated)[0]["deleted_at"] is None


def test_can_take_again_after_untake(isolated: Path) -> None:
    add_supplement()
    run("supplement", "take", "креатин")
    run("supplement", "untake", str(intake_rows(isolated)[0]["id"]))
    assert run("supplement", "take", "креатин").exit_code == 0
    assert len(intake_rows(isolated)) == 2


# --- allow ---


@pytest.mark.parametrize("sub", ["take", "log"])
def test_settings_allow_take_and_log(sub: str) -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert f"Bash(uv run coach supplement {sub}:*)" in allow


def test_settings_allow_has_no_untake() -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert not [r for r in allow if "untake" in r]


def test_settings_allow_has_no_wildcards_and_keeps_old_rules() -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert "Bash(uv run coach supplement:*)" not in allow
    assert "Bash(uv run coach:*)" not in allow
    assert not [r for r in allow if "supplement edit" in r or "supplement delete" in r]
    for sub in ("add", "list", "show"):
        assert f"Bash(uv run coach supplement {sub}:*)" in allow


# --- log: ошибки периода ---


@pytest.mark.parametrize(
    "extra",
    [
        ["--from", "2026-10-01", "--to", "2026-10-08"],
        ["--from", "2026-10-01"],
        ["--to", "2026-10-08"],
    ],
)
def test_log_date_with_period_fails(isolated: Path, extra: list[str]) -> None:
    result = run("supplement", "log", "--date", "2026-10-05", *extra)
    assert result.exit_code == 1
    assert "--date и --from/--to вместе нельзя." in result.output


@pytest.mark.parametrize("option", ["--from", "--to"])
def test_log_one_side_of_period_fails(isolated: Path, option: str) -> None:
    result = run("supplement", "log", option, "2026-10-05")
    assert result.exit_code == 1
    assert "--from и --to нужны вместе." in result.output


def test_log_to_before_from_fails(isolated: Path) -> None:
    result = run("supplement", "log", "--from", "2026-10-08", "--to", "2026-10-07")
    assert result.exit_code == 1
    assert "--to не может быть раньше --from." in result.output


def test_log_from_equal_to_is_allowed(isolated: Path) -> None:
    assert run("supplement", "log", "--from", "2026-10-08", "--to", "2026-10-08").exit_code == 0
