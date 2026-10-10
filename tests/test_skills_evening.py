import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
EVENING = CLAUDE / "skills" / "coach-evening" / "SKILL.md"


def allow() -> list[str]:
    return json.loads((CLAUDE / "settings.json").read_text())["permissions"]["allow"]


def test_evening_skill_exists_and_is_short() -> None:
    assert EVENING.is_file()
    assert len(EVENING.read_bytes()) <= 3072


def test_evening_skill_has_front_matter() -> None:
    head = EVENING.read_text().split("---")[1]
    assert "name: coach-evening" in head
    assert "description:" in head


def test_evening_skill_uses_feel_with_all_options() -> None:
    text = EVENING.read_text()
    for option in ("--mood", "--stress", "--work", "--hobby", "--rest"):
        assert option in text


def test_evening_skill_reads_snapshot_and_checks_evening_done() -> None:
    text = EVENING.read_text()
    assert "get_morning_snapshot" in text
    assert "evening_done_today" in text


def test_evening_skill_tools_are_in_allowed_tools() -> None:
    head = EVENING.read_text().split("---")[1]
    assert "mcp__ai-coach__get_morning_snapshot" in head


def test_feel_command_is_allowed() -> None:
    assert "Bash(uv run coach feel:*)" in allow()


def test_trener_launcher_takes_evening_argument() -> None:
    text = (ROOT / "bin" / "trener").read_text()
    assert "вечер" in text


def test_coach_knows_the_evening_skill_and_overload_tool() -> None:
    coach = (CLAUDE / "agents" / "coach.md").read_text()
    assert "coach-evening" in coach
    assert "get_overload" in coach or "overload" in coach


def test_wellbeing_file_describes_overload_reaction() -> None:
    text = (CLAUDE / "agents" / "coach-wellbeing.md").read_text()
    assert "overload" in text
    assert "overloaded" in text


def test_coach_stays_within_limit_after_v23() -> None:
    assert len((CLAUDE / "agents" / "coach.md").read_bytes()) <= 15360
