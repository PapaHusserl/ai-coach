from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / ".claude"
COACH = ROOT / "agents" / "coach.md"
SPEC_FORMATS = ROOT / "skills" / "coach-plan" / "spec-formats.md"
MAX_BYTES = 15360


def test_coach_md_is_at_most_15360_bytes() -> None:
    assert len(COACH.read_bytes()) <= MAX_BYTES


def test_coach_has_link_tool_in_tools_line() -> None:
    tools_line = next(x for x in COACH.read_text().splitlines() if x.startswith("tools:"))
    assert "mcp__ai-coach__get_workout_link" in tools_line


def test_coach_body_tells_when_to_give_link() -> None:
    body = COACH.read_text().split("---", 2)[2]
    assert "get_workout_link" in body
    assert "телефон" in body
    assert "нет часов" in body


def test_coach_body_says_show_link_as_is() -> None:
    body = COACH.read_text().split("---", 2)[2]
    assert "как есть" in body


def test_spec_formats_mention_title_and_note() -> None:
    text = SPEC_FORMATS.read_text()
    assert "title" in text
    assert "note" in text
