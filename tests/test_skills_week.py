"""Тексты шага v2.5: ядро coach.md и файлы coach-wellbeing/nutrition/week, allow для review done."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / ".claude"
AGENTS = ROOT / "agents"
ALLOW = json.loads((ROOT / "settings.json").read_text())["permissions"]["allow"]


def coach_text() -> str:
    return (AGENTS / "coach.md").read_text()


def test_coach_week_is_not_empty() -> None:
    path = AGENTS / "coach-week.md"
    assert path.is_file()
    assert path.read_text().strip()


def test_coach_md_points_to_all_side_files() -> None:
    text = coach_text()
    for name in ["coach-wellbeing.md", "coach-nutrition.md", "coach-week.md"]:
        assert name in text


def test_every_cat_agent_file_in_coach_md_exists_and_is_allowed() -> None:
    named = set(re.findall(r"cat (\.claude/agents/[\w.-]+\.md)", coach_text()))
    assert named
    for path in named:
        assert (ROOT.parent / path).is_file(), path
        assert f"Bash(cat {path})" in ALLOW, path


def test_week_file_is_read_by_cat_from_coach_md() -> None:
    assert "cat .claude/agents/coach-week.md" in coach_text()
    assert "Bash(cat .claude/agents/coach-week.md)" in ALLOW


def test_coach_md_has_weekly_review_tool() -> None:
    head = coach_text().split("---")[1]
    assert "mcp__ai-coach__get_weekly_review" in head


def test_week_file_evening_hours_name_the_source() -> None:
    text = (AGENTS / "coach-week.md").read_text()
    assert "работа после 19:00: экран, без него календарь" in text


def test_wellbeing_evening_source_is_screen_then_calendar() -> None:
    text = (AGENTS / "coach-wellbeing.md").read_text()
    assert text.count("экран > календарь") >= 2


def test_week_file_mentions_review_done_and_tool() -> None:
    text = (AGENTS / "coach-week.md").read_text()
    assert "get_weekly_review" in text
    assert "uv run coach review done" in text
    assert "week_review_due" in text


def test_review_done_is_allowed() -> None:
    assert "Bash(uv run coach review done:*)" in ALLOW


def test_coach_md_lists_review_in_bash_commands() -> None:
    assert "review" in coach_text()


# шаг Н29, партия 3: строка замера решений


def decisions_line() -> str:
    lines = (AGENTS / "coach-week.md").read_text().splitlines()
    found = [line for line in lines if "get_decisions" in line]
    assert found
    return found[0]


def test_week_file_has_decisions_line_with_stats_words() -> None:
    text = (AGENTS / "coach-week.md").read_text()
    for word in ["get_decisions", "kept", "missed", "данных мало"]:
        assert word in text


def week_item(number: int) -> str:
    lines = (AGENTS / "coach-week.md").read_text().splitlines()
    found = [line for line in lines if line.startswith(f"{number}. ")]
    assert found
    return found[0]


# шаг Н38, партия 3: усталость и раздражительность в обзоре


def test_week_fields_item_names_fatigue_and_irritability() -> None:
    item = week_item(2)
    assert "`fatigue`" in item
    assert "`irritability`" in item


def test_week_fields_item_names_fatigue_after_stress() -> None:
    item = week_item(2)
    assert item.index("`stress`") < item.index("`fatigue`") < item.index("`irritability`")


def test_week_fields_item_names_scale_direction_of_new_marks() -> None:
    item = week_item(2)
    assert "5 - выжат" in item
    assert "5 - всё бесит" in item


def test_week_conclusions_item_names_burnout_with_fatigue_and_irritability() -> None:
    item = week_item(3)
    sentence = next(s for s in item.split(". ") if "ход к выгоранию" in s)
    assert "fatigue" in sentence
    assert "irritability" in sentence


def test_week_decisions_line_names_threshold_ten() -> None:
    assert re.search(r"\b10\b", decisions_line())


# шаг Н6, партия 2: отклик ночи на нагрузку в обзоре недели

RECOVERY_CAT = "cat .claude/agents/coach-wellbeing/recovery.md"


def recovery_text() -> str:
    return (AGENTS / "coach-wellbeing" / "recovery.md").read_text()


def test_recovery_side_file_exists_and_is_not_empty() -> None:
    assert recovery_text().strip()


def test_recovery_side_file_is_allowed_to_cat() -> None:
    assert f"Bash({RECOVERY_CAT})" in ALLOW


def test_week_file_points_to_recovery_side_file() -> None:
    assert RECOVERY_CAT in (AGENTS / "coach-week.md").read_text()


def test_week_file_names_recovery_key() -> None:
    assert "`recovery`" in week_item(3)


def test_recovery_side_file_names_key_and_factors() -> None:
    text = recovery_text()
    for needle in ("`recovery`", "evening_work", "claude_evening", "heavy_day", "`enough`"):
        assert needle in text, needle


def test_recovery_side_file_says_observation_not_cause() -> None:
    assert "наблюдение, не причина" in recovery_text()


def test_recovery_side_file_says_few_data_with_threshold_ten() -> None:
    text = recovery_text()
    assert "данных мало" in text
    assert re.search(r"\b10\b", text)


def test_recovery_side_file_requires_night_count_with_value() -> None:
    assert "ночей" in recovery_text()


def test_recovery_ready_line_follows_r6b_template() -> None:
    pattern = (
        r"После рабочих вечеров \(N ночей против M спокойных\): HRV ниже на X мс, "
        r"пульс покоя выше на Y, сон короче на Z мин - наблюдение, не причина\."
    )
    text = recovery_text()
    assert re.search(pattern, text)
    assert "своих не подставляй" in text


def test_recovery_few_data_line_follows_r6b_template() -> None:
    pattern = r"Отклик на рабочие вечера: данных мало \(N ночей из 10\)\."
    assert re.search(pattern, recovery_text())


def test_recovery_templates_have_no_digits_instead_of_letters() -> None:
    text = recovery_text()
    for bad in (r"\d+ ночей против", r"на \d+ мс", r"\d+ ночей из 10"):
        assert not re.search(bad, text), bad


def test_recovery_says_line_per_factor_up_to_three() -> None:
    text = recovery_text()
    assert "По строке на фактор" in text
    assert "не больше трёх" in text
    assert "одной строкой" not in text
    assert "одна строка на все" not in text


def test_recovery_names_difference_only_when_enough() -> None:
    assert "только у фактора с `enough` = true" in recovery_text()


def test_recovery_keeps_question_and_evening_trial() -> None:
    text = recovery_text()
    assert "замечает ли это сам" in text
    assert "освободить вечер как пробу" in text
    assert "План и черновики по одной разнице не меняй" in text
    assert "Советов и изменений плана по одной разнице нет" not in text


def test_recovery_allows_direct_question_with_one_call() -> None:
    text = recovery_text()
    assert "прямой вопрос" in text
    assert "`get_weekly_review`" in text
    assert "только в недельном обзоре" not in text
    assert "строка только о нём" not in text


def test_recovery_confounders_do_not_name_sleep() -> None:
    text = recovery_text()
    assert "сон, погода и болезнь" not in text
    assert "время года" in text


# шаг Н7, партия 2: отдых и выходные

REST_CAT = "cat .claude/agents/coach-wellbeing/rest.md"
REST_PHRASE = (
    "Без полного выходного N дней (порог 7). Отдых - часть роста, не простой: "
    "предлагаю один день без работы в ближайшие выходные - поставить в календарь?"
)


def rest_text() -> str:
    return (AGENTS / "coach-wellbeing" / "rest.md").read_text()


def test_rest_side_file_exists_and_is_not_empty() -> None:
    assert rest_text().strip()


def test_rest_side_file_is_allowed_to_cat() -> None:
    assert f"Bash({REST_CAT})" in ALLOW


def test_wellbeing_names_no_day_off_and_points_to_rest_file() -> None:
    text = (AGENTS / "coach-wellbeing.md").read_text()
    assert "no_day_off" in text
    assert REST_CAT in text


def test_wellbeing_says_weekend_work_and_no_day_off_are_one_signal() -> None:
    text = (AGENTS / "coach-wellbeing.md").read_text()
    line = next(ln for ln in text.splitlines() if "weekend_work" in ln and "no_day_off" in ln)
    assert "один сигнал" in line


def test_rest_side_file_has_sample_phrase_verbatim() -> None:
    assert REST_PHRASE in rest_text()


def test_rest_side_file_pair_gives_one_offer_day_without_work() -> None:
    assert "день без работы, про полдня выходных не говори" in rest_text()


def test_rest_side_file_names_signal_and_week_fields() -> None:
    text = rest_text()
    for needle in ("no_day_off", "rest_hours", "rest_days", "days_off"):
        assert needle in text, needle


def test_week_file_names_three_rest_fields_in_fields_item() -> None:
    item = week_item(2)
    for needle in ("`rest_hours`", "`rest_days`", "`days_off`"):
        assert needle in item, needle


def test_week_file_says_few_data_with_count_out_of_four() -> None:
    text = (AGENTS / "coach-week.md").read_text()
    assert "данных мало (N дней из 4)" in text


def test_week_file_points_to_rest_side_file() -> None:
    assert REST_CAT in week_item(3)


# шаг Н51, партия 1: хвост шага 5 вынесен в coach-week/done.md

DONE_CAT = "cat .claude/agents/coach-week/done.md"


def done_text() -> str:
    return (AGENTS / "coach-week" / "done.md").read_text()


def test_done_side_file_names_week_option_and_four_am() -> None:
    text = done_text()
    for needle in ("--week", "04:00"):
        assert needle in text, needle


def test_week_item_5_keeps_review_done_command() -> None:
    assert "uv run coach review done" in week_item(5)


def test_week_item_5_points_to_done_side_file() -> None:
    assert DONE_CAT in week_item(5)


def test_done_side_file_is_allowed_to_cat() -> None:
    assert f"Bash({DONE_CAT})" in ALLOW
