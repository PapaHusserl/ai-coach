import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from mcp_fakes import call
from typer.testing import CliRunner

from ai_coach.cli import main

runner = CliRunner()
SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"


def days_from_now(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("pantry не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def pantry_rows(db: Path) -> list[sqlite3.Row]:
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM pantry_log ORDER BY id").fetchall()
    finally:
        conn.close()


def stock_rows(db: Path) -> dict[str, dict[str, Any]]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return {r["item"]: r for r in call(conn, "get_pantry")["rows"]}
    finally:
        conn.close()


def test_add_with_until_saves_expiry(isolated: Path) -> None:
    until = days_from_now(5)
    result = runner.invoke(main.app, ["pantry", "add", "молоко", "1000", "ml", "--until", until])
    assert result.exit_code == 0
    row = pantry_rows(isolated)[0]
    assert row["expires_on"] == until
    assert not row["opened"]


def test_add_with_opened_and_until(isolated: Path) -> None:
    until = days_from_now(3)
    args = ["pantry", "add", "молоко", "1000", "ml", "--opened", "--until", until]
    assert runner.invoke(main.app, args).exit_code == 0
    row = pantry_rows(isolated)[0]
    assert row["expires_on"] == until
    assert row["opened"] == 1


def test_add_without_until_has_no_expiry(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "рис", "1000", "g"])
    row = pantry_rows(isolated)[0]
    assert row["expires_on"] is None
    assert not row["opened"]


@pytest.mark.parametrize("bad", ["завтра", "2026-13-40", "10.10.2026"])
def test_add_with_bad_until_is_an_error_and_writes_nothing(isolated: Path, bad: str) -> None:
    result = runner.invoke(main.app, ["pantry", "add", "молоко", "1", "ml", "--until", bad])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert pantry_rows(isolated) == []


def test_open_changes_expiry_without_changing_qty(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "молоко", "1000", "ml", "--until", days_from_now(30)])
    until = days_from_now(3)
    result = runner.invoke(main.app, ["pantry", "open", "молоко", "--until", until])
    assert result.exit_code == 0
    row = stock_rows(isolated)["молоко"]
    assert row["qty"] == 1000
    assert row["expires_on"] == until
    assert row["opened"]
    assert pantry_rows(isolated)[-1]["op"] == "open"


def test_open_unknown_item_is_an_error(isolated: Path) -> None:
    result = runner.invoke(main.app, ["pantry", "open", "молоко", "--until", days_from_now(3)])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert pantry_rows(isolated) == []


def test_open_without_until_is_an_error(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "молоко", "1000", "ml"])
    result = runner.invoke(main.app, ["pantry", "open", "молоко"])
    assert result.exit_code != 0
    assert len(pantry_rows(isolated)) == 1


def test_spoil_with_qty_reduces_stock_and_writes_op_spoil(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "молоко", "1000", "ml", "--until", days_from_now(-1)])
    result = runner.invoke(main.app, ["pantry", "spoil", "молоко", "400", "ml"])
    assert result.exit_code == 0
    assert stock_rows(isolated)["молоко"]["qty"] == 600
    assert pantry_rows(isolated)[-1]["op"] == "spoil"


def test_spoil_without_qty_writes_off_whole_overdue_stock(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "молоко", "1000", "ml", "--until", days_from_now(-1)])
    result = runner.invoke(main.app, ["pantry", "spoil", "молоко"])
    assert result.exit_code == 0
    assert "молоко" not in stock_rows(isolated)
    assert pantry_rows(isolated)[-1]["op"] == "spoil"


def test_spoil_without_qty_leaves_not_overdue_batch(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "молоко", "300", "ml", "--until", days_from_now(-1)])
    runner.invoke(main.app, ["pantry", "add", "молоко", "700", "ml", "--until", days_from_now(10)])
    runner.invoke(main.app, ["pantry", "spoil", "молоко"])
    assert stock_rows(isolated)["молоко"]["qty"] == 700


def test_spoil_unknown_item_is_an_error(isolated: Path) -> None:
    result = runner.invoke(main.app, ["pantry", "spoil", "молоко"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert pantry_rows(isolated) == []


def test_spoil_with_qty_but_without_unit_is_an_error(isolated: Path) -> None:
    runner.invoke(main.app, ["pantry", "add", "молоко", "1000", "ml"])
    result = runner.invoke(main.app, ["pantry", "spoil", "молоко", "400"])
    assert result.exit_code != 0
    assert len(pantry_rows(isolated)) == 1


def test_pantry_list_shows_expiry_date(isolated: Path) -> None:
    until = days_from_now(4)
    runner.invoke(main.app, ["pantry", "add", "молоко", "1000", "ml", "--until", until])
    result = runner.invoke(main.app, ["pantry", "list"])
    assert result.exit_code == 0
    assert until in result.output


def test_settings_allow_open_but_not_spoil() -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert "Bash(uv run coach pantry open:*)" in allow
    assert not [rule for rule in allow if "spoil" in rule]
    assert "Bash(uv run coach pantry:*)" not in allow
    assert "Bash(uv run coach:*)" not in allow


def test_set_with_until_and_opened(isolated: Path) -> None:
    until = days_from_now(4)
    args = ["pantry", "set", "молоко", "300", "ml", "--opened", "--until", until]
    assert runner.invoke(main.app, args).exit_code == 0
    row = pantry_rows(isolated)[0]
    assert row["op"] == "set"
    assert row["expires_on"] == until
    assert row["opened"] == 1
