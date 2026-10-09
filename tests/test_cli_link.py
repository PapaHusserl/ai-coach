import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.mcp_server.tools import cancel_draft_workout, create_draft_workout
from ai_coach.store.db import open_db
from ai_coach.workouts import phone

runner = CliRunner()
SETTINGS = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"
BASE = "https://example.test/player/"
SPEC = {"steps": [{"type": "interval", "meters": 5000}]}


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.setenv("AI_COACH_PLAYER_URL", BASE)
    monkeypatch.chdir(tmp_path)

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("ссылка не должна ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


def run(*args: str) -> Any:
    return runner.invoke(main.app, list(args))


def make_draft(db: Path, cancel: bool = False) -> int:
    conn = open_db(db)
    try:
        draft_id = create_draft_workout(conn, "2026-10-08", "run", "Бег 5 км", SPEC)["draft_id"]
        if cancel:
            cancel_draft_workout(conn, draft_id)
        return draft_id
    finally:
        conn.close()


def payload_of(output: str) -> dict[str, Any]:
    url = output.strip()
    assert url.startswith(BASE + "#v1.")
    return phone.decode_fragment(url[len(BASE) + 1 :])


def test_link_prints_url(isolated: Path) -> None:
    result = run("link", str(make_draft(isolated)))
    assert result.exit_code == 0, result.output
    assert payload_of(result.output)["n"] == "Бег 5 км"


def test_link_prints_only_url(isolated: Path) -> None:
    result = run("link", str(make_draft(isolated)))
    assert len(result.output.strip().splitlines()) == 1


def test_link_without_time_has_no_tm(isolated: Path) -> None:
    result = run("link", str(make_draft(isolated)))
    assert "tm" not in payload_of(result.output)


def test_link_with_time(isolated: Path) -> None:
    result = run("link", str(make_draft(isolated)), "--time", "07:30")
    assert result.exit_code == 0, result.output
    assert payload_of(result.output)["tm"] == "07:30"


def test_link_bad_time_fails(isolated: Path) -> None:
    result = run("link", str(make_draft(isolated)), "--time", "7:30")
    assert result.exit_code != 0


def test_link_unknown_id_fails(isolated: Path) -> None:
    result = run("link", "999")
    assert result.exit_code != 0
    assert "#v1." not in result.output


def test_link_cancelled_fails(isolated: Path) -> None:
    result = run("link", str(make_draft(isolated, cancel=True)))
    assert result.exit_code != 0
    assert "#v1." not in result.output


def test_link_without_player_url_fails(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft_id = make_draft(isolated)
    monkeypatch.delenv("AI_COACH_PLAYER_URL")
    monkeypatch.setattr(phone, "PLAYER_URL", "")
    result = run("link", str(draft_id))
    assert result.exit_code != 0
    assert "адрес плеера" in result.output


def test_link_is_allowed_without_prompt() -> None:
    allow = json.loads(SETTINGS.read_text())["permissions"]["allow"]
    assert "Bash(uv run coach link:*)" in allow
