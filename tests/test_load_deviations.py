"""Пороги плохого восстановления: константы модуля ai_coach.load.deviations и
find_deviations(wellbeing, metrics, load) -> список {"kind", ...}; None — данных нет."""

from collections.abc import Sequence
from typing import Any

import pytest

from ai_coach.load import deviations
from ai_coach.load.deviations import find_deviations

HOUR = 3600


def metrics(**values: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"readiness_score": None, "hrv_status": None, "sleep_seconds": None}
    return {**row, **values}


def kinds(wellbeing: Any = None, day: Any = None, load: Any = None) -> list[str]:
    return [d["kind"] for d in find_deviations(wellbeing, day, load)]


def test_thresholds_are_module_constants() -> None:
    assert deviations.WELLBEING_MAX == 2
    assert deviations.READINESS_MIN == 33
    assert deviations.ATL_OVER_CTL_MAX == 15
    assert deviations.SLEEP_MIN_HOURS == 6
    assert set(deviations.BAD_HRV_STATUSES) == {"LOW", "UNBALANCED", "BELOW"}


def test_no_data_no_deviations() -> None:
    assert find_deviations(None, None, None) == []


def test_empty_metrics_no_deviations() -> None:
    assert kinds(day=metrics()) == []


def test_good_day_has_no_deviations() -> None:
    day = metrics(readiness_score=70, hrv_status="BALANCED", sleep_seconds=8 * HOUR)
    assert kinds({"score": 4}, day, {"atl": 50, "ctl": 45}) == []


@pytest.mark.parametrize("score", [1, 2])
def test_low_wellbeing_is_a_deviation(score: int) -> None:
    assert kinds({"score": score}) == ["wellbeing"]


def test_wellbeing_3_is_fine() -> None:
    assert kinds({"score": 3}) == []


def test_readiness_32_is_a_deviation_33_is_fine() -> None:
    assert kinds(day=metrics(readiness_score=32)) == ["readiness"]
    assert kinds(day=metrics(readiness_score=33)) == []


@pytest.mark.parametrize("status", ["LOW", "UNBALANCED", "BELOW", "below"])
def test_bad_hrv_status_is_a_deviation(status: str) -> None:
    assert kinds(day=metrics(hrv_status=status)) == ["hrv"]


@pytest.mark.parametrize("status", ["BALANCED", "POOR", "NO_STATUS", "IN_RANGE", "ABOVE"])
def test_other_hrv_status_is_fine(status: str) -> None:
    assert kinds(day=metrics(hrv_status=status)) == []


def test_atl_minus_ctl_over_15_is_a_deviation() -> None:
    assert kinds(load={"atl": 65.5, "ctl": 50}) == ["atl_over_ctl"]


def test_atl_minus_ctl_exactly_15_is_fine() -> None:
    assert kinds(load={"atl": 65, "ctl": 50}) == []


def test_ctl_above_atl_is_fine() -> None:
    assert kinds(load={"atl": 10, "ctl": 50}) == []


def test_sleep_under_6_hours_is_a_deviation() -> None:
    assert kinds(day=metrics(sleep_seconds=6 * HOUR - 1)) == ["sleep"]


def test_sleep_exactly_6_hours_is_fine() -> None:
    assert kinds(day=metrics(sleep_seconds=6 * HOUR)) == []


def test_several_deviations_are_all_reported() -> None:
    day = metrics(readiness_score=10, sleep_seconds=4 * HOUR)
    assert sorted(kinds({"score": 1}, day)) == ["readiness", "sleep", "wellbeing"]


# Н31, партия 1: слова-симптомы в тексте самочувствия.


def symptoms(texts: Any) -> list[str]:
    from ai_coach.load.deviations import find_symptoms

    return find_symptoms(texts)


def test_symptoms_go_in_list_order_not_text_order() -> None:
    assert symptoms(["утро: насморк и горло"]) == ["горло", "насморк"]


@pytest.mark.parametrize(
    ("text", "word"),
    [
        ("ГОРЛО", "горло"),
        ("Насморк", "насморк"),
        ("в горле ком", "горло"),
        ("весь в соплях", "сопли"),
        ("с соплями", "сопли"),
        ("температуры нет", "температура"),
        ("кашляю", "кашель"),
        ("кашель", "кашель"),
        ("нос заложен", "заложенность"),
        ("чихаю", "чихание"),
        ("чихнул", "чихание"),
        ("першит", "першение"),
        ("осип", "осиплость"),
        ("охрип", "осиплость"),
        ("знобит", "озноб"),
        ("озноб", "озноб"),
        ("ломит", "ломота"),
        ("ломота", "ломота"),
        ("простыл", "простуда"),
        ("простуда", "простуда"),
    ],
)
def test_symptom_stems_are_found(text: str, word: str) -> None:
    assert word in symptoms([text])


def test_sore_throat_gives_two_words() -> None:
    assert symptoms(["горло першит"]) == ["горло", "першение"]


@pytest.mark.parametrize(
    "text", ["жарко", "жар", "голова болит", "устал", "раздражён", "устал, голова тяжёлая", "каша"]
)
def test_words_outside_the_list_are_not_symptoms(text: str) -> None:
    assert symptoms([text]) == []


def test_same_word_in_two_entries_is_reported_once() -> None:
    assert symptoms(["горло", "опять горло"]) == ["горло"]


def test_no_texts_no_symptoms() -> None:
    assert symptoms([]) == []


def test_symptom_list_has_the_twelve_agreed_words_in_order() -> None:
    text = (
        "простуда ломит знобит осип чихаю першит нос заложен кашель температура сопли насморк горло"
    )
    assert symptoms([text]) == [
        "горло", "насморк", "сопли", "температура", "кашель", "заложенность",
        "чихание", "першение", "осиплость", "озноб", "ломота", "простуда",
    ]  # fmt: skip


@pytest.mark.parametrize("score", [4, 5])
def test_symptom_in_text_is_a_deviation_at_any_score(score: int) -> None:
    found = find_deviations({"score": score, "texts": ["болит горло"]}, None, None)
    assert found == [{"kind": "symptoms", "value": ["горло"], "limit": None}]


def test_symptoms_come_after_wellbeing() -> None:
    assert kinds({"score": 2, "texts": ["горло"]}) == ["wellbeing", "symptoms"]


def test_symptoms_come_after_stress_before_readiness() -> None:
    wellbeing = {"score": 2, "mood": 2, "stress": 5, "texts": ["горло"]}
    day = metrics(readiness_score=10)
    assert kinds(wellbeing, day) == ["wellbeing", "mood", "stress", "symptoms", "readiness"]


def test_wellbeing_without_texts_key_has_no_symptoms() -> None:
    assert kinds({"score": 3}) == []


def test_negation_is_not_parsed_symptom_still_reported() -> None:
    assert kinds({"score": 4, "texts": ["температуры нет"]}) == ["symptoms"]
    assert kinds({"score": 4, "texts": ["горло прошло"]}) == ["symptoms"]


def test_tiredness_and_irritability_are_not_symptoms() -> None:
    assert kinds({"score": 3, "texts": ["устал, всё раздражает"]}) == []


def mark(logged_at: str, text: str | None, **values: Any) -> dict[str, Any]:
    row = {"score": 3, "mood": None, "stress": None, "event_id": None}
    return {**row, "logged_at": logged_at, "text": text, **values}


def test_main_wellbeing_collects_texts_in_time_order() -> None:
    marks = [mark("08:00", "горло"), mark("12:00", None), mark("20:00", "насморк", event_id=5)]
    main = deviations.main_wellbeing(marks)
    assert main is not None
    assert main["texts"] == ["горло", "насморк"]


def test_main_wellbeing_keeps_scores_of_the_last_entry() -> None:
    marks = [
        mark("08:00", "горло", score=2, mood=3),
        mark("20:00", None, score=4, stress=5, event_id=9),
    ]
    main = deviations.main_wellbeing(marks)
    assert main is not None
    assert (main["score"], main["mood"], main["stress"], main["event_id"]) == (4, 3, 5, 9)


# Н31, партия 2: оценка ниже своей нормы (медиана за 14 предыдущих дней).


def norms_of(marks: list[dict[str, Any]]) -> dict[str, Any]:
    from ai_coach.load.deviations import wellbeing_norms

    return wellbeing_norms(marks)


def history(
    scores: Sequence[int], moods: Sequence[int | None] | None = None
) -> list[dict[str, Any]]:
    """По одной записи на день: даты 2026-10-01, 02, ... (прошлые дни)."""
    given: Sequence[int | None] = moods if moods is not None else [None] * len(scores)
    return [
        mark(f"2026-10-{number:02d} 08:00", None, date=f"2026-10-{number:02d}", score=s, mood=m)
        for number, (s, m) in enumerate(zip(scores, given, strict=True), start=1)
    ]


def below(wellbeing: Any, norms: Any) -> list[dict[str, Any]]:
    from ai_coach.load.deviations import find_below

    return find_below(wellbeing, norms)


def test_below_constants_are_module_constants() -> None:
    assert deviations.BELOW_DAYS == 14
    assert deviations.BELOW_MIN_DAYS == 7
    assert deviations.BELOW_DROP == 1


def test_norm_is_median_of_scores() -> None:
    assert norms_of(history([4] * 14)) == {"score": 4}


def test_norm_has_no_mood_key_when_mood_was_never_set() -> None:
    assert "mood" not in norms_of(history([4] * 14))


def test_norm_of_mood_is_median_of_moods() -> None:
    assert norms_of(history([4] * 7, [3] * 7))["mood"] == 3


def test_six_days_are_not_enough_seven_are() -> None:
    assert "score" not in norms_of(history([4] * 6))
    assert norms_of(history([4] * 7)) == {"score": 4}


def test_days_are_counted_separately_for_score_and_mood() -> None:
    norms = norms_of(history([4] * 8, [3, 3, 3, 3, 3, 3, None, None]))
    assert norms["score"] == 4
    assert "mood" not in norms


def test_norm_takes_the_last_score_of_a_day() -> None:
    marks = history([4] * 7)
    marks.insert(0, mark("2026-10-01 07:00", None, date="2026-10-01", score=1))
    assert norms_of(marks) == {"score": 4}


def test_norm_takes_the_last_given_mood_of_a_day() -> None:
    marks = []
    for number in range(1, 8):
        day = f"2026-10-{number:02d}"
        marks.append(mark(f"{day} 08:00", None, date=day, mood=2))
        marks.append(mark(f"{day} 20:00", None, date=day, mood=4))
        marks.append(mark(f"{day} 21:00", None, date=day, mood=None))
    assert norms_of(marks)["mood"] == 4


def test_norm_is_median_not_mean() -> None:
    assert norms_of(history([4] * 9 + [2] * 5))["score"] == 4


def test_norm_of_even_count_is_midpoint() -> None:
    assert norms_of(history([4, 5] * 4))["score"] == 4.5


def test_norm_without_marks_is_empty() -> None:
    assert norms_of([]) == {}


def test_score_one_below_norm_is_below() -> None:
    found = below({"score": 3, "mood": None}, {"score": 4})
    assert found == [{"kind": "wellbeing_below", "value": 3, "limit": 4}]


def test_score_equal_to_norm_is_fine() -> None:
    assert below({"score": 4, "mood": None}, {"score": 4}) == []


def test_score_above_norm_is_fine() -> None:
    assert below({"score": 5, "mood": None}, {"score": 4}) == []


def test_half_a_point_below_is_fine() -> None:
    assert below({"score": 4, "mood": None}, {"score": 4.5}) == []


def test_one_and_a_half_below_is_below() -> None:
    found = below({"score": 3, "mood": None}, {"score": 4.5})
    assert found == [{"kind": "wellbeing_below", "value": 3, "limit": 4.5}]


def test_mood_one_below_norm_is_mood_below() -> None:
    found = below({"score": 4, "mood": 3}, {"score": 4, "mood": 4})
    assert found == [{"kind": "mood_below", "value": 3, "limit": 4}]


def test_mood_none_gives_no_mood_below() -> None:
    assert below({"score": 4, "mood": None}, {"score": 4, "mood": 4}) == []


def test_missing_norm_gives_no_row() -> None:
    assert below({"score": 1, "mood": 1}, {}) == []
    assert below({"score": 3, "mood": 3}, {}) == []


def test_absolute_threshold_wins_over_below_for_score() -> None:
    assert kinds({"score": 2, "mood": None}, None, None) == ["wellbeing"]
    found = find_deviations({"score": 2, "mood": None}, None, None, {"score": 4})
    assert [d["kind"] for d in found] == ["wellbeing"]


def test_absolute_threshold_wins_over_below_for_mood() -> None:
    wellbeing = {"score": 4, "mood": 2}
    found = find_deviations(wellbeing, None, None, {"score": 4, "mood": 4})
    assert [d["kind"] for d in found] == ["mood"]


def test_scores_are_independent_low_score_and_below_mood() -> None:
    wellbeing = {"score": 2, "mood": 3}
    found = find_deviations(wellbeing, None, None, {"score": 4, "mood": 4})
    assert [d["kind"] for d in found] == ["wellbeing", "mood_below"]


def test_both_scores_below_norm_give_two_rows() -> None:
    wellbeing = {"score": 3, "mood": 3}
    found = find_deviations(wellbeing, None, None, {"score": 4, "mood": 4})
    assert [d["kind"] for d in found] == ["wellbeing_below", "mood_below"]


def test_below_rows_go_after_stress_before_symptoms_and_readiness() -> None:
    wellbeing = {"score": 3, "mood": 3, "stress": 5, "texts": ["горло"]}
    found = find_deviations(wellbeing, metrics(readiness_score=10), None, {"score": 4, "mood": 4})
    assert [d["kind"] for d in found] == [
        "stress", "wellbeing_below", "mood_below", "symptoms", "readiness",
    ]  # fmt: skip


def test_low_wellbeing_mood_stress_then_below_rows_in_order() -> None:
    wellbeing = {"score": 2, "mood": 2, "stress": 5}
    found = find_deviations(wellbeing, None, None, {"score": 4, "mood": 4})
    assert [d["kind"] for d in found] == ["wellbeing", "mood", "stress"]


def test_find_deviations_without_norms_is_as_before() -> None:
    assert kinds({"score": 3, "mood": 3}) == []
    assert find_deviations({"score": 3, "mood": 3}, None, None, None) == []


def test_no_wellbeing_with_norms_gives_no_rows() -> None:
    assert find_deviations(None, None, None, {"score": 4, "mood": 4}) == []
