"""Шаг Н29, партия 1: правило решений на будущее (coach-decisions.md), указатели, справка."""

import json
from pathlib import Path

import pytest
from text_limits import AGENT_LIMITS, EVENING_SKILL_LIMIT, HELP_TOPIC_LIMIT

CLAUDE = Path(__file__).resolve().parent.parent / ".claude"
AGENTS = CLAUDE / "agents"
RULE = AGENTS / "coach-decisions.md"
EVENING = CLAUDE / "skills" / "coach-evening" / "SKILL.md"
HELP_TOPIC = AGENTS / "coach-help" / "decisions.md"
ALLOW = json.loads((CLAUDE / "settings.json").read_text())["permissions"]["allow"]


def test_rule_file_exists_and_within_limit() -> None:
    assert RULE.is_file()
    assert 0 < len(RULE.read_bytes()) <= AGENT_LIMITS["coach-decisions.md"]


@pytest.mark.parametrize(
    "word",
    [
        "day_part",
        "утр",
        "вечер",
        "workload_ahead",
        "overloaded",
        "вернусь утром",
        "разложить завтра",
        "обзор недели",
    ],
)
def test_rule_names_key_words(word: str) -> None:
    assert word in RULE.read_text()


def test_coach_points_to_rule_as_9zh_after_9e() -> None:
    text = (AGENTS / "coach.md").read_text()
    assert "9ж" in text
    assert "coach-decisions.md" in text
    assert text.index("9е.") < text.index("9ж.")


def test_evening_skill_points_to_rule_and_within_limit() -> None:
    assert "coach-decisions.md" in EVENING.read_text()
    assert len(EVENING.read_bytes()) <= EVENING_SKILL_LIMIT


def test_allow_has_rule_file() -> None:
    assert "Bash(cat .claude/agents/coach-decisions.md)" in ALLOW


def test_help_topic_exists_within_limit() -> None:
    assert HELP_TOPIC.is_file()
    assert 0 < len(HELP_TOPIC.read_bytes()) <= HELP_TOPIC_LIMIT


def test_help_index_mentions_decisions_topic() -> None:
    assert "coach-help/decisions.md" in (AGENTS / "coach-help.md").read_text()


def test_allow_has_help_topic() -> None:
    assert "Bash(cat .claude/agents/coach-help/decisions.md)" in ALLOW


def test_help_topic_covers_exceptions() -> None:
    text = HELP_TOPIC.read_text()
    assert "разложить завтра" in text
    assert "обзор недели" in text


# партия 2: команды очереди


def test_decide_commands_are_allowed() -> None:
    assert "Bash(uv run coach decide:*)" in ALLOW


@pytest.mark.parametrize(
    "word", ["decide add", "decide list", "decide done", "decide result", "workout", "phase"]
)
def test_help_topic_covers_queue_commands_and_kinds(word: str) -> None:
    assert word in HELP_TOPIC.read_text()


def test_goals_help_says_phase_is_accepted_by_decide_done() -> None:
    assert "decide done" in (AGENTS / "coach-help" / "goals-profile.md").read_text()


def test_training_help_says_draft_goes_to_decision_queue() -> None:
    text = (AGENTS / "coach-help" / "training.md").read_text()
    assert "очеред" in text
    assert "decisions.md" in text
