"""Справка тренера (шаг Н14): оглавление, файлы тем, allow, триггер, содержимое тем."""

import json
import re
import sqlite3
from pathlib import Path

import typer
from mcp_fakes import tool_names

from ai_coach import pvt
from ai_coach.cli import main
from ai_coach.load import deviations, illness, overload, sleep, training, who5
from ai_coach.workload.claude import CLAUDE_COUNTERS
from ai_coach.workload.config import DEMANDS

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


def test_pvt_topic_has_commands_and_flags() -> None:
    text = topic("pvt.md")
    for needle in ("coach pvt", "coach log pvt", "get_pvt_log", "04:00", "Esc"):
        assert needle in text, needle


def test_pvt_topic_thresholds_match_constants() -> None:
    text = topic("pvt.md")
    for needle in (
        f"{pvt.DURATION_S // 60} минуты",
        f"{pvt.ISI_MIN_MS // 1000}-{pvt.ISI_MAX_MS // 1000} с",
        f"дольше {pvt.LAPSE_MS} мс",
        f"быстрее {pvt.FALSE_START_MS} мс",
        f"нет ответа {pvt.NO_RESPONSE_MS // 1000} с",
        f"{round(pvt.SLOW_SHARE * 100)} %",
    ):
        assert needle in text, needle


def test_sleep_topic_has_fields() -> None:
    text = topic("sleep.md")
    for needle in (
        "get_sleep",
        "debt_7_h",
        "debt_14_h",
        "awake_h",
        "caution_from",
        "short_night",
        "nap_h",
    ):
        assert needle in text, needle


def test_sleep_topic_thresholds_match_constants() -> None:
    text = topic("sleep.md")
    for needle in (
        f"{sleep.NORM_DAYS} дней",
        f"{sleep.NORM_MIN_NIGHTS} ночей",
        f"{sleep.SHORT_NIGHT_H:g} ч",
        f"{sleep.AWAKE_LIMIT_H} ч от подъёма",
        f"{sleep.DEBT_7_H:g}",
        f"{sleep.DEBT_14_H:g}",
    ):
        assert needle in text, needle


def test_sleep_topic_describes_illness_tool() -> None:
    text = topic("sleep.md")
    for needle in (
        "get_illness",
        "illness_risk",
        "rhr_high_from",
        "hrv_low_from",
        "streak",
        "confounders",
        "trained_yesterday",
        f"{illness.MIN_BASELINE_DAYS} дней",
        f"{illness.BASELINE_DAYS} дней",
        f"{illness.CENTER_DAYS} дней",
        f"{illness.STREAK_DAYS} дня подряд",
    ):
        assert needle in text, needle


def test_help_index_lists_illness_tool() -> None:
    assert "get_illness" in HELP.read_text()


def test_who5_topic_has_commands_and_fields() -> None:
    text = topic("who5.md")
    for needle in ("coach who5", "coach log who5", "get_who5", "who5.due", "04:00"):
        assert needle in text, needle


def test_who5_topic_has_items_and_scale() -> None:
    text = topic("who5.md")
    for needle in (
        "бодрой",
        "спокойной",
        "активной",
        "просыпаюсь",
        "интерес",
        "всё время",
        "большую часть времени",
        "более половины времени",
        "менее половины времени",
        "некоторое время",
        "никогда",
    ):
        assert needle in text, needle


def test_who5_topic_thresholds_match_constants() -> None:
    text = topic("who5.md")
    for needle in (
        f"{who5.LOW_SCORE} и ниже",
        f"{who5.REDUCED_SCORE} и ниже",
        f"{who5.DROP_POINTS} баллов",
        f"{who5.PERIOD_DAYS} дней",
        "Topp и др., 2015",
    ):
        assert needle in text, needle


def test_help_index_lists_who5() -> None:
    text = HELP.read_text()
    for needle in ("who5.md", "coach who5", "get_who5"):
        assert needle in text, needle


def test_claude_topic_has_commands_and_fields() -> None:
    text = topic("claude.md")
    needles = ("coach sync", "uv run coach claude", "--days", "04:00", "30 дней")
    for needle in (*needles, *CLAUDE_COUNTERS):
        assert needle in text, needle


def test_claude_topic_says_what_is_not_counted() -> None:
    text = topic("claude.md")
    for needle in ("субагент", "коммит", "не попадают"):
        assert needle in text, needle


def test_help_index_lists_claude() -> None:
    assert "claude.md" in HELP.read_text()


def test_pvt_topic_has_metric_poles() -> None:
    text = topic("pvt.md")
    for pole in ("медленные 10 %", "скорость", "больше - быстрее"):
        assert pole in text, pole


def test_calendar_topic_has_pvt_reminder() -> None:
    text = topic("calendar.md")
    for needle in ("Реакция 3 мин", "uv run coach pvt", "09:30"):
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
        "challenge",
        "hindrance",
        "screen_challenge_hours",
        "screen_hindrance_hours",
        "coach screen --days",
        "предложи разметку",
    ):
        assert needle in text, needle


def test_workload_topic_describes_calendar_demand() -> None:
    text = topic("workload.md")
    for needle in (
        "[calendar.demand]",
        "challenge_hours",
        "hindrance_hours",
        "coach sync --days 30",
    ):
        assert needle in text, needle


def test_workload_topic_names_every_demand_key() -> None:
    text = topic("workload.md")
    for key in DEMANDS:
        assert key in text, key


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


def cli_commands(app: typer.Typer, prefix: str = "") -> set[str]:
    """Имена всех команд CLI вида «med add» (обход вложенных групп typer)."""
    names = set()
    for cmd in app.registered_commands:
        assert cmd.callback is not None
        name = cmd.name or cmd.callback.__name__.replace("_", "-")
        names.add(f"{prefix}{name}")
    for group in app.registered_groups:
        assert group.typer_instance is not None
        names |= cli_commands(group.typer_instance, f"{prefix}{group.name} ")
    return names


def help_text() -> str:
    return HELP.read_text() + "".join(p.read_text() for p in topic_files())


def test_cli_commands_walk_finds_commands() -> None:
    names = cli_commands(main.app)
    assert {"food", "med add", "pantry use"} <= names
    assert len(names) > 60


def test_every_cli_command_is_in_help() -> None:
    text = help_text()
    missing = {
        name
        for name in cli_commands(main.app)
        if not re.search(rf"coach {re.escape(name)}(?![\w-])", text)
    }
    assert missing == set(), missing


def test_every_mcp_tool_is_in_help(conn: sqlite3.Connection) -> None:
    text = help_text()
    missing = {name for name in tool_names(conn) if not re.search(rf"\b{name}\b", text)}
    assert missing == set(), missing


def test_every_skill_is_in_help() -> None:
    text = help_text()
    names = [p.parent.name for p in (CLAUDE / "skills").glob("*/SKILL.md")]
    assert names
    missing = {name for name in names if not re.search(rf"(?<![\w-]){name}(?![\w-])", text)}
    assert missing == set(), missing


def test_agents_md_has_help_rule() -> None:
    assert "coach-help" in (ROOT / "AGENTS.md").read_text()


def test_readme_mentions_help() -> None:
    assert "coach-help.md" in (ROOT / "README.md").read_text()


def test_agenda_note_has_focus_title_and_poles() -> None:
    path = AGENTS / "coach-agenda.md"
    text = path.read_text()
    assert "Фокус 1–5?" in text
    for pole in ("рассеян", "собран", "свеж", "выжат", "легко", "через силу"):
        assert pole in text, pole
    assert len(path.read_bytes()) <= 6144
