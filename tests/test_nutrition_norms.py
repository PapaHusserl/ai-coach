"""Нормы (МР 2.3.1.0253-21), верхние уровни (КТС № 299), типичное потребление с едой (шаг 24)."""

import pytest

from ai_coach.nutrition.groups import FOOD_GROUPS
from ai_coach.nutrition.norms import FOOD_TYPICAL, NUTRIENT_NORMS, norms_table

OMEGA3 = "омега-3 (ДГК+ЭПК)"

# нутриент: (норма, верхний уровень, единица)
NORMS = {
    "витамин D": (15, 15, "мкг"),
    "йод": (150, 300, "мкг"),
    "селен": (70, 150, "мкг"),
    "железо": (10, 20, "мг"),
    "витамин B12": (3, 9, "мкг"),
    "цинк": (12, 25, "мг"),
    "кальций": (1000, 2500, "мг"),
    "магний": (420, 800, "мг"),
    "фолаты": (400, 600, "мкг"),
    "витамин E": (15, 150, "мг ТЭ"),
    "витамин C": (100, 900, "мг"),
    OMEGA3: (250, 5000, "мг"),
}
TYPICAL = {
    "кальций": 690,
    "железо": 17.8,
    "магний": 323,
    "витамин C": 58,
    "йод": 80,
    "фолаты": 0,
    "витамин D": 4.9,
    OMEGA3: 110,
    "селен": 132,
    "витамин B12": 5.8,
    "цинк": 12.6,
    "витамин E": 10.4,
}
SUPPLEMENT_MAX = {
    "витамин D": 10.1,
    "йод": 220,
    "селен": 18,
    "железо": 2.2,
    "фолаты": 600,
    OMEGA3: 4890,
}


def by_name() -> dict[str, dict]:
    return {row["nutrient"]: row for row in norms_table()}  # type: ignore[misc]


def test_twelve_rows() -> None:
    assert len(norms_table()) == 12


def test_every_row_has_all_fields() -> None:
    fields = {
        "nutrient",
        "norm",
        "upper",
        "unit",
        "note",
        "norm_source",
        "upper_source",
        "food_typical",
        "food_source",
        "food_confidence",
        "supplement_max",
    }
    for row in norms_table():
        assert fields <= set(row)


@pytest.mark.parametrize("name", sorted(NORMS))
def test_norm_upper_unit(name: str) -> None:
    row = by_name()[name]
    assert (row["norm"], row["upper"], row["unit"]) == NORMS[name]


def test_sources_are_mr_and_ktc() -> None:
    for row in norms_table():
        assert "МР 2.3.1.0253-21" in str(row["norm_source"])
        assert "КТС № 299" in str(row["upper_source"])


@pytest.mark.parametrize("name", [OMEGA3, "фолаты"])
def test_special_rows_have_note(name: str) -> None:
    assert by_name()[name]["note"]


def test_other_rows_have_no_note() -> None:
    notes = {n: r["note"] for n, r in by_name().items() if n not in (OMEGA3, "фолаты")}
    assert all(note is None for note in notes.values())
    assert len(notes) == 10


def test_food_typical_keys_match_norms() -> None:
    assert set(FOOD_TYPICAL) == set(NUTRIENT_NORMS)


@pytest.mark.parametrize("name", sorted(TYPICAL))
def test_food_typical_values(name: str) -> None:
    assert FOOD_TYPICAL[name][0] == TYPICAL[name]
    assert by_name()[name]["food_typical"] == TYPICAL[name]


def test_food_source_is_not_empty() -> None:
    for row in norms_table():
        assert str(row["food_source"]).strip()


def test_confidence_values() -> None:
    allowed = {"высокая", "средняя", "низкая"}
    assert {r["food_confidence"] for r in norms_table()} <= allowed


def test_low_confidence_only_iodine_selenium_d() -> None:
    low = {n for n, r in by_name().items() if r["food_confidence"] == "низкая"}
    assert low == {"йод", "селен", "витамин D"}


def test_high_confidence_only_folate() -> None:
    high = {n for n, r in by_name().items() if r["food_confidence"] == "высокая"}
    assert high == {"фолаты"}


@pytest.mark.parametrize("name", sorted(SUPPLEMENT_MAX))
def test_supplement_max_values(name: str) -> None:
    assert by_name()[name]["supplement_max"] == pytest.approx(SUPPLEMENT_MAX[name])


def test_supplement_max_formula_for_all_rows() -> None:
    for row in norms_table():
        expected = max(row["upper"] - row["food_typical"], 0)  # type: ignore[operator]
        assert row["supplement_max"] == pytest.approx(expected)


def test_supplement_max_never_exceeds_upper() -> None:
    for row in norms_table():
        assert 0 <= row["supplement_max"] <= row["upper"]  # type: ignore[operator]


def test_vitamin_d_in_international_units() -> None:
    row = by_name()["витамин D"]
    assert (row["norm_iu"], row["upper_iu"]) == (600, 600)
    assert row["supplement_max_iu"] == pytest.approx(404)


def test_only_vitamin_d_has_iu_fields() -> None:
    for name, row in by_name().items():
        if name != "витамин D":
            assert "norm_iu" not in row


def test_group_nutrients_with_norm_use_norm_keys() -> None:
    """Имена из FOOD_GROUPS, похожие на строки норм, совпадают с ключами NUTRIENT_NORMS."""
    used = {n for _, nutrients in FOOD_GROUPS.values() for n in nutrients}
    assert OMEGA3 in used
    assert "омега-3" not in used
    for name in ("витамин D", "йод", "селен", "железо", "витамин B12", "цинк", "кальций"):
        assert name in used
    for name in ("магний", "фолаты", "витамин E", "витамин C"):
        assert name in used
    assert {n for n in used if n in NUTRIENT_NORMS} == set(NUTRIENT_NORMS)
