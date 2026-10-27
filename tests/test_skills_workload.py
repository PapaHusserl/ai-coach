import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / ".claude"
WELLBEING = ROOT / "agents" / "coach-wellbeing.md"


def test_coach_wellbeing_exists_and_is_short() -> None:
    assert WELLBEING.is_file()
    assert len(WELLBEING.read_bytes()) <= 7168


def test_coach_wellbeing_mentions_workload_tool() -> None:
    assert "get_workload" in WELLBEING.read_text()


def test_coach_wellbeing_describes_all_screen_fields() -> None:
    text = WELLBEING.read_text()
    for field in (
        "screen_work_hours",
        "screen_hobby_hours",
        "screen_browser_hours",
        "screen_evening_hours",
    ):
        assert field in text


def test_coach_wellbeing_gives_hours_priority_manual_screen_calendar() -> None:
    text = WELLBEING.read_text()
    assert "ручные (вечерний чек-ин) > экран > календарь" in text


def test_coach_wellbeing_explains_screen_lines_of_sync_summary() -> None:
    text = WELLBEING.read_text()
    assert "экран не настроен" in text
    assert "экран: …" in text
    assert "ActivityWatch" in text


def test_coach_wellbeing_says_null_screen_means_no_data() -> None:
    assert "null - нет данных" in WELLBEING.read_text()


def test_readme_documents_screen_time() -> None:
    text = (ROOT.parent / "README.md").read_text()
    for word in (
        "ActivityWatch",
        "coach screen",
        "[screen]",
        "screen_work_hours",
        "ручные (`coach feel --work/--hobby`) > экран > календарь",
        "Приватность",
    ):
        assert word in text


def test_architecture_documents_screen_step() -> None:
    text = (ROOT.parent / "docs" / "architecture.md").read_text()
    assert "## v2: экранное время (шаг v2.8)" in text
    section = text.split("## v2: экранное время (шаг v2.8)")[1]
    assert "manual if manual is not None else (screen if screen is not None else" in section
    for word in (
        "screen_evening_hours",
        "COUNTER_KINDS",
        "coach screen",
        "AHEAD_SKIP",
        "read_screen",
    ):
        assert word in section


def test_coach_allows_reading_wellbeing_file() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert "Bash(cat .claude/agents/coach-wellbeing.md)" in allow


def test_coach_mentions_workload_tool_and_wellbeing_file() -> None:
    coach = (ROOT / "agents" / "coach.md").read_text()
    assert "get_workload" in coach
    assert "coach-wellbeing.md" in coach


def test_coach_is_still_within_limit() -> None:
    assert len((ROOT / "agents" / "coach.md").read_bytes()) <= 15360
