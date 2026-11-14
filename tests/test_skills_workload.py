import json
from pathlib import Path

from ai_coach.load import deviations

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


def test_coach_md_offers_who5() -> None:
    text = (ROOT / "agents" / "coach.md").read_text()
    assert "who5.due" in text
    assert "9е" in text


def test_recalc_mentions_who5_low() -> None:
    path = ROOT / "skills" / "coach-plan" / "recalc.md"
    assert "who5_low" in path.read_text()


def test_recovery_mentions_who5() -> None:
    path = ROOT / "skills" / "coach-morning" / "recovery.md"
    assert "who5" in path.read_text()


def test_coach_day_mentions_who5_low() -> None:
    assert "who5_low" in (ROOT / "agents" / "coach-day.md").read_text()


def test_coach_week_reads_who5() -> None:
    assert "get_who5" in (ROOT / "agents" / "coach-week.md").read_text()


def test_coach_md_reads_illness_signals() -> None:
    assert "illness.signals" in (ROOT / "agents" / "coach.md").read_text()


def test_recalc_handles_illness_risk() -> None:
    path = ROOT / "skills" / "coach-plan" / "recalc.md"
    assert "illness_risk" in path.read_text()


def test_recalc_and_wellbeing_mention_symptoms() -> None:
    recalc = ROOT / "skills" / "coach-plan" / "recalc.md"
    assert "symptoms" in recalc.read_text()
    assert "symptoms" in WELLBEING.read_text()


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


def test_recalc_lists_every_deviation_code_once_in_full() -> None:
    text = (ROOT / "skills" / "coach-plan" / "recalc.md").read_text()
    for needle in (
        "BELOW",
        "LOW",
        "UNBALANCED",
        "symptoms",
        "wellbeing_below",
        "mood_below",
        f"самочувствие ≤ {deviations.WELLBEING_MAX}",
        f"настроение ≤ {deviations.MOOD_MAX}",
        f"стресс ≥ {deviations.STRESS_MIN}",
        f"readiness < {deviations.READINESS_MIN}",
        f"ATL − CTL > {deviations.ATL_OVER_CTL_MAX}",
        f"сон < {deviations.SLEEP_MIN_HOURS} ч",
    ):
        assert needle in text, needle


def test_recalc_names_every_bad_hrv_status() -> None:
    text = (ROOT / "skills" / "coach-plan" / "recalc.md").read_text()
    assert [s for s in deviations.BAD_HRV_STATUSES if s not in text] == []


def test_coach_md_step_5_has_no_threshold_list_and_points_to_recalc() -> None:
    text = (ROOT / "agents" / "coach.md").read_text()
    step = next(line for line in text.splitlines() if line.startswith("5. Адаптация плана"))
    assert "recalc.md" in step
    assert "get_deviations" in step
    for needle in ("≤ 2", "≥ 4", "< 33", "> 15", "< 6"):
        assert needle not in step, needle


def test_coach_md_keeps_yes_before_editing_or_deleting_food_entries() -> None:
    text = (ROOT / "agents" / "coach.md").read_text()
    step = next(line for line in text.splitlines() if line.startswith("3. Спроси"))
    assert "только после «да»" in step
    assert "coach-help/food.md" in step


def test_get_deviations_description_names_mood_and_stress() -> None:
    from ai_coach.mcp_server.server import TOOLS

    description = TOOLS["get_deviations"][1]
    assert "настроение" in description
    assert "стресс" in description


def test_deviations_docstring_names_mood_and_stress() -> None:
    from ai_coach.mcp_server import tools

    doc = tools.deviations.__doc__ or ""
    assert "настроение" in doc
    assert "стресс" in doc


def test_wellbeing_fields_file_holds_day_fields() -> None:
    text = (ROOT / "agents" / "coach-wellbeing" / "fields.md").read_text()
    for needle in ("work_hours", "screen_work_hours", "claude_prompts", "todo_closed"):
        assert needle in text, needle


def test_wellbeing_agent_links_fields_file_instead_of_listing_fields() -> None:
    text = WELLBEING.read_text()
    assert "coach-wellbeing/fields.md" in text
    assert "screen_hindrance_hours" not in text


def test_allow_can_read_wellbeing_fields_file() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert "Bash(cat .claude/agents/coach-wellbeing/fields.md)" in allow


def test_wellbeing_below_codes_are_in_symptoms_paragraph_not_in_precursors() -> None:
    text = WELLBEING.read_text()
    symptoms = paragraph(text, "Симптомы в тексте")
    precursors = paragraph(text, "Предвестники")
    for code in ("wellbeing_below", "mood_below"):
        assert code in symptoms, code
        assert code not in precursors, code
    assert "план не трогай" in precursors


def test_recovery_mentions_illness() -> None:
    path = ROOT / "skills" / "coach-morning" / "recovery.md"
    assert "illness" in path.read_text()


def test_coach_wellbeing_mentions_workload_tool() -> None:
    assert "get_workload" in WELLBEING.read_text()


def test_wellbeing_fields_file_describes_all_screen_fields() -> None:
    text = (ROOT / "agents" / "coach-wellbeing" / "fields.md").read_text()
    for field in (
        "screen_work_hours",
        "screen_hobby_hours",
        "screen_browser_hours",
        "screen_evening_hours",
        "screen_challenge_hours",
        "screen_hindrance_hours",
    ):
        assert field in text


def test_wellbeing_fields_file_describes_claude_fields_as_observation() -> None:
    text = (ROOT / "agents" / "coach-wellbeing" / "fields.md").read_text()
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


def test_recovery_has_caution_from() -> None:
    path = ROOT / "skills" / "coach-morning" / "recovery.md"
    assert "caution_from" in path.read_text()


def test_day_plan_role_mentions_sleep_signal() -> None:
    text = (ROOT / "agents" / "coach-day.md").read_text()
    assert "short_night" in text
    assert "caution_from" in text
