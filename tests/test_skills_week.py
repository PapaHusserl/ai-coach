"""Тексты шага v2.5: ядро coach.md и файлы coach-wellbeing/nutrition/week, allow для review done."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / ".claude"
AGENTS = ROOT / "agents"
ALLOW = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]


def coach_text() -> str:
    return (AGENTS / "coach.md").read_text()


def test_coach_week_is_not_empty() -> None:
    path = AGENTS / "coach-week.md"
    assert path.is_file()
    assert path.read_text().strip()


def test_coach_md_points_to_all_side_files() -> None:
    text = coach_text()
    for name in ["coach-wellbeing.md", "coach-nutrition.md", "coach-week.md"]:
        assert name in text


def test_every_cat_agent_file_in_coach_md_exists_and_is_allowed() -> None:
    named = set(re.findall(r"cat (\.claude/agents/[\w.-]+\.md)", coach_text()))
    assert named
    for path in named:
        assert (ROOT.parent / path).is_file(), path
        assert f"Bash(cat {path})" in ALLOW, path


def test_week_file_is_read_by_cat_from_coach_md() -> None:
    assert "cat .claude/agents/coach-week.md" in coach_text()
    assert "Bash(cat .claude/agents/coach-week.md)" in ALLOW


def test_coach_md_has_weekly_review_tool() -> None:
    head = coach_text().split("---")[1]
    assert "mcp__ai-coach__get_weekly_review" in head


def test_week_file_mentions_review_done_and_tool() -> None:
    text = (AGENTS / "coach-week.md").read_text()
    assert "get_weekly_review" in text
    assert "uv run coach review done" in text
    assert "week_review_due" in text


def test_review_done_is_allowed() -> None:
    assert "Bash(uv run coach review done:*)" in ALLOW


def test_coach_md_lists_review_in_bash_commands() -> None:
    assert "review" in coach_text()


# шаг Н29, партия 3: строка замера решений


def decisions_line() -> str:
    lines = (AGENTS / "coach-week.md").read_text().splitlines()
    found = [line for line in lines if "get_decisions" in line]
    assert found
    return found[0]


def test_week_file_has_decisions_line_with_stats_words() -> None:
    text = (AGENTS / "coach-week.md").read_text()
    for word in ["get_decisions", "kept", "missed", "данных мало"]:
        assert word in text


def test_week_decisions_line_names_threshold_ten() -> None:
    assert re.search(r"\b10\b", decisions_line())
