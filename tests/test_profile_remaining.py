import pytest

from ai_coach.profile.nutrition import remaining

TARGETS = {"kcal_target": 2500, "protein_g": 150, "fat_g": 70, "carbs_g": 300}


def eaten(kcal: float | None, protein: float, fat: float, carbs: float) -> dict:
    return {"kcal": kcal, "protein_g": protein, "fat_g": fat, "carbs_g": carbs}


def test_remaining_is_target_minus_eaten() -> None:
    result = remaining(TARGETS, [eaten(1000, 60, 40, 120), eaten(800, 40, 20, 80)])
    assert result is not None
    assert result["kcal"] == pytest.approx(700)
    assert result["protein_g"] == pytest.approx(50)
    assert result["fat_g"] == pytest.approx(10)
    assert result["carbs_g"] == pytest.approx(100)


def test_nothing_eaten_gives_whole_target() -> None:
    result = remaining(TARGETS, [])
    assert result is not None
    assert (result["kcal"], result["protein_g"]) == (2500, 150)
    assert result["pending_count"] == 0


def test_overeating_gives_negative_numbers() -> None:
    result = remaining(TARGETS, [eaten(3000, 200, 100, 350)])
    assert result is not None
    assert result["kcal"] == pytest.approx(-500)
    assert result["protein_g"] == pytest.approx(-50)
    assert result["fat_g"] == pytest.approx(-30)
    assert result["carbs_g"] == pytest.approx(-50)


def test_entry_without_nutrition_is_pending_and_not_summed() -> None:
    pending = {"kcal": None, "protein_g": None, "fat_g": None, "carbs_g": None}
    result = remaining(TARGETS, [eaten(1800, 100, 60, 200), pending])
    assert result is not None
    assert result["pending_count"] == 1
    assert result["kcal"] == pytest.approx(700)


def test_without_nutrition_remaining_is_none() -> None:
    assert remaining(None, [eaten(100, 1, 1, 1)]) is None


def test_target_without_kcal_remaining_is_none() -> None:
    assert remaining({"kcal_target": None, "missing": ["sex"]}, []) is None
