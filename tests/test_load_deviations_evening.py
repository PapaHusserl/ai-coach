"""find_deviations учитывает вечерние оценки: mood <= MOOD_MAX (2), stress >= STRESS_MIN (4)."""

from typing import Any

import pytest

from ai_coach.load import deviations
from ai_coach.load.deviations import find_deviations


def kinds(wellbeing: Any) -> list[str]:
    return [d["kind"] for d in find_deviations(wellbeing, None, None)]


def mark(**fields: Any) -> dict[str, Any]:
    return {"score": 4, "mood": None, "stress": None} | fields


def test_thresholds_are_module_constants() -> None:
    assert deviations.MOOD_MAX == 2
    assert deviations.STRESS_MIN == 4


@pytest.mark.parametrize("mood", [1, 2])
def test_low_mood_is_a_deviation(mood: int) -> None:
    assert kinds(mark(mood=mood)) == ["mood"]


def test_mood_3_is_fine() -> None:
    assert kinds(mark(mood=3)) == []


@pytest.mark.parametrize("stress", [4, 5])
def test_high_stress_is_a_deviation(stress: int) -> None:
    assert kinds(mark(stress=stress)) == ["stress"]


def test_stress_3_is_fine() -> None:
    assert kinds(mark(stress=3)) == []


def test_empty_mood_and_stress_are_fine() -> None:
    assert kinds(mark()) == []


def test_old_style_mark_without_mood_keys_still_works() -> None:
    assert kinds({"score": 2}) == ["wellbeing"]


def test_all_three_at_once() -> None:
    assert sorted(kinds(mark(score=1, mood=1, stress=5))) == ["mood", "stress", "wellbeing"]


def test_deviation_has_value_and_limit() -> None:
    found = find_deviations(mark(mood=1, stress=5), None, None)
    by_kind = {d["kind"]: d for d in found}
    assert (by_kind["mood"]["value"], by_kind["mood"]["limit"]) == (1, 2)
    assert (by_kind["stress"]["value"], by_kind["stress"]["limit"]) == (5, 4)


# Н38, партия 2: усталость и раздражительность (Р5 = 2, порог 4 и выше).
def test_fatigue_and_irritability_thresholds_are_module_constants() -> None:
    assert deviations.FATIGUE_MIN == 4
    assert deviations.IRRITABILITY_MIN == 4


@pytest.mark.parametrize("fatigue", [4, 5])
def test_high_fatigue_is_a_deviation_row(fatigue: int) -> None:
    found = find_deviations(mark(fatigue=fatigue), None, None)
    assert found == [{"kind": "fatigue", "value": fatigue, "limit": 4}]


@pytest.mark.parametrize("irritability", [4, 5])
def test_high_irritability_is_a_deviation_row(irritability: int) -> None:
    found = find_deviations(mark(irritability=irritability), None, None)
    assert found == [{"kind": "irritability", "value": irritability, "limit": 4}]


def test_fatigue_3_is_fine() -> None:
    assert kinds(mark(fatigue=3)) == []


def test_irritability_3_is_fine() -> None:
    assert kinds(mark(irritability=3)) == []


def test_empty_fatigue_and_irritability_are_fine() -> None:
    assert kinds(mark(fatigue=None, irritability=None)) == []


def test_low_wellbeing_row_has_exact_value_and_limit() -> None:
    assert find_deviations(mark(score=2), None, None) == [
        {"kind": "wellbeing", "value": 2, "limit": 2}
    ]


def test_stress_row_at_threshold_has_exact_value_and_limit() -> None:
    assert find_deviations(mark(stress=4), None, None) == [
        {"kind": "stress", "value": 4, "limit": 4}
    ]


def full_mark(logged_at: str, **fields: Any) -> dict[str, Any]:
    base = {"score": 4, "mood": None, "stress": None, "text": None, "logged_at": logged_at}
    return base | fields


def test_main_wellbeing_takes_last_given_fatigue() -> None:
    marks = [
        full_mark("08:00", fatigue=None),
        full_mark("20:00", fatigue=4),
        full_mark("21:00", fatigue=None),
    ]
    main = deviations.main_wellbeing(marks)
    assert main is not None
    assert main["fatigue"] == 4


def test_main_wellbeing_takes_last_given_irritability() -> None:
    marks = [
        full_mark("20:00", irritability=2),
        full_mark("21:00", irritability=None),
    ]
    main = deviations.main_wellbeing(marks)
    assert main is not None
    assert main["irritability"] == 2


def test_main_wellbeing_without_given_fatigue_has_none() -> None:
    main = deviations.main_wellbeing([full_mark("08:00", fatigue=None, irritability=None)])
    assert main is not None
    assert (main["fatigue"], main["irritability"]) == (None, None)


def test_main_wellbeing_survives_marks_without_new_keys() -> None:
    main = deviations.main_wellbeing([full_mark("08:00"), full_mark("20:00", mood=3)])
    assert main is not None
    assert main["mood"] == 3
