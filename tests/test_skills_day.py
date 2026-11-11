"""Тексты шага Н13: роль coach-day.md, триггер 9д в coach.md, allow, вечерний вопрос, справка."""

import json
from pathlib import Path

import pytest
from text_limits import AGENT_LIMITS, EVENING_SKILL_LIMIT

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
    assert 0 < len(DAY.read_bytes()) <= AGENT_LIMITS["coach-day.md"]


def test_day_file_mentions_illness_risk() -> None:
    assert "illness_risk" in day_text()


def test_coach_md_within_limit() -> None:
    assert len((AGENTS / "coach.md").read_bytes()) <= AGENT_LIMITS["coach.md"]


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
    assert len(EVENING.read_bytes()) <= EVENING_SKILL_LIMIT


def test_todo_commands_are_allowed() -> None:
    assert "Bash(uv run coach todo:*)" in ALLOW


def test_todo_has_no_narrower_allow_entries() -> None:
    assert [entry for entry in ALLOW if "coach todo" in entry] == ["Bash(uv run coach todo:*)"]


def test_help_day_plan_topic_has_day_plan() -> None:
    text = (AGENTS / "coach-help" / "day-plan.md").read_text()
    assert "## План дня" in text
    assert "create_day_plan" in text


def test_help_toc_day_plan_row() -> None:
    rows = [r for r in (AGENTS / "coach-help.md").read_text().splitlines() if "day-plan.md" in r]
    assert rows
    assert any("спланируй день" in row for row in rows)


def test_help_todo_topic_has_commands() -> None:
    text = (AGENTS / "coach-help" / "todo.md").read_text()
    for command in ["list", "add", "start", "done", "drop", "reopen", "edit"]:
        assert f"coach todo {command}" in text


def test_help_workload_topic_points_to_todo_topic() -> None:
    assert "coach-help/todo.md" in (AGENTS / "coach-help" / "workload.md").read_text()


def test_day_step_five_asks_by_text_not_window() -> None:
    step = next(line for line in day_text().splitlines() if line.startswith("5. "))
    assert "Спроси текстом" in step
    assert "Спроси окном" not in day_text()
    step_two = next(line for line in day_text().splitlines() if line.startswith("2. Задачи"))
    assert "AskUserQuestion" in step_two


def test_recalc_yes_no_is_text_with_substance() -> None:
    text = (ROOT / "skills" / "coach-plan" / "recalc.md").read_text()
    assert "текстом - с сутью изменений" in text
    assert "Окно «да/нет»" not in text


def test_help_day_plan_says_one_window() -> None:
    assert "одним окном" in (AGENTS / "coach-help" / "day-plan.md").read_text()


def test_day_file_offers_cancelling_cooking_block_by_event_cancel() -> None:
    text = day_text()
    assert "готовк" in text
    assert "`uv run coach event cancel <id>` блоков «Готовка»" in text


def test_day_file_puts_meals_before_tasks() -> None:
    text = day_text()
    assert "готовка и завтрак, перекус, отдых после перекуса, готовка и ужин, задачи, фокус" in text


def test_day_step_two_asks_morning_routine() -> None:
    step = next(line for line in day_text().splitlines() if line.startswith("2. Задачи"))
    assert "распорядок утра" in step
    assert "`day_start`" in step
    assert "`breakfast_at`" in step


def test_recalc_window_shows_substance_of_changes() -> None:
    text = (ROOT / "skills" / "coach-plan" / "recalc.md").read_text()
    assert "с сутью изменений" in text


def test_meal_skill_reads_pantry_first_and_avoids_recent_food() -> None:
    text = (ROOT / "skills" / "coach-meal" / "SKILL.md").read_text()
    step = next(line for line in text.splitlines() if line.startswith("1. "))
    assert "Сначала `get_pantry`" in step
    assert "1-2 дня" in step
    assert "не повторяй" in step


def test_day_file_puts_late_tasks_after_dinner_and_evening_not_free() -> None:
    text = day_text()
    assert "не влезшие до ужина задачи - после ужина" in text
    assert "вечер после ужина свободен" not in text.lower()


def test_day_file_asks_confirmation_with_plan_summary() -> None:
    assert "краткий план" in day_text()


def test_coach_runs_push_and_cancel_with_yes_after_user_yes() -> None:
    assert "coach push <id> --yes` / `uv run coach cancel <id> --yes`" in coach_text()


def test_help_training_topic_mentions_yes_flag() -> None:
    text = (AGENTS / "coach-help" / "training.md").read_text()
    assert "coach push <id> --yes" in text
    assert "--yes" in text.split("Отменить")[1]


def test_help_calendar_topic_mentions_cooking() -> None:
    assert "готовк" in (AGENTS / "coach-help" / "day-plan.md").read_text()


def test_readme_mentions_cooking() -> None:
    assert "готовк" in (BASE / "README.md").read_text()


@pytest.mark.parametrize("word", ["create_day_plan", "coach todo list"])
def test_readme_mentions_day_plan(word: str) -> None:
    assert word in (BASE / "README.md").read_text()
