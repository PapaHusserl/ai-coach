"""Тексты шага 24: coach-food/groups.md, coach-nutrition/variety.md, 8в, coach-week, allow."""

import json
from pathlib import Path

from ai_coach.nutrition.groups import FOOD_GROUPS

CLAUDE = Path(__file__).resolve().parent.parent / ".claude"
AGENTS = CLAUDE / "agents"
FOOD = CLAUDE / "skills" / "coach-food"
ALLOW = json.loads((CLAUDE / "settings.json").read_text())["permissions"]["allow"]


def test_food_skill_within_limit() -> None:
    assert len((FOOD / "SKILL.md").read_bytes()) <= 3072


def test_food_skill_references_groups_file() -> None:
    assert "groups.md" in (FOOD / "SKILL.md").read_text()


def test_groups_file_lists_every_food_group_key() -> None:
    text = (FOOD / "groups.md").read_text()
    assert [key for key in FOOD_GROUPS if f"`{key}`" not in text] == []


def test_groups_file_has_no_organ_meat_key() -> None:
    assert "`organ_meat`" not in (FOOD / "groups.md").read_text()


def test_groups_file_mentions_save_tool_param() -> None:
    assert "groups" in (FOOD / "groups.md").read_text()


def test_nutrition_within_limit() -> None:
    assert len((AGENTS / "coach-nutrition.md").read_bytes()) <= 6144


def test_nutrition_mentions_variety_tool_and_file() -> None:
    text = (AGENTS / "coach-nutrition.md").read_text()
    assert "get_food_variety" in text
    assert "coach-nutrition/variety.md" in text


def test_variety_file_exists_and_names_tools() -> None:
    text = (AGENTS / "coach-nutrition" / "variety.md").read_text()
    for word in ("get_food_variety", "get_nutrient_norms", "supplement_max", "get_meds"):
        assert word in text


def test_variety_file_mentions_upper_limit() -> None:
    text = (AGENTS / "coach-nutrition" / "variety.md").read_text()
    assert "ВДУП" in text or "верхн" in text


def test_allow_can_read_variety_file() -> None:
    assert "Bash(cat .claude/agents/coach-nutrition/variety.md)" in ALLOW


def test_allow_can_read_groups_file() -> None:
    assert "Bash(cat .claude/skills/coach-food/groups.md)" in ALLOW


def test_coach_week_mentions_food_variety() -> None:
    assert "get_food_variety" in (AGENTS / "coach-week.md").read_text()


def test_coach_agent_has_new_tools() -> None:
    head = (AGENTS / "coach.md").read_text().split("---")[1]
    for tool in ("get_food_variety", "get_nutrient_norms"):
        assert f"mcp__ai-coach__{tool}" in head


def test_coach_agent_has_regroup_tools() -> None:
    head = (AGENTS / "coach.md").read_text().split("---")[1]
    for tool in ("get_food_without_groups", "save_food_groups"):
        assert f"mcp__ai-coach__{tool}" in head


def test_food_skill_allows_regroup_tools() -> None:
    head = (FOOD / "SKILL.md").read_text().split("---")[1]
    for tool in ("get_food_without_groups", "save_food_groups"):
        assert f"mcp__ai-coach__{tool}" in head


def test_groups_file_describes_regroup_tools_and_empty_list() -> None:
    text = (FOOD / "groups.md").read_text()
    assert "get_food_without_groups" in text
    assert "save_food_groups" in text
    assert "`[]`" in text


def test_save_nutrition_description_says_groups_required() -> None:
    from ai_coach.mcp_server.server import TOOLS

    assert "обязател" in TOOLS["save_food_nutrition"][1]
