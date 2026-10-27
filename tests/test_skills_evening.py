import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
EVENING = CLAUDE / "skills" / "coach-evening" / "SKILL.md"


def allow() -> list[str]:
    return json.loads((CLAUDE / "settings.json").read_text())["permissions"]["allow"]


def test_evening_skill_exists_and_is_short() -> None:
    assert EVENING.is_file()
    assert len(EVENING.read_bytes()) <= 3072


def test_evening_skill_has_front_matter() -> None:
    head = EVENING.read_text().split("---")[1]
    assert "name: coach-evening" in head
    assert "description:" in head


def test_evening_skill_uses_feel_with_all_options() -> None:
    text = EVENING.read_text()
    for option in ("--mood", "--stress", "--work", "--hobby", "--rest"):
        assert option in text


def test_evening_skill_reads_snapshot_and_checks_evening_done() -> None:
    text = EVENING.read_text()
    assert "get_morning_snapshot" in text
    assert "evening_done_today" in text


def test_evening_skill_tools_are_in_allowed_tools() -> None:
    head = EVENING.read_text().split("---")[1]
    assert "mcp__ai-coach__get_morning_snapshot" in head


def test_evening_skill_runs_coach_screen_before_the_snapshot() -> None:
    body = EVENING.read_text().split("---", 2)[2]
    assert "uv run coach screen" in body
    assert body.index("uv run coach screen") < body.index("get_morning_snapshot")


def test_evening_skill_continues_when_screen_is_unavailable() -> None:
    line = next(x for x in EVENING.read_text().splitlines() if "uv run coach screen" in x)
    assert "не настроен" in line
    assert "не ответил" in line
    assert "дальше" in line


def test_evening_skill_offers_screen_hours_and_writes_them_with_feel() -> None:
    text = EVENING.read_text()
    assert "screen_work_hours" in text
    assert "экран:" in text
    assert "записать так" in text
    assert "--work N --hobby M" in text


def test_evening_skill_still_asks_hours_without_screen() -> None:
    assert "нет - спроси сам" in EVENING.read_text()


def test_evening_skill_has_no_application_or_window_names() -> None:
    text = EVENING.read_text().lower()
    for word in ("заголовок", "window title", "obsidian"):
        assert word not in text


def test_feel_command_is_allowed() -> None:
    assert "Bash(uv run coach feel:*)" in allow()


def test_screen_command_is_allowed() -> None:
    assert "Bash(uv run coach screen:*)" in allow()


def test_trener_launcher_takes_evening_argument() -> None:
    text = (ROOT / "bin" / "trener").read_text()
    assert "вечер" in text


def test_trener_launcher_sets_own_output_style() -> None:
    text = (ROOT / "bin" / "trener").read_text()
    style = (CLAUDE / "output-styles" / "trener.md").read_text()
    assert '"outputStyle": "Тренер"' in text
    assert text.count('--settings "$STYLE"') == 2
    assert "name: Тренер" in style.split("---")[1]


def test_coach_asks_questions_interactively() -> None:
    coach = (CLAUDE / "agents" / "coach.md").read_text()
    assert "AskUserQuestion" in coach.split("---")[1]
    assert "AskUserQuestion" in coach.split("---", 2)[2]


def test_coach_knows_the_evening_skill_and_overload_tool() -> None:
    coach = (CLAUDE / "agents" / "coach.md").read_text()
    assert "coach-evening" in coach
    assert "get_overload" in coach or "overload" in coach


def test_wellbeing_file_describes_overload_reaction() -> None:
    text = (CLAUDE / "agents" / "coach-wellbeing.md").read_text()
    assert "overload" in text
    assert "overloaded" in text


def test_coach_stays_within_limit_after_v23() -> None:
    assert len((CLAUDE / "agents" / "coach.md").read_bytes()) <= 15360
