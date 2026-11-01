"""Тексты шага Н13: роль coach-day.md, триггер 9д в coach.md, allow, вечерний вопрос, справка."""

import json
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE / ".claude"
AGENTS = ROOT / "agents"
ALLOW = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
DAY = AGENTS / "coach-day.md"
EVENING = ROOT / "skills" / "coach-evening" / "SKILL.md"


def coach_text() -> str:
    return (AGENTS / "coach.md").read_text()


def day_text() -> str:
    return DAY.read_text()


def test_day_file_exists_and_within_limit() -> None:
    assert 0 < len(DAY.read_bytes()) <= 6144


def test_coach_md_within_limit() -> None:
    assert len((AGENTS / "coach.md").read_bytes()) <= 16384


def test_day_file_is_allowed_by_cat() -> None:
    assert "Bash(cat .claude/agents/coach-day.md)" in ALLOW


def test_coach_md_reads_day_file_by_cat() -> None:
    assert "cat .claude/agents/coach-day.md" in coach_text()


def test_coach_md_mentions_day_plan() -> None:
    assert "план дня" in coach_text()


def test_coach_md_has_tool_in_header() -> None:
    assert "mcp__ai-coach__create_day_plan" in coach_text().split("---")[1]


def test_day_trigger_stands_between_9v_and_9g() -> None:
    text = coach_text()
    assert text.index("9в.") < text.index("9д.") < text.index("9г.")


@pytest.mark.parametrize(
    "word",
    [
        "create_day_plan",
        "uv run coach event write",
        "uv run coach event cancel",
        "uv run coach todo list",
        "uv run coach sync",
        "get_agenda",
        "skipped",
        "already_planned",
        "event remove",
        "«Да»",
        "AskUserQuestion",
        "без `event cancel`",
    ],
)
def test_day_file_has_word(word: str) -> None:
    assert word in day_text()


def test_day_file_has_no_mcp_prefix() -> None:
    assert "mcp__" not in day_text()


def test_evening_skill_offers_to_plan_tomorrow() -> None:
    assert "cat .claude/agents/coach-day.md" in EVENING.read_text()


def test_evening_skill_has_no_mcp_prefix_in_body() -> None:
    assert "mcp__" not in EVENING.read_text().split("---", 2)[2]


def test_evening_skill_within_limit() -> None:
    assert len(EVENING.read_bytes()) <= 4096


def test_todo_list_is_allowed() -> None:
    assert "Bash(uv run coach todo list:*)" in ALLOW


def test_todo_add_is_not_allowed() -> None:
    assert not [entry for entry in ALLOW if "coach todo" in entry and "list" not in entry]


def test_help_calendar_topic_has_day_plan() -> None:
    text = (AGENTS / "coach-help" / "calendar.md").read_text()
    assert "## План дня" in text
    assert "create_day_plan" in text


def test_help_toc_calendar_row_mentions_day_plan() -> None:
    rows = [r for r in (AGENTS / "coach-help.md").read_text().splitlines() if "calendar.md" in r]
    assert rows
    assert any("план дня" in row for row in rows)


def test_help_workload_topic_has_todo_list() -> None:
    assert "coach todo list" in (AGENTS / "coach-help" / "workload.md").read_text()


@pytest.mark.parametrize("word", ["create_day_plan", "coach todo list"])
def test_readme_mentions_day_plan(word: str) -> None:
    assert word in (BASE / "README.md").read_text()
