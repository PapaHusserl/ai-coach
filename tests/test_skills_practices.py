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


@pytest.mark.parametrize("name", sorted(AGENT_LIMITS))
def test_agent_file_keeps_reserve_below_limit(name: str) -> None:
    from text_limits import RESERVE

    size = len((AGENTS / name).read_bytes())
    assert AGENT_LIMITS[name] - size >= RESERVE, name


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


@pytest.mark.parametrize("path", agent_side_files(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_agent_side_file_keeps_reserve_below_limit(path: Path) -> None:
    from text_limits import RESERVE

    assert SIDE_FILE_LIMIT - len(path.read_bytes()) >= RESERVE, path.name


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


FOCUS_LINE = (
    "Дневная оценка: «фокус 4 2 3» (фокус, усталость, усилие, 1-5) - "
    "выполни `uv run coach focus 4 2 3`, больше ничего."
)
SLIP_LINE = (
    'Срыв: «срыв: <текст>» - выполни `uv run coach slip "<текст как есть>"`, '
    "не комментируй, не уточняй, окон не открывай."
)


def test_coach_names_report_add_in_bash_list() -> None:
    assert "`report add`" in (AGENTS / "coach.md").read_text()


def test_coach_reads_report_side_file() -> None:
    text = (AGENTS / "coach.md").read_text()
    assert "cat .claude/agents/coach/report.md" in text


def test_report_side_file_is_not_empty() -> None:
    assert (AGENTS / "coach" / "report.md").read_text().strip()


def test_report_side_file_within_limit() -> None:
    assert len((AGENTS / "coach" / "report.md").read_bytes()) <= SIDE_FILE_LIMIT


@pytest.mark.parametrize(
    "needle",
    ["uv run coach report add", "без чисел", "пульс", "HRV", "координат", "записал для техагента:"],
)
def test_report_side_file_has_needle(needle: str) -> None:
    assert needle in (AGENTS / "coach" / "report.md").read_text()


def test_records_file_has_focus_line_verbatim() -> None:
    assert FOCUS_LINE in (AGENTS / "coach" / "records.md").read_text().splitlines()


def test_records_file_has_slip_line_verbatim() -> None:
    assert SLIP_LINE in (AGENTS / "coach" / "records.md").read_text().splitlines()


def test_coach_no_longer_has_focus_line() -> None:
    assert FOCUS_LINE not in (AGENTS / "coach.md").read_text().splitlines()


def test_coach_no_longer_has_slip_line() -> None:
    assert SLIP_LINE not in (AGENTS / "coach.md").read_text().splitlines()


def test_coach_links_to_records_for_focus_and_slip() -> None:
    lines = (AGENTS / "coach.md").read_text().splitlines()
    linked = [ln for ln in lines if "coach/records.md" in ln and "фокус" in ln and "срыв" in ln]
    assert len(linked) == 1


def test_allow_has_report_command_and_side_file() -> None:
    rules = allow()
    assert "Bash(uv run coach report:*)" in rules
    assert "Bash(cat .claude/agents/coach/report.md)" in rules


def test_agents_md_local_rules_name_report_list_and_done() -> None:
    text = (ROOT / "AGENTS.md").read_text()
    assert "coach report list" in text
    assert "coach report done" in text
