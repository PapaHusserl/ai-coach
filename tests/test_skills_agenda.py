"""Тексты шага v2.6: роль coach-agenda.md, триггер в coach.md, allow для event list/cancel."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / ".claude"
AGENTS = ROOT / "agents"
ALLOW = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
AGENDA = AGENTS / "coach-agenda.md"
EVENING = ROOT / "skills" / "coach-evening" / "SKILL.md"


def coach_text() -> str:
    return (AGENTS / "coach.md").read_text()


def test_agenda_file_exists_and_within_limit() -> None:
    assert AGENDA.is_file()
    assert 0 < len(AGENDA.read_bytes()) <= 6144


def test_coach_md_within_limit() -> None:
    assert len((AGENTS / "coach.md").read_bytes()) <= 15360


def test_coach_md_reads_agenda_file_by_cat_and_it_is_allowed() -> None:
    assert "cat .claude/agents/coach-agenda.md" in coach_text()
    assert "Bash(cat .claude/agents/coach-agenda.md)" in ALLOW


def test_coach_md_has_agenda_tools() -> None:
    head = coach_text().split("---")[1]
    for name in ("create_draft_event", "cancel_draft_event", "get_agenda"):
        assert f"mcp__ai-coach__{name}" in head


def test_agenda_file_mentions_tools_and_commands() -> None:
    text = AGENDA.read_text()
    for word in ("create_draft_event", "cancel_draft_event", "get_agenda"):
        assert word in text
    assert "uv run coach event write" in text
    assert "uv run coach event remove" in text


def test_agenda_file_requires_user_confirmation() -> None:
    assert "да" in AGENDA.read_text()


def test_event_list_and_cancel_are_allowed() -> None:
    assert "Bash(uv run coach event list:*)" in ALLOW
    assert "Bash(uv run coach event cancel:*)" in ALLOW


def test_event_write_and_remove_are_not_allowed() -> None:
    for entry in ALLOW:
        assert "coach event write" not in entry
        assert "coach event remove" not in entry
        assert "coach event:*" not in entry
        assert "coach event *" not in entry


def test_side_roles_point_to_agenda_file() -> None:
    for name in ("coach-wellbeing.md", "coach-week.md"):
        assert "coach-agenda.md" in (AGENTS / name).read_text(), name


def test_evening_role_does_not_mention_agenda() -> None:
    assert "coach-agenda" not in EVENING.read_text()


def test_wellbeing_file_within_limit() -> None:
    assert len((AGENTS / "coach-wellbeing.md").read_bytes()) <= 7168
