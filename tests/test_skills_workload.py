import json
from pathlib import Path

from text_limits import AGENT_LIMITS, SKILL_LIMIT

ROOT = Path(__file__).resolve().parent.parent / ".claude"
WELLBEING = ROOT / "agents" / "coach-wellbeing.md"


def test_coach_wellbeing_exists() -> None:
    assert WELLBEING.is_file()


def test_coach_wellbeing_describes_illness_reaction() -> None:
    text = WELLBEING.read_text()
    for needle in (
        "illness_risk",
        "rhr_high_from",
        "hrv_low_from",
        "streak",
        "confounders",
        "снять интенсивное",
        "лечь раньше",
        "нагрузку не добирать",
    ):
        assert needle in text, needle


def test_coach_wellbeing_describes_who5_reaction() -> None:
    text = WELLBEING.read_text()
    for needle in (
        "WHO-5",
        "who5_low",
        "low_until",
        "врачу или психологу",
        "щажения",
        "предложение одно",
        "двумя окнами",
        "coach-help/who5.md",
    ):
        assert needle in text, needle


def test_coach_md_offers_who5_and_fits_limit() -> None:
    path = ROOT / "agents" / "coach.md"
    text = path.read_text()
    assert "who5.due" in text
    assert "9е" in text
    assert len(path.read_bytes()) <= AGENT_LIMITS["coach.md"]


def test_recalc_mentions_who5_low_and_fits_limit() -> None:
    path = ROOT / "skills" / "coach-plan" / "recalc.md"
    assert "who5_low" in path.read_text()
    assert len(path.read_bytes()) <= SKILL_LIMIT


def test_recovery_mentions_who5_and_fits_limit() -> None:
    path = ROOT / "skills" / "coach-morning" / "recovery.md"
    assert "who5" in path.read_text()
    assert len(path.read_bytes()) <= SKILL_LIMIT


def test_coach_day_mentions_who5_low_and_fits_limit() -> None:
    path = ROOT / "agents" / "coach-day.md"
    assert "who5_low" in path.read_text()
    assert len(path.read_bytes()) <= AGENT_LIMITS["coach-day.md"]


def test_coach_week_reads_who5_and_fits_limit() -> None:
    path = ROOT / "agents" / "coach-week.md"
    assert "get_who5" in path.read_text()
    assert len(path.read_bytes()) <= AGENT_LIMITS["coach-week.md"]


def test_coach_md_reads_illness_signals() -> None:
    assert "illness.signals" in (ROOT / "agents" / "coach.md").read_text()


def test_recalc_handles_illness_risk_and_fits_limit() -> None:
    path = ROOT / "skills" / "coach-plan" / "recalc.md"
    assert "illness_risk" in path.read_text()
    assert len(path.read_bytes()) <= SKILL_LIMIT


def test_recalc_and_wellbeing_mention_symptoms_and_fit_limits() -> None:
    recalc = ROOT / "skills" / "coach-plan" / "recalc.md"
    assert "symptoms" in recalc.read_text()
    assert len(recalc.read_bytes()) <= SKILL_LIMIT
    assert "symptoms" in WELLBEING.read_text()
    assert len(WELLBEING.read_bytes()) <= AGENT_LIMITS["coach-wellbeing.md"]


def test_coach_wellbeing_has_precursors_paragraph_that_keeps_the_plan() -> None:
    text = WELLBEING.read_text()
    assert "Предвестники" in text
    assert "план не трогай" in text


def paragraph(text: str, start: str) -> str:
    found = [p for p in text.split("\n\n") if p.startswith(start)]
    assert len(found) == 1, start
    return found[0]


def test_recalc_lists_below_norm_codes_in_the_deviations_sentence() -> None:
    text = (ROOT / "skills" / "coach-plan" / "recalc.md").read_text()
    deviations_part = text.split("или есть сигналы перегруза")[0]
    assert "wellbeing_below" in deviations_part
    assert "mood_below" in deviations_part
    assert "не пересчёт" not in text


def test_wellbeing_below_codes_are_in_symptoms_paragraph_not_in_precursors() -> None:
    text = WELLBEING.read_text()
    symptoms = paragraph(text, "Симптомы в тексте")
    precursors = paragraph(text, "Предвестники")
    for code in ("wellbeing_below", "mood_below"):
        assert code in symptoms, code
        assert code not in precursors, code
    assert "план не трогай" in precursors


def test_recovery_mentions_illness_and_fits_limit() -> None:
    path = ROOT / "skills" / "coach-morning" / "recovery.md"
    assert "illness" in path.read_text()
    assert len(path.read_bytes()) <= SKILL_LIMIT


def test_coach_wellbeing_mentions_workload_tool() -> None:
    assert "get_workload" in WELLBEING.read_text()


def test_coach_wellbeing_describes_all_screen_fields() -> None:
    text = WELLBEING.read_text()
    for field in (
        "screen_work_hours",
        "screen_hobby_hours",
        "screen_browser_hours",
        "screen_evening_hours",
        "screen_challenge_hours",
        "screen_hindrance_hours",
    ):
        assert field in text


def test_coach_wellbeing_describes_claude_fields_as_observation() -> None:
    text = WELLBEING.read_text()
    for field in (
        "claude_prompts",
        "claude_prompts_evening",
        "claude_decisions",
        "claude_repos",
        "claude_switches",
    ):
        assert field in text
    assert "наблюдение" in text


def test_coach_wellbeing_explains_unmarked_demand_note() -> None:
    assert "вызов/помеха не размечены" in WELLBEING.read_text()


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
    assert len((ROOT / "agents" / "coach.md").read_bytes()) <= AGENT_LIMITS["coach.md"]


def test_wellbeing_has_sleep_rule() -> None:
    text = WELLBEING.read_text()
    for needle in (
        "short_night",
        "sleep_debt",
        "caution_from",
        "debt_7_h",
        "не считай восстановлением",
    ):
        assert needle in text, needle


def test_coach_summary_points_to_sleep_signals() -> None:
    assert "sleep.signals" in (ROOT / "agents" / "coach.md").read_text()


def test_recovery_has_caution_from_and_is_short() -> None:
    path = ROOT / "skills" / "coach-morning" / "recovery.md"
    assert "caution_from" in path.read_text()
    assert len(path.read_bytes()) <= SKILL_LIMIT


def test_day_plan_role_mentions_sleep_signal() -> None:
    text = (ROOT / "agents" / "coach-day.md").read_text()
    assert "short_night" in text
    assert "caution_from" in text
