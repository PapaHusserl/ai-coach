import json
import re
import sqlite3
from pathlib import Path

import pytest
from mcp_fakes import tool_names

ROOT = Path(__file__).resolve().parent.parent / ".claude"
SKILLS = ROOT / "skills"
MAX_BYTES = 3072
ALLOW = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]


def skill_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def extra_files(skill: str) -> list[Path]:
    return sorted(p for p in (SKILLS / skill).iterdir() if p.is_file() and p.name != "SKILL.md")


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_skill_is_at_most_3072_bytes(path: Path) -> None:
    assert len(path.read_bytes()) <= MAX_BYTES


def test_skills_are_found() -> None:
    assert len(skill_files()) >= 4


# --- coach-morning: ядро + файлы-опции ---


def test_morning_has_at_least_three_option_files() -> None:
    assert len([p for p in extra_files("coach-morning") if p.suffix == ".md"]) >= 3


def test_morning_skill_references_every_option_file() -> None:
    text = (SKILLS / "coach-morning" / "SKILL.md").read_text()
    for path in extra_files("coach-morning"):
        assert path.name in text


def test_morning_option_files_are_not_empty() -> None:
    for path in extra_files("coach-morning"):
        assert path.read_text().strip()


def test_morning_has_sport_nutrition_option_with_mcp_tool() -> None:
    texts = [p.read_text() for p in extra_files("coach-morning")]
    assert any("get_sport_nutrition_for" in t for t in texts)


def test_morning_option_files_can_be_read_without_prompt() -> None:
    for path in extra_files("coach-morning"):
        assert f"Bash(cat .claude/skills/coach-morning/{path.name})" in ALLOW


def test_morning_core_depends_on_time_of_day() -> None:
    text = (SKILLS / "coach-morning" / "SKILL.md").read_text().lower()
    assert "утр" in text
    assert "днём" in text or "днем" in text or "вечер" in text


# --- coach-meal: питание к тренировке отдельным файлом ---


def test_meal_has_separate_training_nutrition_file() -> None:
    files = [p for p in extra_files("coach-meal") if p.suffix == ".md"]
    assert len(files) >= 1
    assert any("get_sport_nutrition_for" in p.read_text() for p in files)


def test_meal_skill_references_its_extra_files() -> None:
    text = (SKILLS / "coach-meal" / "SKILL.md").read_text()
    for path in extra_files("coach-meal"):
        assert path.name in text


def test_meal_extra_files_can_be_read_without_prompt() -> None:
    for path in extra_files("coach-meal"):
        assert f"Bash(cat .claude/skills/coach-meal/{path.name})" in ALLOW


def test_meal_skill_has_sport_nutrition_tool_in_allowed_tools() -> None:
    head = (SKILLS / "coach-meal" / "SKILL.md").read_text().split("---")[1]
    assert "mcp__ai-coach__get_sport_nutrition_for" in head


def test_meal_skill_keeps_other_allowed_tools() -> None:
    head = (SKILLS / "coach-meal" / "SKILL.md").read_text().split("---")[1]
    for tool in ["get_profile", "get_pantry", "get_plan", "get_recipes"]:
        assert f"mcp__ai-coach__{tool}" in head


# --- agent coach.md ---


def test_agent_describes_supplements_with_limits() -> None:
    text = agent_text()
    assert "uv run coach supplement add" in text
    assert "uv run coach protocol add" in text
    assert "не медицинский совет" in text.lower()
    assert "кофеин" in text.lower()


# --- шаг 18: курсы витаминов и средств ---


def coach_only_text() -> str:
    return (ROOT / "agents" / "coach.md").read_text()


def agent_text() -> str:
    return coach_only_text() + "\n" + (ROOT / "agents" / "coach-nutrition.md").read_text()


def agent_tools() -> str:
    return agent_text().split("---")[1]


def test_morning_core_mentions_meds_today() -> None:
    text = (SKILLS / "coach-morning" / "SKILL.md").read_text()
    assert "meds_today" in text


def test_agent_has_get_meds_in_tools() -> None:
    assert "mcp__ai-coach__get_meds" in agent_tools()


def test_agent_keeps_sport_nutrition_tools() -> None:
    for tool in ["get_sport_nutrition", "get_sport_nutrition_for", "cancel_draft_workout"]:
        assert f"mcp__ai-coach__{tool}" in agent_tools()


def test_agent_allows_med_in_bash_list() -> None:
    assert "`med`" in agent_text()


def test_agent_describes_med_add_after_yes() -> None:
    text = agent_text()
    assert "uv run coach med add" in text
    assert "--kind" in text
    assert "после «да»" in text


def test_agent_advises_only_otc_and_sends_prescription_to_doctor() -> None:
    text = agent_text().lower()
    assert "безрецептурн" in text
    assert "рецептурное" in text
    assert "к врачу" in text
    assert "инструкц" in text


def test_agent_lists_all_red_flags() -> None:
    text = agent_text().lower()
    for flag in ["боль в груди", "обморок", "пульса в покое", "травма", "температур"]:
        assert flag in text


def test_agent_red_flag_cancels_workout_and_records_feel() -> None:
    text = agent_text()
    assert "cancel_draft_workout" in text
    assert "на часах" in text
    assert "uv run coach feel" in text


def test_agent_keeps_vitamins_in_med_not_supplement() -> None:
    text = agent_text().lower()
    assert "`med`" in text
    assert "`supplement`" in text
    assert "спортпит" in text


def test_agent_does_not_give_med_edit_delete_to_itself() -> None:
    text = agent_text()
    assert "med edit" in text
    assert "пользователь сам" in text


def test_agent_keeps_step_17_texts() -> None:
    text = agent_text()
    assert "uv run coach supplement add" in text
    assert "кофеин" in text.lower()


# --- шаг 19в: журнал приёма ---


def morning_text() -> str:
    parts = [(SKILLS / "coach-morning" / "SKILL.md").read_text()]
    parts += [p.read_text() for p in extra_files("coach-morning")]
    return "\n".join(parts)


def test_morning_describes_taken_and_evening_reminder() -> None:
    text = morning_text()
    assert "taken" in text
    assert "непринят" in text.lower() or "не принят" in text.lower()
    assert "вечер" in text.lower()


def test_morning_training_nutrition_offers_to_mark_after_intake() -> None:
    text = (SKILLS / "coach-morning" / "training-nutrition.md").read_text()
    assert "uv run coach supplement take" in text
    assert "after" in text


def test_agent_has_get_supplement_log_in_tools() -> None:
    assert "mcp__ai-coach__get_supplement_log" in agent_tools()


def test_agent_describes_supplement_take_after_yes() -> None:
    text = agent_text()
    assert "uv run coach supplement take" in text
    assert "get_supplement_log" in text
    assert "после «да»" in text


def test_agent_keeps_step_18_tools() -> None:
    for tool in ["get_meds", "get_sport_nutrition_for", "cancel_draft_workout"]:
        assert f"mcp__ai-coach__{tool}" in agent_tools()


# --- шаг 19в, решения пользователя ---


@pytest.mark.parametrize("path", skill_files(), ids=lambda p: p.parent.name)
def test_skill_tools_mentioned_in_files_are_in_allowed_tools(
    path: Path, conn: sqlite3.Connection
) -> None:
    head = path.read_text().split("---")[1]
    allowed = set(re.findall(r"mcp__ai-coach__(\w+)", head))
    texts = [p.read_text() for p in path.parent.iterdir() if p.suffix == ".md"]
    mentioned = {n for n in tool_names(conn) if any(re.search(rf"\b{n}\b", t) for t in texts)}
    assert mentioned - allowed == set()


def test_morning_has_get_supplement_log_in_allowed_tools() -> None:
    head = (SKILLS / "coach-morning" / "SKILL.md").read_text().split("---")[1]
    assert "mcp__ai-coach__get_supplement_log" in head


def test_meal_training_nutrition_mentions_taken() -> None:
    text = (SKILLS / "coach-meal" / "training-nutrition.md").read_text()
    assert "taken" in text


def test_meal_training_nutrition_has_no_mark_after_rule() -> None:
    text = (SKILLS / "coach-meal" / "training-nutrition.md").read_text()
    assert "supplement take" not in text


# --- шаг 20: проактивность тренера ---

COACH_MAX_BYTES = 15360


def test_coach_is_at_most_15360_bytes() -> None:
    assert len((ROOT / "agents" / "coach.md").read_bytes()) <= COACH_MAX_BYTES


def test_coach_nutrition_can_be_read_without_prompt() -> None:
    assert "Bash(cat .claude/agents/coach-nutrition.md)" in ALLOW


def test_coach_references_nutrition_file() -> None:
    assert "coach-nutrition.md" in coach_only_text()


def test_coach_summary_mentions_meds_today_and_sport_nutrition_today() -> None:
    text = coach_only_text()
    assert "meds_today" in text
    assert "sport_nutrition_today" in text


def test_coach_summary_calls_unaccepted_supplements() -> None:
    text = coach_only_text()
    assert "sport_nutrition_today" in text
    assert "(принято)" in text


def test_coach_uses_catalog_triggers() -> None:
    text = coach_only_text()
    assert "catalog" in text
    assert "catalog.protocols" in text
    assert "catalog.meds" in text


def test_coach_offers_training_nutrition_without_request() -> None:
    text = coach_only_text()
    assert "sport_nutrition_today.workouts" in text
    assert "оценк" in text.lower()


def test_coach_has_what_i_can_line() -> None:
    assert "что умею" in coach_only_text()


def test_coach_has_red_flags_and_doctor_itself() -> None:
    text = coach_only_text().lower()
    assert "красные флаги" in text
    assert "к врачу" in text


def test_coach_does_not_store_supplements_intake() -> None:
    assert "supplements_intake" not in agent_text()
    assert "supplements_intake" not in (ROOT / "agents" / "coach-onboarding.md").read_text()


def test_coach_asks_what_he_takes_on_first_run_of_the_day() -> None:
    text = coach_only_text()
    assert "catalog.meds" in text
    assert "meal_plan_today" in text
    assert "med add" in text


def test_onboarding_asks_about_vitamins_and_offers_courses_after_yes() -> None:
    text = (ROOT / "agents" / "coach-onboarding.md").read_text()
    assert "витамин" in text.lower()
    assert "med add" in text
    assert "supplement add" in text


def test_coach_keeps_red_flags_commands() -> None:
    text = coach_only_text()
    assert "cancel_draft_workout" in text
    assert "uv run coach feel" in text


def test_server_describes_catalog_in_snapshot() -> None:
    text = (ROOT.parent / "src" / "ai_coach" / "mcp_server" / "server.py").read_text()
    assert "catalog (" in text
