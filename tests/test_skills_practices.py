"""Тексты и лимиты шага v2.4: размеры промптов, allow для practice/habit, подсказки агенту."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
AGENTS = CLAUDE / "agents"
EVENING = CLAUDE / "skills" / "coach-evening" / "SKILL.md"
LIMITS = {
    "coach.md": 15360,
    "coach-wellbeing.md": 6144,
    "coach-nutrition.md": 6144,
    "coach-onboarding.md": 6144,
    "coach-week.md": 6144,
    "coach-agenda.md": 6144,
}


def allow() -> list[str]:
    return json.loads((CLAUDE / "settings.json").read_text())["permissions"]["allow"]


def test_coach_md_within_limit() -> None:
    assert len((AGENTS / "coach.md").read_bytes()) <= 15360


def test_wellbeing_within_limit() -> None:
    assert len((AGENTS / "coach-wellbeing.md").read_bytes()) <= 6144


def test_other_agent_files_within_their_limits() -> None:
    for name, limit in LIMITS.items():
        assert len((AGENTS / name).read_bytes()) <= limit, name


def test_every_agent_file_has_a_limit() -> None:
    assert {p.name for p in AGENTS.glob("*.md")} <= set(LIMITS)


def test_evening_skill_within_limit() -> None:
    assert len(EVENING.read_bytes()) <= 3072


def test_evening_skill_asks_about_habits() -> None:
    text = EVENING.read_text()
    assert "habits_today" in text
    assert "coach habit done" in text


def test_prompts_know_get_practices() -> None:
    texts = (AGENTS / "coach.md").read_text() + (AGENTS / "coach-wellbeing.md").read_text()
    assert "get_practices" in texts


def test_allow_practice_add_list_show() -> None:
    for command in ("add", "list", "show"):
        assert f"Bash(uv run coach practice {command}:*)" in allow()


def test_allow_has_no_practice_edit_delete_or_wildcard() -> None:
    rules = allow()
    assert not [r for r in rules if "practice edit" in r or "practice delete" in r]
    assert "Bash(uv run coach practice:*)" not in rules


def test_allow_habit_add_list_done_undo() -> None:
    for command in ("add", "list", "done", "undo"):
        assert f"Bash(uv run coach habit {command}:*)" in allow()


def test_allow_has_no_habit_wildcard() -> None:
    rules = allow()
    assert "Bash(uv run coach habit:*)" not in rules
    assert "Bash(uv run coach:*)" not in rules


def test_allow_has_no_habit_edit_or_delete() -> None:
    assert not [r for r in allow() if "habit edit" in r or "habit delete" in r]
