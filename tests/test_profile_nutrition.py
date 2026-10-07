from typing import Any

import pytest

from ai_coach.profile.nutrition import NutritionInput, bmr
from ai_coach.profile.nutrition import nutrition as calc


def nutrition(**fields: Any) -> dict[str, Any]:
    return calc(NutritionInput(**fields))


MAN: dict = {"sex": "m", "age": 35, "height_cm": 180, "weight_kg": 80, "activity_level": "moderate"}
WOMAN: dict = {
    "sex": "f",
    "age": 40,
    "height_cm": 160,
    "weight_kg": 50,
    "activity_level": "sedentary",
}


def kcal_from_macros(result: dict) -> float:
    return 4 * result["protein_g"] + 9 * result["fat_g"] + 4 * result["carbs_g"]


def test_bmr_man() -> None:
    assert bmr("m", 80, 180, 35) == pytest.approx(1755)


def test_bmr_woman_is_161_lower_than_man_formula() -> None:
    assert bmr("f", 80, 180, 35) == pytest.approx(1755 - 166)


def test_result_has_bmr_and_tdee() -> None:
    result = nutrition(**MAN)
    assert result["bmr"] == pytest.approx(1755)
    assert result["tdee_rest"] == pytest.approx(2720, abs=2)


@pytest.mark.parametrize(
    ("level", "factor"),
    [("sedentary", 1.2), ("light", 1.375), ("moderate", 1.55), ("active", 1.725)],
)
def test_activity_factor(level: str, factor: float) -> None:
    result = nutrition(**{**MAN, "activity_level": level})
    assert result["tdee_rest"] == pytest.approx(1755 * factor, abs=2)


def test_today_adds_activity_calories() -> None:
    result = nutrition(**MAN, activity_kcal=500)
    assert result["tdee_today"] == pytest.approx(result["tdee_rest"] + 500, abs=1)


def test_today_equals_rest_without_activity_calories() -> None:
    result = nutrition(**MAN)
    assert result["tdee_today"] == pytest.approx(result["tdee_rest"], abs=1)


def test_keep_target_is_tdee() -> None:
    result = nutrition(**MAN, weight_goal="keep")
    assert result["kcal_target"] == pytest.approx(result["tdee_rest"], abs=2)


def test_lose_target_is_15_to_20_percent_below_tdee() -> None:
    result = nutrition(**MAN, weight_goal="lose")
    assert 0.80 * 2720 - 2 <= result["kcal_target"] <= 0.85 * 2720 + 2


def test_lose_target_is_not_below_bmr() -> None:
    result = nutrition(**WOMAN, weight_goal="lose")
    assert result["bmr"] == pytest.approx(1139)
    assert result["kcal_target"] >= result["bmr"] - 1


def test_gain_target_is_10_percent_above_tdee() -> None:
    result = nutrition(**MAN, weight_goal="gain")
    assert result["kcal_target"] == pytest.approx(2720 * 1.10, abs=3)


def test_weekly_rate_changes_lose_target() -> None:
    slow = nutrition(**MAN, weight_goal="lose", weekly_rate_kg=0.25)
    fast = nutrition(**MAN, weight_goal="lose", weekly_rate_kg=0.75)
    assert slow["kcal_target"] > fast["kcal_target"]


def test_protein_for_keep_is_1_8_per_kg() -> None:
    assert nutrition(**MAN, weight_goal="keep")["protein_g"] == pytest.approx(1.8 * 80, abs=2)


def test_protein_for_gain_is_1_8_per_kg() -> None:
    assert nutrition(**MAN, weight_goal="gain")["protein_g"] == pytest.approx(1.8 * 80, abs=2)


def test_protein_for_lose_is_2_to_2_2_per_kg() -> None:
    assert 2.0 * 80 - 1 <= nutrition(**MAN, weight_goal="lose")["protein_g"] <= 2.2 * 80 + 1


@pytest.mark.parametrize("goal", ["lose", "keep", "gain"])
def test_fat_is_0_8_to_1_per_kg(goal: str) -> None:
    assert 0.8 * 80 - 1 <= nutrition(**MAN, weight_goal=goal)["fat_g"] <= 1.0 * 80 + 1


@pytest.mark.parametrize("goal", ["lose", "keep", "gain"])
def test_macros_add_up_to_target(goal: str) -> None:
    result = nutrition(**MAN, weight_goal=goal)
    assert kcal_from_macros(result) == pytest.approx(result["kcal_target"], rel=0.01)


def test_macros_add_up_when_bmr_floor_applies() -> None:
    result = nutrition(**WOMAN, weight_goal="lose")
    assert kcal_from_macros(result) == pytest.approx(result["kcal_target"], rel=0.01)


def test_manual_kcal_target_wins() -> None:
    result = nutrition(**MAN, weight_goal="lose", kcal_target=2400)
    assert result["kcal_target"] == 2400
    assert kcal_from_macros(result) == pytest.approx(2400, rel=0.01)


def test_manual_kcal_target_does_not_change_tdee() -> None:
    assert nutrition(**MAN, kcal_target=2400)["tdee_rest"] == pytest.approx(2720, abs=2)


def test_without_goal_target_is_tdee() -> None:
    result = nutrition(**MAN)
    assert result["kcal_target"] == pytest.approx(result["tdee_rest"], abs=2)


def test_without_sex_nothing_is_calculated() -> None:
    result = nutrition(**{**MAN, "sex": None})
    assert result["kcal_target"] is None
    assert result["missing"] == ["sex"]


@pytest.mark.parametrize(
    ("field", "name"),
    [("age", "age"), ("height_cm", "height_cm"), ("weight_kg", "weight_kg")],
)
def test_without_body_data_nothing_is_calculated(field: str, name: str) -> None:
    result = nutrition(**{**MAN, field: None})
    assert result["kcal_target"] is None
    assert result["missing"] == [name]


def test_complete_data_has_no_missing() -> None:
    assert not nutrition(**MAN).get("missing")


def test_training_calories_minus_bmr_for_its_time() -> None:
    result = nutrition(**MAN, activity_kcal=500, activity_minutes=60)
    assert result["tdee_today"] == pytest.approx(result["tdee_rest"] + 500 - 1755 / 24, abs=2)
    assert result["assumptions"]


def test_training_calories_do_not_go_below_zero() -> None:
    result = nutrition(**MAN, activity_kcal=10, activity_minutes=120)
    assert result["tdee_today"] == pytest.approx(result["tdee_rest"], abs=1)


def test_weekly_rate_clamp_is_in_assumptions() -> None:
    result = nutrition(**MAN, weight_goal="lose", weekly_rate_kg=0.75)
    assert any("weekly_rate_kg" in a for a in result["assumptions"])


def test_zero_carbs_is_in_assumptions() -> None:
    result = nutrition(**MAN, kcal_target=800)
    assert result["carbs_g"] == 0
    assert any("углеводы 0" in a for a in result["assumptions"])
