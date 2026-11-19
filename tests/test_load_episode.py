"""Серия болезни по дням (Н33, партия 2а): sick_days(texts, recorded) -> признаки по датам,
episode_state(days, flags, today) -> фаза (ill / rest / return / None), счёт чистых дней,
потолок покоя.

Сигнатуры - «Партии» п. 2а, «Сигнатуры и границы»:
texts - {дата: фразы дня (записи и ответы форм)}, recorded - даты со строкой журнала самочувствия,
days - результат sick_days, flags - {дата: результат day_flags}, today - дата ISO."""

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

import pytest

START = date(2026, 11, 1)

# токен дня -> (тексты, есть строка журнала, {"out": флаг коридора})
TOKENS: dict[str, tuple[list[str], bool, bool | None]] = {
    "sick": (["температура 38"], True, False),
    "mild": (["кашель"], True, False),
    "clean": ([], True, False),
    "norec": ([], False, False),
    "nonight": ([], True, None),
    "corr": ([], True, True),
    "empty": ([], False, None),
    "norec_corr": ([], False, True),
    "formonly": (["хорошо"], False, False),
}


def day(index: int) -> str:
    return (START + timedelta(days=index)).isoformat()


def run(tokens: list[str]) -> dict[str, Any]:
    """Последний токен - сегодня."""
    from ai_coach.load.episode import episode_state, sick_days

    texts = {day(i): list(TOKENS[t][0]) for i, t in enumerate(tokens) if TOKENS[t][0]}
    recorded = {day(i) for i, t in enumerate(tokens) if TOKENS[t][1]}
    flags = {day(i): {"out": TOKENS[t][2]} for i, t in enumerate(tokens)}
    return episode_state(sick_days(texts, recorded), flags, day(len(tokens) - 1))


def test_sick_days_symptoms_fever_severe_record() -> None:
    from ai_coach.load.episode import sick_days

    found = sick_days({"2026-11-01": ["горло болит, температура 37,0"]}, {"2026-11-01"})[
        "2026-11-01"
    ]
    assert found["record"] is True
    assert "горло" in found["symptoms"]
    assert found["fever"] == 37.0
    assert found["severe"] is True


def test_sick_days_fever_below_limit_not_severe() -> None:
    from ai_coach.load.episode import sick_days

    found = sick_days({"2026-11-01": ["температура 36,9"]}, {"2026-11-01"})["2026-11-01"]
    assert found["fever"] is None
    assert found["severe"] is False


@pytest.mark.parametrize("text", ["ломота", "озноб"])
def test_sick_days_body_ache_and_chills_are_severe(text: str) -> None:
    from ai_coach.load.episode import sick_days

    assert sick_days({"2026-11-01": [text]}, {"2026-11-01"})["2026-11-01"]["severe"] is True


def test_sick_days_cough_not_severe() -> None:
    from ai_coach.load.episode import sick_days

    found = sick_days({"2026-11-01": ["кашель"]}, {"2026-11-01"})["2026-11-01"]
    assert found["symptoms"] == ["кашель"]
    assert found["severe"] is False


def test_sick_days_record_without_text_is_clean_record() -> None:
    from ai_coach.load.episode import sick_days

    found = sick_days({}, {"2026-11-01"})["2026-11-01"]
    assert found["record"] is True
    assert found["symptoms"] == []
    assert found["fever"] is None


def test_sick_days_form_answer_without_journal_row_is_not_record() -> None:
    from ai_coach.load.episode import sick_days

    assert sick_days({"2026-11-01": ["хорошо"]}, set())["2026-11-01"]["record"] is False


def test_mild_series_opens_no_phase() -> None:
    assert run(["mild", "mild"])["phase"] is None


def test_mild_series_then_clean_days_no_phase() -> None:
    assert run(["mild", "mild", "clean", "clean", "clean"])["phase"] is None


def test_fever_at_limit_opens_ill() -> None:
    from ai_coach.load.episode import episode_state, sick_days

    days = sick_days({day(0): ["температура 37,0"]}, {day(0)})
    assert episode_state(days, {day(0): {"out": False}}, day(0))["phase"] == "ill"


def test_fever_below_limit_no_phase() -> None:
    from ai_coach.load.episode import episode_state, sick_days

    days = sick_days({day(0): ["температура 36,9"]}, {day(0)})
    assert episode_state(days, {day(0): {"out": False}}, day(0))["phase"] is None


@pytest.mark.parametrize("text", ["ломота", "озноб"])
def test_body_ache_or_chills_open_ill(text: str) -> None:
    from ai_coach.load.episode import episode_state, sick_days

    days = sick_days({day(0): [text]}, {day(0)})
    assert episode_state(days, {day(0): {"out": False}}, day(0))["phase"] == "ill"


def test_ill_state_severe_and_bounds() -> None:
    state = run(["sick"])
    assert state["severe"] is True
    assert state["sick_first"] == day(0)
    assert state["sick_last"] == day(0)


@pytest.mark.parametrize(
    ("clean_days", "phase", "rest_day", "return_day"),
    [
        (1, "rest", 1, None),
        (2, "rest", 2, None),
        (3, "return", None, 1),
        (9, "return", None, 7),
        (10, None, None, None),
    ],
)
def test_ladder_after_severe_series(
    clean_days: int, phase: str | None, rest_day: int | None, return_day: int | None
) -> None:
    state = run(["sick", *["clean"] * clean_days])
    assert (state["phase"], state["rest_day"], state["return_day"]) == (phase, rest_day, return_day)


def test_covid_word_same_ladder_no_covid_field() -> None:
    from ai_coach.load.episode import episode_state, sick_days

    days = sick_days({day(0): ["ковид, температура 38"]}, {day(i) for i in range(4)})
    flags = {day(i): {"out": False} for i in range(4)}
    state = episode_state(days, flags, day(3))
    assert (state["phase"], state["return_day"]) == ("return", 1)
    assert "covid" not in state


def test_series_gap_of_one_day_joins() -> None:
    state = run(["mild", "clean", "sick"])
    assert state["phase"] == "ill"
    assert state["sick_first"] == day(0)
    assert state["sick_last"] == day(2)


def test_series_gap_of_two_days_splits() -> None:
    state = run(["mild", "clean", "clean", "sick"])
    assert state["sick_first"] == day(3)


def test_mild_day_after_one_clean_day_continues_ill() -> None:
    assert run(["sick", "clean", "mild"])["phase"] == "ill"


def test_new_symptom_in_return_is_ill_again() -> None:
    assert run(["sick", "clean", "clean", "mild"])["phase"] == "ill"


def test_clean_day_counts() -> None:
    assert run(["sick", "clean"])["clean_days"] == 1


def test_two_clean_days_count_two() -> None:
    assert run(["sick", "clean", "clean"])["clean_days"] == 2


def test_clean_day_not_clean_codes_empty() -> None:
    assert run(["sick", "clean"])["not_clean"] == []


def test_no_record_day_not_clean() -> None:
    state = run(["sick", "norec", "clean"])
    assert state["clean_days"] == 1
    assert state["not_clean"] == []


def test_today_without_record_waits_keeps_count_and_reports_reason() -> None:
    state = run(["sick", "clean", "norec"])
    assert state["clean_days"] == 1
    assert state["not_clean"] == ["no_record"]
    assert state["phase"] == "rest"


def test_past_day_without_record_resets_count() -> None:
    assert run(["sick", "clean", "norec", "norec"])["clean_days"] == 0


def test_clean_norec_clean_counts_one_not_two() -> None:
    assert run(["sick", "clean", "norec", "clean"])["clean_days"] == 1


def test_form_answer_without_journal_row_is_no_record() -> None:
    assert run(["sick", "clean", "formonly"])["not_clean"] == ["no_record"]


def test_today_without_night_waits_reports_no_night() -> None:
    state = run(["sick", "clean", "nonight"])
    assert state["clean_days"] == 1
    assert state["not_clean"] == ["no_night"]
    assert state["phase"] == "rest"


def test_clean_nonight_clean_counts_one_not_two() -> None:
    assert run(["sick", "clean", "nonight", "clean"])["clean_days"] == 1


def test_day_out_of_corridor_resets_count() -> None:
    state = run(["sick", "clean", "corr"])
    assert state["clean_days"] == 0
    assert state["not_clean"] == ["corridor"]
    assert state["phase"] == "rest"


def test_cap_two_clean_days_return_on_third_not_by_cap() -> None:
    state = run(["sick", "clean", "clean", "clean"])
    assert (state["phase"], state["return_day"], state["by_cap"]) == ("return", 1, False)


def test_cap_clean_dirty_clean_third_day_still_rest() -> None:
    state = run(["sick", "clean", "corr", "clean"])
    assert (state["phase"], state["rest_day"]) == ("rest", 3)


def test_cap_clean_dirty_clean_returns_on_fourth_by_cap() -> None:
    state = run(["sick", "clean", "corr", "clean", "clean"])
    assert (state["phase"], state["return_day"], state["by_cap"]) == ("return", 1, True)


def test_cap_three_dirty_days_third_still_rest() -> None:
    assert run(["sick", "corr", "corr", "corr"])["phase"] == "rest"


def test_cap_three_dirty_days_return_on_fourth_by_cap() -> None:
    state = run(["sick", "corr", "corr", "corr", "corr"])
    assert (state["phase"], state["return_day"], state["by_cap"]) == ("return", 1, True)


def test_cap_dirty_clean_clean_returns_on_fourth_not_by_cap() -> None:
    state = run(["sick", "corr", "clean", "clean", "clean"])
    assert (state["phase"], state["return_day"], state["by_cap"]) == ("return", 1, False)


def test_cap_fourth_day_without_record_and_night_still_return() -> None:
    state = run(["sick", "corr", "corr", "corr", "empty"])
    assert (state["phase"], state["return_day"], state["by_cap"]) == ("return", 1, True)


def test_cap_symptom_on_fourth_day_is_ill() -> None:
    assert run(["sick", "corr", "corr", "corr", "mild"])["phase"] == "ill"


def test_cap_return_lasts_seven_days() -> None:
    state = run(["sick", "corr", "corr", "corr", *["clean"] * 7])
    assert (state["phase"], state["return_day"]) == ("return", 7)


def test_cap_return_ends_after_seven_days() -> None:
    assert run(["sick", "corr", "corr", "corr", *["clean"] * 8])["phase"] is None


def test_return_ignores_day_out_of_corridor() -> None:
    state = run(["sick", "clean", "clean", "clean", "corr"])
    assert (state["phase"], state["return_day"]) == ("return", 2)


@pytest.mark.parametrize(
    ("tokens", "step"),
    [
        (["sick", "clean"], 1),
        (["sick", "clean", "clean"], 2),
        (["sick", "corr", "clean"], 1),
        (["sick", "clean", "corr", "clean"], 1),
        (["sick", "corr", "clean", "clean"], 2),
        (["sick", "corr", "corr", "clean"], 1),
    ],
)
def test_rest_step_counts_clean_days_before_today_plus_one(tokens: list[str], step: int) -> None:
    assert run(tokens)["rest_step"] == step


def test_rest_step_today_out_of_corridor_after_clean_day() -> None:
    state = run(["sick", "clean", "corr"])
    assert (state["clean_days"], state["rest_step"]) == (0, 2)


@pytest.mark.parametrize(
    "tokens",
    [["sick"], ["sick", "clean", "clean", "clean"], ["mild"]],
    ids=["ill", "return", "none"],
)
def test_rest_step_none_outside_rest(tokens: list[str]) -> None:
    assert run(tokens)["rest_step"] is None


@pytest.mark.parametrize("clean_days", [3, 9])
def test_until_is_last_ladder_day_same_on_first_and_last_day(clean_days: int) -> None:
    assert run(["sick", *["clean"] * clean_days])["until"] == day(9)


def test_until_by_cap_is_one_day_later() -> None:
    assert run(["sick", "corr", "corr", "corr", "corr"])["until"] == day(10)


@pytest.mark.parametrize(
    "tokens", [["sick", "clean"], ["sick"], ["mild"]], ids=["rest", "ill", "none"]
)
def test_until_none_outside_return(tokens: list[str]) -> None:
    assert run(tokens)["until"] is None


def test_today_without_record_and_out_of_corridor_reports_both() -> None:
    state = run(["sick", "clean", "norec_corr"])
    assert state["not_clean"] == ["no_record", "corridor"]
    assert state["clean_days"] == 0


def test_window_severe_day_at_today_minus_20_counts() -> None:
    state = run(["sick", *["mild"] * 20])
    assert (state["severe"], state["phase"]) == (True, "ill")


def test_window_severe_day_at_today_minus_21_not_seen() -> None:
    state = run(["sick", *["mild"] * 21])
    assert (state["severe"], state["phase"]) == (False, None)


def test_state_has_all_eleven_keys_without_illness() -> None:
    assert set(run(["clean"])) == {
        "phase",
        "severe",
        "sick_first",
        "sick_last",
        "clean_days",
        "rest_day",
        "rest_step",
        "return_day",
        "until",
        "by_cap",
        "not_clean",
    }


def test_no_illness_values_are_empty() -> None:
    state = run(["clean"])
    assert (state["phase"], state["sick_first"], state["sick_last"]) == (None, None, None)
    assert (state["severe"], state["by_cap"], state["clean_days"], state["not_clean"]) == (
        False,
        False,
        0,
        [],
    )


def test_mild_series_keeps_bounds_without_phase() -> None:
    state = run(["mild", "mild"])
    assert (state["sick_first"], state["sick_last"]) == (day(0), day(1))
    assert (state["severe"], state["phase"]) == (False, None)


def test_sick_days_symptom_from_phrase_without_journal_row() -> None:
    from ai_coach.load.episode import sick_days

    found = sick_days({"2026-11-01": ["кашель"]}, set())["2026-11-01"]
    assert found["record"] is False
    assert found["symptoms"] == ["кашель"]


def test_symptom_in_return_continues_series_from_severe_day() -> None:
    state = run(["sick", *["clean"] * 4, "mild"])
    assert (state["phase"], state["sick_first"], state["severe"]) == ("ill", day(0), True)


def test_after_symptom_in_return_rest_starts_again() -> None:
    state = run(["sick", *["clean"] * 4, "mild", "clean"])
    assert (state["phase"], state["rest_day"]) == ("rest", 1)


def test_symptom_right_after_return_ended_is_new_mild_series() -> None:
    state = run(["sick", *["clean"] * 9, "mild"])
    assert (state["phase"], state["sick_first"], state["severe"]) == (None, day(10), False)


def test_symptom_in_rest_after_gap_continues_ill() -> None:
    state = run(["sick", "corr", "clean", "mild"])
    assert (state["phase"], state["sick_first"]) == ("ill", day(0))


def test_symptom_after_today_is_ignored() -> None:
    from ai_coach.load.episode import episode_state, sick_days

    days = sick_days({day(1): ["кашель"]}, {day(0), day(1)})
    state = episode_state(days, {day(0): {"out": False}, day(1): {"out": False}}, day(0))
    assert (state["phase"], state["sick_first"], state["sick_last"]) == (None, None, None)


def test_day_without_flags_is_no_night() -> None:
    from ai_coach.load.episode import episode_state, sick_days

    days = sick_days({day(0): ["температура 38"]}, {day(0), day(1)})
    state = episode_state(days, {day(0): {"out": False}}, day(1))
    assert state["not_clean"] == ["no_night"]


def test_symptom_after_phase_ended_is_new_mild_series() -> None:
    state = run(["sick", *["clean"] * 10, "mild"])
    assert (state["phase"], state["sick_first"], state["severe"]) == (None, day(11), False)


# --- Н33, партия 3: серия статуса HRV, метрики ночи ---


def statuses_of(*values: str | None) -> dict[str, str | None]:
    """Статусы по дням: последний - сегодня day(len - 1)."""
    return {day(i): value for i, value in enumerate(values)}


def streak(*values: str | None) -> int:
    from ai_coach.load.episode import status_streak

    return status_streak(statuses_of(*values), day(len(values) - 1))


def test_status_streak_empty_is_zero() -> None:
    from ai_coach.load.episode import status_streak

    assert status_streak({}, day(0)) == 0


@pytest.mark.parametrize("status", ["LOW", "UNBALANCED", "BELOW"])
def test_status_streak_each_bad_status_counts(status: str) -> None:
    assert streak(status) == 1


def test_status_streak_counts_days_back_from_today() -> None:
    assert streak("LOW", "UNBALANCED", "BELOW") == 3


def test_status_streak_lowercase_counts() -> None:
    assert streak("unbalanced", "Low") == 2


@pytest.mark.parametrize("today", [None, "BALANCED", "POOR", "IN_RANGE"])
def test_status_streak_today_not_bad_is_zero_after_bad_days(today: str | None) -> None:
    assert streak("LOW", "LOW", today) == 0


@pytest.mark.parametrize("middle", [None, "BALANCED", "POOR", "IN_RANGE"])
def test_status_streak_broken_by_not_bad_day(middle: str | None) -> None:
    assert streak("LOW", middle, "LOW", "LOW") == 2


def test_status_streak_broken_by_missing_date() -> None:
    from ai_coach.load.episode import status_streak

    found = {day(0): "LOW", day(2): "LOW", day(3): "LOW"}
    assert status_streak(found, day(3)) == 2


def vitals(row: dict[str, Any], skin: float | None = 1.0, resp: float | None = 15.0) -> dict:
    from ai_coach.load.episode import vitals_flags

    return vitals_flags(row, skin, resp)


@pytest.mark.parametrize(
    ("key", "value", "flag"),
    [
        ("skin_temp", 1.0, False),
        ("skin_temp", 1.1, True),
        ("skin_temp", 0.0, False),
        ("respiration", 15.0, False),
        ("respiration", 15.1, True),
        ("respiration", 10.0, False),
    ],
)
def test_vitals_flags_corridor_metric_edge(key: str, value: float, flag: bool) -> None:
    """Границы: кожа 1.0, дыхание 15.0 (значения по умолчанию помощника)."""
    assert vitals({key: value})[key] is flag


def test_vitals_flags_skin_without_edge_is_none() -> None:
    assert vitals({"skin_temp": 5.0}, skin=None)["skin_temp"] is None


def test_vitals_flags_respiration_without_edge_is_none() -> None:
    assert vitals({"respiration": 30.0}, resp=None)["respiration"] is None


def test_vitals_flags_skin_without_value_is_none() -> None:
    assert vitals({"skin_temp": None})["skin_temp"] is None


def test_vitals_flags_respiration_without_value_is_none() -> None:
    assert vitals({"respiration": None})["respiration"] is None


def test_vitals_flags_spo2_92_is_not_flag() -> None:
    assert vitals({"spo2": 92})["spo2"] is False


def test_vitals_flags_spo2_below_92_is_flag() -> None:
    assert vitals({"spo2": 91.9})["spo2"] is True


def test_vitals_flags_spo2_high_is_not_flag() -> None:
    assert vitals({"spo2": 98})["spo2"] is False


def test_vitals_flags_spo2_needs_no_edge() -> None:
    assert vitals({"spo2": 80}, skin=None, resp=None)["spo2"] is True


def test_vitals_flags_spo2_without_value_is_none() -> None:
    assert vitals({"spo2": None})["spo2"] is None


def test_vitals_flags_row_without_keys_is_three_none() -> None:
    assert vitals({}) == {"skin_temp": None, "respiration": None, "spo2": None}


def test_vitals_flags_metrics_are_independent() -> None:
    found = vitals({"skin_temp": None, "respiration": 16.0, "spo2": 90})
    assert found == {"skin_temp": None, "respiration": True, "spo2": True}


def rest_state(
    today_flags: Mapping[str, bool | None], *, record: bool = True, clean_yesterday: bool = False
) -> dict[str, Any]:
    """Тяжёлый день day(0); вчерашний день покоя чистый или нет; сегодня day(2) с флагами."""
    from ai_coach.load.episode import episode_state, sick_days

    recorded = {day(0), day(1)} | ({day(2)} if record else set())
    days = sick_days({day(0): ["температура 38"]}, recorded)
    flags = {
        day(0): {"out": False},
        day(1): {"out": not clean_yesterday},
        day(2): today_flags,
    }
    return episode_state(days, flags, day(2))


def test_metric_flag_true_gives_its_reason() -> None:
    from ai_coach.load.episode import episode_state, sick_days

    days = sick_days({day(0): ["температура 38"]}, {day(0), day(1)})
    state = episode_state(days, {day(1): {"out": False, "spo2": True}}, day(1))
    assert state["not_clean"] == ["spo2"]


@pytest.mark.parametrize("value", [None, False])
def test_metric_flag_none_or_false_is_clean(value: bool | None) -> None:
    state = rest_state({"out": False, "spo2": value, "skin_temp": value, "respiration": value})
    assert state["not_clean"] == []


def test_metric_reason_without_night_comes_after_no_night() -> None:
    state = rest_state({"out": None, "spo2": True})
    assert state["not_clean"] == ["no_night", "spo2"]


def test_all_reasons_keep_order() -> None:
    flags = {"out": True, "skin_temp": True, "respiration": True, "spo2": True}
    state = rest_state(flags, record=False)
    assert state["not_clean"] == ["no_record", "corridor", "skin_temp", "respiration", "spo2"]


@pytest.mark.parametrize("metric", ["skin_temp", "respiration", "spo2"])
def test_today_with_metric_out_after_clean_day_does_not_wait(metric: str) -> None:
    state = rest_state({"out": False, metric: True}, clean_yesterday=True)
    assert (state["clean_days"], state["rest_step"]) == (0, 2)


def test_today_without_record_and_metrics_in_norm_waits() -> None:
    flags = {"out": False, "skin_temp": False, "respiration": False, "spo2": False}
    state = rest_state(flags, record=False, clean_yesterday=True)
    assert (state["clean_days"], state["not_clean"]) == (1, ["no_record"])


def test_today_without_record_and_without_night_waits() -> None:
    state = rest_state({"out": None}, record=False, clean_yesterday=True)
    assert (state["clean_days"], state["not_clean"]) == (1, ["no_record", "no_night"])


def test_past_rest_day_with_metric_out_breaks_the_count() -> None:
    from ai_coach.load.episode import episode_state, sick_days

    days = sick_days({day(0): ["температура 38"]}, {day(0), day(1), day(2), day(3)})
    flags = {
        day(1): {"out": False},
        day(2): {"out": False, "respiration": True},
        day(3): {"out": False},
    }
    state = episode_state(days, flags, day(3))
    assert (state["phase"], state["rest_step"]) == ("rest", 1)
