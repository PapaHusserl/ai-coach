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


PRECURSORS = ROOT / "agents" / "coach-wellbeing" / "precursors.md"


def test_precursors_file_has_paragraph_that_keeps_the_plan() -> None:
    text = PRECURSORS.read_text()
    assert "Предвестники" in text
    assert "план не трогай" in text


def test_coach_wellbeing_links_precursors_file() -> None:
    assert "cat .claude/agents/coach-wellbeing/precursors.md" in WELLBEING.read_text()


def test_allow_can_read_precursors_file() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert "Bash(cat .claude/agents/coach-wellbeing/precursors.md)" in allow


def test_recalc_names_new_rows_and_points_to_precursors_file() -> None:
    text = (ROOT / "skills" / "coach-plan" / "recalc.md").read_text()
    for needle in ("fatigue", "irritability", "`day`", "coach-wellbeing/precursors.md"):
        assert needle in text, needle


def test_recalc_deviations_sentence_does_not_list_new_rows() -> None:
    text = (ROOT / "skills" / "coach-plan" / "recalc.md").read_text()
    deviations_part = text.split("или есть сигналы перегруза")[0]
    assert "fatigue" not in deviations_part
    assert "irritability" not in deviations_part


def test_precursors_file_names_thresholds_and_yesterday_evening_rule() -> None:
    text = PRECURSORS.read_text()
    for needle in ("fatigue", "irritability", "`day`", "вчера вечером"):
        assert needle in text, needle


def test_precursors_yesterday_paragraph_names_below_norm_and_recalc_argument() -> None:
    text = paragraph(PRECURSORS.read_text(), "Вчерашний вечер")
    for needle in ("`mood_below`", "довод в пересчёте", "`recalc.md`"):
        assert needle in text, needle


def test_precursors_paragraph_asks_whether_illness_starts() -> None:
    text = paragraph(PRECURSORS.read_text(), "Предвестники")
    assert "не заболевает ли" in text
    assert "fatigue" in text
    assert "irritability" in text


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
    precursors = paragraph(PRECURSORS.read_text(), "Предвестники")
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


FIELDS = ROOT / "agents" / "coach-wellbeing" / "fields.md"


def test_coach_wellbeing_explains_unmarked_demand_note() -> None:
    assert "вызов/помеха не размечены" in FIELDS.read_text()


def test_coach_wellbeing_gives_hours_priority_manual_screen_calendar() -> None:
    text = WELLBEING.read_text()
    assert "ручные (вечерний чек-ин) > экран > календарь" in text


def test_coach_wellbeing_explains_screen_lines_of_sync_summary() -> None:
    text = FIELDS.read_text()
    assert "экран не настроен" in text
    assert "экран: …" in text
    assert "ActivityWatch" in text


def test_coach_wellbeing_no_longer_holds_sync_screen_lines() -> None:
    text = WELLBEING.read_text()
    assert "экран не настроен" not in text
    assert "вызов/помеха не размечены" not in text


def test_coach_wellbeing_points_to_fields_file_for_sync_messages() -> None:
    assert "cat .claude/agents/coach-wellbeing/fields.md" in WELLBEING.read_text()


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
COVID_SIDE = ROOT / "agents" / "coach-wellbeing" / "covid.md"
COVID_TOPIC = ROOT / "agents" / "coach-help" / "illness-return.md"
MEASURE_TEXTS = (
    WELLBEING,
    ILLNESS_SIDE,
    CARE_SIDE,
    COVID_SIDE,
    ROOT / "skills" / "coach-plan" / "recalc.md",
    ROOT / "agents" / "coach-help" / "sleep.md",
    COVID_TOPIC,
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


COVID_TEXTS = ("covid.md", "illness.md", "illness-return.md", "sleep.md")
NO_COVID_TEXTS = tuple(path for path in MEASURE_TEXTS if path.name not in COVID_TEXTS)


def test_covid_is_named_only_in_covid_texts() -> None:
    assert NO_COVID_TEXTS
    for path in NO_COVID_TEXTS:
        text = path.read_text(encoding="utf-8").lower()
        if path == WELLBEING:  # ссылка на covid.md и ключ episode.covid разрешены
            text = text.replace("coach-wellbeing/covid.md", "").replace("episode.covid", "")
        assert "ковид" not in text, path.name
        assert "covid" not in text, path.name


def sentence_around(line: str, needle: str) -> str:
    """Предложение строки (границы — «. » и край строки), в котором стоит needle."""
    at = line.index(needle)
    start = line.rfind(". ", 0, at) + 2 if ". " in line[:at] else 0
    end = line.find(". ", at)
    return line[start : end if end >= 0 else len(line)]


def coach_text() -> str:
    return (ROOT / "agents" / "coach.md").read_text(encoding="utf-8")


def test_coach_morning_step_reads_wellbeing_before_summary_without_covid_condition() -> None:
    lines = lines_with(coach_text(), "2. Один раз вызови")
    assert len(lines) == 1
    command = "`cat .claude/agents/coach-wellbeing.md`"
    for needle in ("illness.signals", "до сводки", command):
        assert needle in lines[0], needle
    assert lines[0].index("до сводки") < lines[0].index(command)
    assert "series_day" not in lines[0]


def test_coach_step_2a_reads_covid_side_before_summary_even_without_signals() -> None:
    from ai_coach.load.covid import COVID_REST_DAYS

    lines = [ln for ln in coach_text().splitlines() if ln.startswith("2а.")]
    assert len(lines) == 1
    command = "`cat .claude/agents/coach-wellbeing/covid.md`"
    for needle in (
        "illness.episode.series_day",
        f"от 1 до {COVID_REST_DAYS}",
        "illness.episode.covid",
        "до сводки",
        command,
    ):
        assert needle in lines[0], needle
    assert lines[0].index("до сводки") < lines[0].index(command)


def test_coach_step_3_keeps_past_entries_and_records_link() -> None:
    step = next(ln for ln in coach_text().splitlines() if ln.startswith("3. Спроси"))
    assert "--at" in step
    assert "cat .claude/agents/coach/records.md" in step


def test_coach_step_3_names_group_backfill() -> None:
    step = next(ln for ln in coach_text().splitlines() if ln.startswith("3. Спроси"))
    assert "дозапись групп" in step


def test_coach_records_file_holds_group_backfill_pointer() -> None:
    text = (ROOT / "agents" / "coach" / "records.md").read_text(encoding="utf-8")
    assert "cat .claude/skills/coach-food/groups.md" in text
    assert "Дозапись старым записям" in text


def test_coach_md_has_no_groups_file_line() -> None:
    assert "coach-food/groups.md" not in coach_text()


def test_coach_records_file_starts_with_past_entry_rule() -> None:
    text = (ROOT / "agents" / "coach" / "records.md").read_text(encoding="utf-8")
    assert "--at <YYYY-MM-DD>" in text
    assert "12:00" in text
    assert "в будущее нельзя" in text


def test_wellbeing_illness_line_links_covid_side_with_condition() -> None:
    from ai_coach.load.covid import COVID_REST_DAYS

    lines = lines_with(WELLBEING.read_text(encoding="utf-8"), "Возможно, заболеваешь")
    assert len(lines) == 1
    command = "`cat .claude/agents/coach-wellbeing/covid.md`"
    sentence = sentence_around(lines[0], command)
    for needle in ("episode.series_day", f"от 1 до {COVID_REST_DAYS}", "episode.covid"):
        assert needle in sentence, needle


def test_illness_side_first_item_links_covid_side_with_condition() -> None:
    from ai_coach.load.covid import COVID_REST_DAYS

    lines = lines_with(illness_side(), "covid.md")
    assert len(lines) == 1
    for needle in (
        "episode.series_day",
        f"от 1 до {COVID_REST_DAYS}",
        "episode.covid",
        "illness_light",
    ):
        assert needle in lines[0], needle
    items = [ln for ln in illness_side().splitlines() if ln.startswith("- ")]
    assert items[0] == lines[0]


def test_every_covid_path_condition_uses_covid_rest_days() -> None:
    from ai_coach.load.covid import COVID_REST_DAYS

    paths = (ROOT / "agents" / "coach.md", WELLBEING, ILLNESS_SIDE)
    for path in paths:
        found = re.findall(r"от 1 до (\d+)", path.read_text(encoding="utf-8"))
        assert found, path.name
        assert set(found) == {str(COVID_REST_DAYS)}, path.name


def test_covid_side_first_line_names_all_source_files() -> None:
    first = covid_side().splitlines()[0]
    for name in ("coach.md", "coach-wellbeing.md", "illness.md"):
        assert name in first, name


def test_covid_question_and_reminder_lines_say_first_answer_of_session() -> None:
    for marker in (COVID_QUESTION, COVID_REMINDER):
        lines = lines_with(covid_side(), marker)
        assert len(lines) == 1
        assert "в первом ответе сессии" in lines[0], marker


def test_covid_texts_mention_covid() -> None:
    named = [path for path in MEASURE_TEXTS if path.name in COVID_TEXTS]
    assert {path.name for path in named} == set(COVID_TEXTS)
    for path in named:
        assert "covid" in path.read_text(encoding="utf-8").lower(), path.name


COVID_QUESTION = "тест на COVID делал?"
COVID_REMINDER = "если тест на COVID положительный — скажи: отмечу, будет 5 дней лёгкого режима"


def covid_side() -> str:
    return COVID_SIDE.read_text(encoding="utf-8")


def test_covid_side_file_is_within_size_and_names_command_and_numbers() -> None:
    assert COVID_SIDE.is_file()
    text = covid_side()
    assert len(text.encode("utf-8")) <= 4096
    for needle in (
        "coach covid",
        "coach covid --undo",
        "episode.covid",
        "light",
        "5",
        "6-го",
        "BJSM 2022",
    ):
        assert needle in text, needle


def test_allow_can_read_covid_side_file() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert "Bash(cat .claude/agents/coach-wellbeing/covid.md)" in allow


def test_covid_question_line_names_condition_keys() -> None:
    lines = lines_with(covid_side(), COVID_QUESTION)
    assert len(lines) == 1
    for needle in ("episode.severe", "episode.series_day", "5", "episode.covid", "в каждой сессии"):
        assert needle in lines[0], needle
    assert "episode.sick_first" not in lines[0]


def test_covid_question_commands_stand_after_yes() -> None:
    lines = lines_with(covid_side(), COVID_QUESTION)
    assert len(lines) == 1
    for command in ("`uv run coach covid`", "`uv run coach covid --undo`"):
        assert re.search(f"после «да»[^.;]*{re.escape(command)}", lines[0]), command


def test_covid_reminder_line_names_keys_and_forbids_question_on_light() -> None:
    lines = lines_with(covid_side(), COVID_REMINDER)
    assert len(lines) == 1
    for needle in ("episode.severe", "episode.sick_first", "episode.covid", "не спрашивай"):
        assert needle in lines[0], needle
    assert re.search("после «да»[^.;]*`uv run coach covid`", lines[0])


def test_covid_severe_series_line_names_steps_and_source() -> None:
    lines = lines_with(covid_side(), "тяжёлая серия")
    assert len(lines) == 1
    for needle in (
        "episode.severe",
        "episode.covid",
        "после COVID",
        "5-го",
        "не раньше 6-го",
        "13-го",
        "BJSM 2022",
        "дословно",
        "episode.sick_first",
        "ДД.ММ",
        "(<дата 6-го дня>, BJSM 2022)",
        "(<дата 13-го дня>)",
        "на пункты не дели",
    ):
        assert needle in lines[0], needle
    assert "можно добавить" not in lines[0]


def test_covid_header_line_names_severe_by_symptoms() -> None:
    lines = lines_with(covid_side(), "Поля `get_illness`")
    assert len(lines) == 1
    for needle in ("ознобом", "ломотой", "температурой от 37,0"):
        assert needle in lines[0], needle
    assert "тяжёлая серия" not in lines[0]


def test_covid_light_series_line_names_days_and_source() -> None:
    lines = [ln for ln in lines_with(covid_side(), "лёгкая серия") if "light" in ln]
    assert len(lines) == 1
    for needle in ("5 дней от начала болезни", "покоя нет", "40 минут", "BJSM 2022"):
        assert needle in lines[0], needle


def test_covid_topic_quotes_question_and_reminder_verbatim() -> None:
    text = COVID_TOPIC.read_text(encoding="utf-8")
    assert COVID_QUESTION in text
    assert COVID_REMINDER in text


def test_illness_side_links_covid_side_and_keeps_reserve() -> None:
    assert "cat .claude/agents/coach-wellbeing/covid.md" in illness_side()
    assert 4096 - len(ILLNESS_SIDE.read_bytes()) >= 200


def test_readme_illness_line_names_covid_command() -> None:
    text = (ROOT.parent / "README.md").read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.startswith("- Возможно, заболеваешь:")]
    assert len(lines) == 1
    assert "COVID" in lines[0]
    assert "coach covid" in lines[0]


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
    text = paragraph(PRECURSORS.read_text(encoding="utf-8"), "Предвестники")
    assert "coach-wellbeing/care.md" in text
    assert "план не трогай" in text


def test_wellbeing_sleep_paragraph_names_season_and_overload_days() -> None:
    text = paragraph(WELLBEING.read_text(encoding="utf-8"), "Сон:")
    for needle in ("октябр", "март", "total_streak", "evening_streak"):
        assert needle in text, needle


def care_sleep_section() -> str:
    return CARE_SIDE.read_text().split("## Сон в сезон", 1)[1].split("\n## ", 1)[0]


def test_care_season_section_names_efficiency_rule() -> None:
    text = care_sleep_section()
    for needle in (
        "efficiency",
        "92",
        "без сигнала сна",
        "эффективность сна",
        "для часов порог не проверен",
    ):
        assert needle in text, needle


def test_care_season_section_does_not_glue_efficiency_to_the_sleep_line() -> None:
    assert "в той же строке" not in care_sleep_section()


def test_morning_recovery_line_names_efficiency_rule() -> None:
    line = next(
        ln
        for ln in (ROOT / "skills" / "coach-morning" / "recovery.md").read_text().splitlines()
        if ln.startswith("- Восстановление")
    )
    for needle in ("efficiency", "92", "октябр", "март", "эффективность сна"):
        assert needle in line, needle


def test_illness_side_file_points_red_flags_to_8b_and_not_to_care() -> None:
    text = illness_side()
    assert "красные флаги - п. 8б" in text
    assert "care.md" not in text


def test_coach_md_reads_weather_signals_next_to_illness_signals() -> None:
    text = (ROOT / "agents" / "coach.md").read_text()
    assert "weather.signals" in text
    assert text.index("illness.signals") < text.index("weather.signals")


def test_morning_skill_morning_line_names_weather_signal_words() -> None:
    text = (ROOT / "skills" / "coach-morning" / "SKILL.md").read_text()
    line = next(ln for ln in text.splitlines() if "weather.signals" in ln)
    for needle in ("`at`", "порог", "возможно ухудшение самочувствия", "Как сейчас?", "план"):
        assert needle in line, needle


def test_precursors_weather_paragraph_has_pressure_phrase_and_asks() -> None:
    text = paragraph(PRECURSORS.read_text(), "Погода")
    for needle in (
        "weather.signals",
        "Давление к 19:00 упадёт на 7 гПа (порог 5)",
        "возможно ухудшение самочувствия",
        "Как сейчас?",
        "план не трогай",
    ):
        assert needle in text, needle


def test_precursors_weather_paragraph_has_temperature_phrases() -> None:
    text = paragraph(PRECURSORS.read_text(), "Погода")
    assert "Температура к 15:00 вырастет на 8° (порог 7)" in text
    assert "упадёт на 8°" in text


def test_precursors_weather_paragraph_has_one_phrase_for_two_signals() -> None:
    text = paragraph(PRECURSORS.read_text(), "Погода")
    sample = (
        "Давление к 19:00 упадёт на 7 гПа (порог 5), температура к 15:00 вырастет на 8° "
        "(порог 7) - возможно ухудшение самочувствия. Как сейчас?"
    )
    assert sample in text


def test_precursors_weather_paragraph_names_row_keys_and_tomorrow() -> None:
    text = paragraph(PRECURSORS.read_text(), "Погода")
    for needle in ("`at`", "`next_day`", "завтра к"):
        assert needle in text, needle


def test_precursors_weather_paragraph_is_silent_after_a_bad_day() -> None:
    text = paragraph(PRECURSORS.read_text(), "Погода")
    assert "после плохого дня" in text


def test_precursors_weather_paragraph_has_no_old_words() -> None:
    text = paragraph(PRECURSORS.read_text(), "Погода")
    assert "ориентир" not in text
    assert "за сутки" not in text


def test_precursors_file_stays_within_side_limit() -> None:
    assert len(PRECURSORS.read_bytes()) <= 4096


def test_wellbeing_line_17_names_weather_next_to_precursors() -> None:
    line = WELLBEING.read_text().splitlines()[16]
    assert "погод" in line.lower()
    assert "coach-wellbeing/precursors.md" in line


def test_morning_recovery_names_weather_key() -> None:
    text = (ROOT / "skills" / "coach-morning" / "recovery.md").read_text()
    assert "`weather`" in text


PRECURSORS_CAT = "cat .claude/agents/coach-wellbeing/precursors.md"


def test_morning_skill_weather_line_has_time_next_day_and_full_cat() -> None:
    text = (ROOT / "skills" / "coach-morning" / "SKILL.md").read_text()
    line = next(ln for ln in text.splitlines() if "weather.signals" in ln)
    for needle in ("до 12:00", "`next_day`", "завтра к", PRECURSORS_CAT):
        assert needle in line, needle


def test_morning_skill_weather_line_comes_after_plan_for_today_line() -> None:
    lines = (ROOT / "skills" / "coach-morning" / "SKILL.md").read_text().splitlines()
    plan = next(i for i, ln in enumerate(lines) if "план на сегодня - что стоит" in ln)
    weather = next(i for i, ln in enumerate(lines) if "weather.signals" in ln)
    assert plan < weather


def test_morning_recovery_weather_pointer_is_full_cat() -> None:
    line = next(
        ln
        for ln in (ROOT / "skills" / "coach-morning" / "recovery.md").read_text().splitlines()
        if ln.startswith("- Восстановление")
    )
    assert "`weather`" in line
    assert PRECURSORS_CAT in line


def test_wellbeing_confounders_phrase_names_four_causes() -> None:
    phrase = (
        "вчера тренировка / короткая ночь / рабочий вечер / тяжёлый день - сдвиг мог быть от них"
    )
    assert phrase in WELLBEING.read_text()


def test_wellbeing_role_points_to_recovery_side_file() -> None:
    assert "cat .claude/agents/coach-wellbeing/recovery.md" in WELLBEING.read_text()


def test_weather_topic_threshold_words_are_not_tied_to_marks_or_backlog() -> None:
    text = (ROOT / "agents" / "coach-help" / "weather.md").read_text()
    assert "Пороги ты выбрал сам по своему ряду погоды" in text
    assert "под плохие дни они не подогнаны" in text
    assert "Личная подстройка - позже" in text
    assert "отметок" not in text
    assert "BACKLOG 147" not in text


# шаг Н8, партия 2: переключения и длинные отрезки

ATTENTION = ROOT / "agents" / "coach-wellbeing" / "attention.md"
ATTENTION_CAT = "cat .claude/agents/coach-wellbeing/attention.md"
SWITCHING_PHRASE = (
    "Вчера переключений между видами работы N в час - больше твоего обычного (медиана M). "
    "Это про усталость, не про продуктивность: как себя чувствуешь? Предлагаю почту и "
    "мессенджеры разбирать пачками 2-3 раза в день, а перед вынужденным переключением "
    "записывать строчку, где остановился."
)
STRETCH_PHRASE = (
    "Вчера самый длинный отрезок работы без паузы - N ч (порог 2). Предлагаю сегодня "
    "паузу-прогулку на 10 минут в середине такого отрезка - поставить в план дня?"
)


def test_wellbeing_points_to_attention_side_file() -> None:
    assert ATTENTION_CAT in WELLBEING.read_text()


def test_wellbeing_names_attention_signals() -> None:
    text = WELLBEING.read_text()
    assert "switching_high" in text
    assert "long_stretch" in text


def test_allow_can_read_attention_file() -> None:
    allow = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]
    assert f"Bash({ATTENTION_CAT})" in allow


def test_attention_file_has_switching_phrase_verbatim() -> None:
    assert SWITCHING_PHRASE in ATTENTION.read_text()


def test_attention_file_has_stretch_phrase_verbatim() -> None:
    assert STRETCH_PHRASE in ATTENTION.read_text()


def test_attention_file_does_not_use_minutes_or_percent_as_argument() -> None:
    text = ATTENTION.read_text()
    assert "23 минуты" not in text
    assert "40 %" not in text


def test_fields_file_names_both_new_screen_fields() -> None:
    text = (ROOT / "agents" / "coach-wellbeing" / "fields.md").read_text()
    assert "screen_switches_hour" in text
    assert "screen_stretch_hours" in text
