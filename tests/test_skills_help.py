"""Справка тренера (шаг Н14): оглавление, файлы тем, allow, триггер, содержимое тем."""

import json
import re
from pathlib import Path

from ai_coach.load import deviations, overload, training

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / ".claude"
AGENTS = CLAUDE / "agents"
HELP = AGENTS / "coach-help.md"
TOPICS = AGENTS / "coach-help"
INDEX_LIMIT = 6144
TOPIC_LIMIT = 8192


def topic_files() -> list[Path]:
    return sorted(TOPICS.glob("*.md"))


def topic(name: str) -> str:
    return (TOPICS / name).read_text()


def allow() -> list[str]:
    return json.loads((CLAUDE / "settings.json").read_text())["permissions"]["allow"]


def test_index_within_limit() -> None:
    assert len(HELP.read_bytes()) <= INDEX_LIMIT


def test_topic_files_exist() -> None:
    assert topic_files()


def test_topic_files_within_limit_and_not_empty() -> None:
    for path in topic_files():
        size = len(path.read_bytes())
        assert 0 < size <= TOPIC_LIMIT, path.name


def test_index_mentions_every_topic_file() -> None:
    text = HELP.read_text()
    assert [p.name for p in topic_files() if p.name not in text] == []


def test_index_mentions_no_missing_topic_file() -> None:
    mentioned = set(re.findall(r"coach-help/([\w.-]+\.md)", HELP.read_text()))
    assert mentioned <= {p.name for p in topic_files()}


def test_allow_has_index() -> None:
    assert "Bash(cat .claude/agents/coach-help.md)" in allow()


def test_allow_has_every_topic_file() -> None:
    rules = allow()
    missing = [
        p.name
        for p in topic_files()
        if f"Bash(cat .claude/agents/coach-help/{p.name})" not in rules
    ]
    assert missing == []


def test_coach_points_to_help_with_triggers() -> None:
    text = (AGENTS / "coach.md").read_text()
    assert "coach-help.md" in text
    for trigger in ("справка", "что значит", "что умеешь"):
        assert trigger in text, trigger


def test_wellbeing_topic_has_commands_and_flags() -> None:
    text = topic("wellbeing.md")
    for needle in (
        "coach focus",
        "coach log focus",
        "coach feel",
        "--mood",
        "--stress",
        "--thoughts",
        "--flow",
        "--hindrance",
        "--valuable",
        "get_focus_log",
        "get_wellbeing",
        "04:00",
    ):
        assert needle in text, needle


def test_wellbeing_topic_has_scale_poles() -> None:
    text = topic("wellbeing.md").lower()
    for pole in (
        "рассеян",
        "собран",
        "свеж",
        "выжат",
        "легко",
        "через силу",
        "плохо",
        "отлично",
        "сильный",
        "не думал",
        "всё время",
        "почти не было",
        "весь день",
        "почти ничего",
        "всё ценное",
    ):
        assert pole in text, pole


def test_wellbeing_topic_deviation_thresholds_match_deviations() -> None:
    text = topic("wellbeing.md")
    for needle in (
        f"самочувствие {deviations.WELLBEING_MAX} и ниже",
        f"настроение {deviations.MOOD_MAX} и ниже",
        f"стресс {deviations.STRESS_MIN} и выше",
        f"readiness ниже {deviations.READINESS_MIN}",
        *(f"{status}" for status in deviations.BAD_HRV_STATUSES),
        f"ATL минус CTL больше {deviations.ATL_OVER_CTL_MAX}",
        f"сон меньше {deviations.SLEEP_MIN_HOURS} часов",
    ):
        assert needle in text, needle


def test_training_topic_load_numbers_match_training() -> None:
    text = topic("training.md")
    for needle in (
        f"примерно {training.CTL_DAYS} дня",
        f"примерно {training.ATL_DAYS} дней",
        f"Силовая - {training.STRENGTH_TSS_PER_HOUR} в час",
        f"больше {deviations.ATL_OVER_CTL_MAX}",
    ):
        assert needle in text, needle


def test_start_topic() -> None:
    text = topic("start.md")
    for needle in ("тренер", "тренер вечер", "coach sync", "coach login"):
        assert needle in text, needle


def test_training_topic() -> None:
    text = topic("training.md")
    for needle in ("coach approve", "coach push", "coach link", "CTL", "ATL"):
        assert needle in text, needle


def test_workload_topic() -> None:
    text = topic("workload.md")
    for needle in (
        "coach screen",
        "coach review done",
        "workload.toml",
        "total_streak",
        "evening_streak",
        "weekend_work",
        "recovery_drop",
        "todo_growth",
    ):
        assert needle in text, needle


def num(value: float) -> str:
    """Число как в русском тексте: 0.05 -> «0,05», 10.0 -> «10»."""
    return f"{value:g}".replace(".", ",")


def test_workload_topic_total_formula_matches_overload_weights() -> None:
    text = topic("workload.md")
    for needle in (
        f"TSS × {num(overload.W_TSS)}",
        f"часы хобби × {num(overload.W_HOBBY)}",
        f"после 19:00 × {num(overload.W_EVENING)}",
        f"работа × {num(overload.W_WEEKEND)}",
        f"туду × {num(overload.W_TODO)}",
        f"груминг × {num(overload.W_GROOMING)}",
    ):
        assert needle in text, needle
    assert overload.W_WORK == 1.0  # «часы работы» без множителя


def test_workload_topic_signal_thresholds_match_overload() -> None:
    text = topic("workload.md")
    days = {3: "три"}
    for needle in (
        f"не меньше {num(overload.TOTAL_HIGH)} {days[overload.TOTAL_STREAK_DAYS]} дня подряд",
        f"{days[overload.EVENING_STREAK_DAYS]} вечера подряд",
        f"за {overload.RECOVERY_RECENT_DAYS} последних дня",
        f"за {overload.RECOVERY_BASELINE_DAYS} предыдущих",
        f"ниже на {overload.READINESS_DROP} и больше",
        f"настроение ниже на {num(overload.MOOD_DROP)}",
        f"стресс выше на {num(overload.STRESS_RISE)}",
        f"больше на {overload.TODO_GROWTH_MIN} и более",
        f"за последние {overload.OVERLOAD_DAYS} дней",
        "не меньше часа",
    ):
        assert needle in text, needle
    assert overload.WEEKEND_WORK_MIN == 1.0  # «не меньше часа»


def test_agenda_note_has_focus_title_and_poles() -> None:
    path = AGENTS / "coach-agenda.md"
    text = path.read_text()
    assert "Фокус 1–5?" in text
    for pole in ("рассеян", "собран", "свеж", "выжат", "легко", "через силу"):
        assert pole in text, pole
    assert len(path.read_bytes()) <= 6144
