"""Тексты и лимиты шага v2.4: размеры промптов, allow для practice/habit, подсказки агенту."""

import json
import re
from pathlib import Path

import pytest
from text_limits import AGENT_LIMITS, SIDE_FILE_LIMIT

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
AGENTS = CLAUDE / "agents"
EVENING = CLAUDE / "skills" / "coach-evening" / "SKILL.md"


def allow() -> list[str]:
    return json.loads((CLAUDE / "settings.json").read_text())["permissions"]["allow"]


def test_agent_files_within_their_limits() -> None:
    for name, limit in AGENT_LIMITS.items():
        assert len((AGENTS / name).read_bytes()) <= limit, name


def test_every_agent_file_has_a_limit() -> None:
    assert {p.name for p in AGENTS.glob("*.md")} <= set(AGENT_LIMITS)


def agent_side_files() -> list[Path]:
    return sorted(
        (p for p in AGENTS.glob("*/*.md") if p.parent.name != "coach-help"),
        key=lambda p: (p.parent.name, p.name),
    )


@pytest.mark.parametrize("path", agent_side_files(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_agent_side_file_is_within_its_limit(path: Path) -> None:
    assert len(path.read_bytes()) <= SIDE_FILE_LIMIT


def test_agent_side_files_are_found() -> None:
    assert len(agent_side_files()) >= 2


# Лимит файла проверяет один общий тест.
LIMIT_TESTS = {
    "test_skills_practices.py",
    "test_skills_text.py",
    "test_skills_help.py",
}


def test_text_limits_imported_only_by_shared_limit_tests() -> None:
    importers = {
        path.name
        for path in Path(__file__).parent.glob("*.py")
        if re.search(r"^\s*(from text_limits import|import text_limits)", path.read_text(), re.M)
    }
    assert importers <= LIMIT_TESTS


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
