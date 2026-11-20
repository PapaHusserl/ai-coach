import json
import re
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
    assert "cat .claude/agents/coach/records.md" in step


def test_coach_records_file_exists_and_is_not_empty() -> None:
    assert (ROOT / "agents" / "coach" / "records.md").read_text().strip()


def test_coach_records_file_holds_edit_and_delete_commands() -> None:
    text = (ROOT / "agents" / "coach" / "records.md").read_text()
    assert "uv run coach log" in text
    assert "uv run coach edit|delete food|weight <id>" in text


def test_coach_records_file_points_to_food_help_and_kbzhu_reset() -> None:
    text = (ROOT / "agents" / "coach" / "records.md").read_text()
    assert "coach-help/food.md" in text
    assert "сбрасывает КБЖУ" in text


def test_coach_md_keeps_edit_delete_commands_only_in_records_file() -> None:
    lines = (ROOT / "agents" / "coach.md").read_text().splitlines()
    rest = [line for line in lines if not line.startswith("Что можно")]
    for line in rest:
        assert "uv run coach edit|delete" not in line
        assert "coach log food|weight" not in line


def test_allow_can_read_coach_records_file() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert "Bash(cat .claude/agents/coach/records.md)" in allow


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
        "screen_work_evening_hours",
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


ILLNESS_SIDE = ROOT / "agents" / "coach-wellbeing" / "illness.md"
LADDER_LIMIT = "40 минут"  # константы в коде нет: стоит в боковом файле и в sleep.md
CARE_SIDE = ROOT / "agents" / "coach-wellbeing" / "care.md"
MEASURE_TEXTS = (
    WELLBEING,
    ILLNESS_SIDE,
    CARE_SIDE,
    ROOT / "skills" / "coach-plan" / "recalc.md",
    ROOT / "agents" / "coach-help" / "sleep.md",
    ROOT / "agents" / "coach-help" / "deviations.md",
    ROOT / "agents" / "coach-help.md",
)


def illness_side() -> str:
    return ILLNESS_SIDE.read_text(encoding="utf-8")


def lines_with(text: str, word: str) -> list[str]:
    return [ln for ln in text.splitlines() if word in ln]


def test_wellbeing_role_names_streak_phases_and_side_file() -> None:
    text = WELLBEING.read_text(encoding="utf-8")
    for needle in (
        "hrv_streak",
        "illness_rest",
        "illness_return",
        "coach-wellbeing/illness.md",
    ):
        assert needle in text, needle


def test_illness_side_file_exists_and_is_not_empty() -> None:
    assert ILLNESS_SIDE.is_file()
    assert ILLNESS_SIDE.read_bytes()


def test_allow_can_read_illness_side_file() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert "Bash(cat .claude/agents/coach-wellbeing/illness.md)" in allow


def test_recalc_names_new_deviation_and_streak_codes() -> None:
    text = (ROOT / "skills" / "coach-plan" / "recalc.md").read_text(encoding="utf-8")
    for code in ("fever", "hrv_streak", "illness_rest", "illness_return"):
        assert code in text, code
    assert any("3 дня" in ln for ln in lines_with(text, "hrv_streak"))
    assert "coach-wellbeing/illness.md" in text


def test_illness_side_file_names_signals_and_numbers_from_constants() -> None:
    from ai_coach.load.episode import (
        HRV_STREAK_DAYS,
        REST_DAYS,
        REST_MAX_DAYS,
        RETURN_DAYS,
        SPO2_MIN,
    )

    text = illness_side()
    for code in ("hrv_streak", "illness_rest", "illness_return"):
        assert f"`{code}`" in text, code
    fever = f"{deviations.FEVER_FROM:g}".replace(".", ",")
    assert fever in text.replace(".", ",")
    checks = (
        ("hrv_streak", f"{HRV_STREAK_DAYS} дня"),
        ("illness_rest", f"{REST_DAYS} чистых дня"),
        ("потолок", f"{REST_MAX_DAYS} дня"),
        ("лестниц", f"{RETURN_DAYS} дней"),
        ("SpO2", f"{SPO2_MIN}"),
    )
    for word, number in checks:
        assert any(number in ln for ln in lines_with(text, word)), (word, number)
    assert LADDER_LIMIT in text


def test_illness_side_file_severe_signs_line_names_all_three_measures() -> None:
    lines = lines_with(illness_side(), "озноб")
    assert lines
    for needle in ("ломот", "fever", "нагрузк"):
        assert any(needle in ln for ln in lines), needle


def test_illness_side_file_names_every_reason_code_and_by_cap() -> None:
    text = illness_side()
    for code in ("no_record", "no_night", "corridor", "skin_temp", "respiration", "spo2"):
        assert f"`{code}`" in text, code
    assert "`by_cap`" in text


def test_illness_side_file_covers_unread_abbreviation_with_both_ways() -> None:
    text = illness_side()
    lines = lines_with(text, "темп")
    assert lines
    joined = " ".join(lines)
    assert "fever" in joined
    assert "температура" in joined
    assert "форм" in joined
    assert "не переписывай" in text


def test_deviations_help_trainer_line_says_unread_temperature_is_named() -> None:
    text = (ROOT / "agents" / "coach-help" / "deviations.md").read_text(encoding="utf-8")
    trainer = [ln for ln in lines_with(text, "Что делает тренер") if "прочёл" in ln]
    assert len(trainer) == 1
    assert "не прочёл" in trainer[0]
    assert "темп." in trainer[0]
    assert "форм" in trainer[0]
    for stem in ("озноб", "ломот", "нагрузк"):
        assert stem in trainer[0], stem


def test_sleep_help_trainer_line_names_rest_and_return_phases() -> None:
    path = ROOT / "agents" / "coach-help" / "sleep.md"
    text = path.read_text(encoding="utf-8")
    section = text.split("## Возможно, заболеваешь", 1)[1].split("\n## ", 1)[0]
    lines = [ln for ln in section.splitlines() if ln.startswith("- Что делает тренер")]
    assert len(lines) == 1
    for needle in ("illness_rest", "illness_return", "hrv_streak", LADDER_LIMIT):
        assert needle in lines[0], needle


def test_coach_help_index_names_streak_rest_and_return() -> None:
    text = (ROOT / "agents" / "coach-help.md").read_text(encoding="utf-8")
    assert "серия статуса HRV" in text
    assert "покой и возврат после болезни" in text


def test_readme_illness_line_names_streak_rest_and_return() -> None:
    text = (ROOT.parent / "README.md").read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.startswith("- Возможно, заболеваешь:")]
    assert len(lines) == 1
    for code in ("hrv_streak", "illness_rest", "illness_return"):
        assert code in lines[0], code


def test_measure_texts_do_not_mention_covid() -> None:
    for path in MEASURE_TEXTS:
        text = path.read_text(encoding="utf-8").lower()
        assert "ковид" not in text, path.name
        assert "covid" not in text, path.name


def care() -> str:
    return CARE_SIDE.read_text(encoding="utf-8")


def care_lines(word: str) -> list[str]:
    found = lines_with(care(), word)
    assert found, word
    return found


def test_care_side_file_exists_and_is_not_empty() -> None:
    assert CARE_SIDE.is_file()
    assert CARE_SIDE.read_bytes()


def test_allow_can_read_care_side_file() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert "Bash(cat .claude/agents/coach-wellbeing/care.md)" in allow


def test_care_names_every_advice() -> None:
    text = care().lower()
    for needle in ("сон", "солевой раствор", "полоскан", "цинк", "флаг", "п. 8б"):
        assert needle in text, needle


def test_care_gives_source_in_brackets_for_advice() -> None:
    text = care()
    for source in ("Cohen 2009", "Little 2024", "Cochrane 2024"):
        assert re.search(rf"\([^)]*{source}[^)]*\)", text), source


def test_care_nose_and_throat_line_has_ramalingam_source_in_brackets() -> None:
    assert any(re.search(r"\([^)]*Ramalingam 2019[^)]*\)", ln) for ln in care_lines("солевой"))


def test_care_sleep_line_says_eight_hours_and_more() -> None:
    assert "8 ч и больше" in care()


def test_care_zinc_line_says_about_two_days_shorter_and_by_instruction() -> None:
    lines = care_lines("цинк")
    assert any("около 2 дней короче" in ln for ln in lines)
    assert any("по инструкции" in ln for ln in lines)


def test_care_does_not_say_small_effect() -> None:
    assert "эффект небольшой" not in care()


def test_care_weakness_words_list_has_plain_tiredness_without_reason_clause() -> None:
    line = next(ln for ln in care_lines("Слова слабости:") if ln.startswith("Слова слабости:"))
    assert "усталость" in line.lower()
    assert "без причины" not in line


def test_care_says_recap_of_research_not_prescription() -> None:
    assert "не назначение" in care()


def test_care_nose_and_throat_line_says_several_times_a_day_without_number() -> None:
    assert any("несколько раз в день" in ln for ln in care_lines("солевой"))
    assert "4–6" not in care()


def test_care_zinc_line_names_low_data_quality() -> None:
    assert any("низкое качество" in ln for ln in care_lines("цинк"))


def test_care_hedges_nose_and_zinc_for_first_symptoms() -> None:
    assert any("при первых симптомах" in ln for ln in care_lines("солевой"))
    assert any("если симптомы начались сегодня" in ln for ln in care_lines("цинк"))


def test_care_names_triggers() -> None:
    text = care()
    for code in ("illness_risk", "symptoms", "fever"):
        assert code in text, code


def test_care_says_other_signals_are_not_a_trigger() -> None:
    for code in ("corridor_out", "hrv_streak", "mood_below", "mood"):
        assert all("не повод" in ln for ln in care_lines(code)), code


def test_care_full_set_starts_by_limit_or_sick_first() -> None:
    text = care()
    for needle in ("value", "limit", "episode.sick_first", "episode.sick_last"):
        assert needle in text, needle


def test_care_repeat_line_has_no_zinc() -> None:
    line = next(ln for ln in care_lines("Одна фраза:") if ln.startswith("Одна фраза:"))
    assert "советы прежние" in line
    assert "цинк" not in line.lower()


def test_care_weakness_line_names_fields_and_conditions() -> None:
    text = care()
    assert "wellbeing_below" in text
    assert "серия не идёт" in text
    for needle in ("wellbeing", "symptoms", "fever", "illness_risk"):
        assert needle in text, needle


def test_care_weakness_line_gives_sleep_saline_and_zinc_of_first_day() -> None:
    text = care()
    assert "Самочувствие ниже обычного - сегодня лечь раньше." in text
    assert "солевой раствор в нос и полоскание несколько раз в день" in text
    assert "цинк - только с первого дня симптомов, данные слабые" in text
    assert "Появятся горло, нос или кашель - в тот же день" in text
    assert "Это пересказ исследований, не назначение." in text


def test_care_lists_weakness_words_and_says_trainer_reads_records() -> None:
    text = care().lower()
    for stem in ("слабост", "разбит", "вялост", "недомогани", "нет сил", "усталост"):
        assert stem in text, stem
    assert re.search(r"чита\w+ (записи|тексты)", text)


def test_care_does_not_repeat_load_measures_and_points_to_illness_file() -> None:
    text = care().lower()
    assert "coach-wellbeing/illness.md" in text
    for word in ("интервал", "лестниц"):
        assert word not in text, word


def test_wellbeing_illness_risk_paragraph_points_to_care_not_old_advice() -> None:
    text = paragraph(WELLBEING.read_text(encoding="utf-8"), "Возможно, заболеваешь")
    assert "coach-wellbeing/care.md" in text
    assert "Совет: лечь раньше, нагрузку не добирать" not in text


def test_wellbeing_symptoms_paragraph_points_to_care_and_keeps_measures() -> None:
    text = paragraph(WELLBEING.read_text(encoding="utf-8"), "Симптомы в тексте")
    assert "coach-wellbeing/care.md" in text
    assert "снять интенсивное" in text
    assert "Температура - п. 8б" in text


def test_wellbeing_precursors_paragraph_points_to_care_and_keeps_plan() -> None:
    text = paragraph(WELLBEING.read_text(encoding="utf-8"), "Предвестники")
    assert "coach-wellbeing/care.md" in text
    assert "план не трогай" in text


def test_wellbeing_sleep_paragraph_names_season_and_overload_days() -> None:
    text = paragraph(WELLBEING.read_text(encoding="utf-8"), "Сон:")
    for needle in ("октябр", "март", "total_streak", "evening_streak"):
        assert needle in text, needle


def test_illness_side_file_points_red_flags_to_8b_and_not_to_care() -> None:
    text = illness_side()
    assert "красные флаги - п. 8б" in text
    assert "care.md" not in text
