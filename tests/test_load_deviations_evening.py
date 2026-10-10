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
