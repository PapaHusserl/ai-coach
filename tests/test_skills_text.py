import json
from pathlib import Path

import pytest

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
    text = (ROOT / "agents" / "coach.md").read_text()
    assert "uv run coach supplement add" in text
    assert "uv run coach protocol add" in text
    assert "не медицинский совет" in text.lower()
    assert "кофеин" in text.lower()
