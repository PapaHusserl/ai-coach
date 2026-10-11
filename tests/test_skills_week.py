"""Тексты шага v2.5: ядро coach.md и файлы coach-wellbeing/nutrition/week, allow для review done."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / ".claude"
AGENTS = ROOT / "agents"
ALLOW = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]


def coach_text() -> str:
    return (AGENTS / "coach.md").read_text()


def test_coach_md_within_limit() -> None:
    assert len((AGENTS / "coach.md").read_bytes()) <= 15360


def test_coach_week_exists_and_within_limit() -> None:
    path = AGENTS / "coach-week.md"
    assert path.is_file()
    assert 0 < len(path.read_bytes()) <= 6144


def test_coach_week_is_not_empty() -> None:
    assert (AGENTS / "coach-week.md").read_text().strip()


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
