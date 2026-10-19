"""Суточные нормы, верхние уровни и типичное потребление с едой для нутриентов из FOOD_GROUPS.
Пол и возраст в профиле не хранятся - константы для мужчин."""

D_IU_PER_MCG = 40  # витамин D: 1 мкг = 40 МЕ

NORM_SOURCE = "МР 2.3.1.0253-21, табл. 11–12, мужчины старше 18 лет"
UPPER_SOURCE = "КТС № 299, прил. 5, гл. II разд. 1 — уровень для суточной дозы БАД"

OMEGA3 = "омега-3 (ДГК+ЭПК)"

# нутриент -> (суточная норма, верхний уровень для дозы БАД, единица, примечание)
NUTRIENT_NORMS: dict[str, tuple[float, float | None, str, str | None]] = {
    "витамин D": (15, 15, "мкг", None),
    OMEGA3: (
        250,
        5000,
        "мг",
        "норма — адекватный уровень ДГК+ЭПК по МР; 5 г — предел КТС на всё семейство ω-3, "
        "своего предела у ДГК+ЭПК нет",
    ),
    "йод": (150, 300, "мкг", None),
    "селен": (70, 150, "мкг", None),
    "железо": (10, 20, "мг", None),
    "витамин B12": (3, 9, "мкг", None),
    "цинк": (12, 25, "мг", None),
    "кальций": (1000, 2500, "мг", None),
    "магний": (420, 800, "мг", None),
    "фолаты": (400, 600, "мкг", "ВДУП — для фолиевой кислоты"),
    "витамин E": (15, 150, "мг ТЭ", None),
    "витамин C": (100, 900, "мг", None),
}

HIGH, MEDIUM, LOW = "высокая", "средняя", "низкая"
RU_2023 = "РФ 2023, Кешабянц и др., Вопросы питания 2026, т. 95 № 3, табл. 1"
NHANES = "NHANES/WWEIA 2017–03.2020, Table 1, мужчины 20+"

# нутриент -> (типичное суточное потребление с едой в единицах NUTRIENT_NORMS,
#              источник, уверенность)
FOOD_TYPICAL: dict[str, tuple[float, str, str]] = {
    "витамин D": (4.9, NHANES, LOW),
    OMEGA3: (110, NHANES, MEDIUM),
    "йод": (80, "РФ, оценка НМИЦ эндокринологии (вторично)", LOW),
    "селен": (132, NHANES, LOW),
    "железо": (17.8, RU_2023, MEDIUM),
    "витамин B12": (5.8, NHANES, MEDIUM),
    "цинк": (12.6, NHANES, MEDIUM),
    "кальций": (690, RU_2023, MEDIUM),
    "магний": (323, RU_2023, MEDIUM),
    "фолаты": (0, "в РФ мука не обогащается; пищевые фолаты в ВДУП не входят", HIGH),
    "витамин E": (10.4, NHANES, MEDIUM),
    "витамин C": (58, RU_2023, MEDIUM),
}


def norms_table() -> list[dict[str, object]]:
    """Строки для MCP: nutrient, norm, upper, unit, note, norm_source, upper_source, food_typical,
    food_source, food_confidence, supplement_max = max(upper - food_typical, 0) (None без upper);
    у витамина D ещё norm_iu, upper_iu, supplement_max_iu (МЕ)."""
    rows: list[dict[str, object]] = []
    for name, (norm, upper, unit, note) in NUTRIENT_NORMS.items():
        typical, food_source, confidence = FOOD_TYPICAL[name]
        supplement_max = None if upper is None else round(max(upper - typical, 0), 2)
        row: dict[str, object] = {
            "nutrient": name,
            "norm": norm,
            "upper": upper,
            "unit": unit,
            "note": note,
            "norm_source": NORM_SOURCE,
            "upper_source": UPPER_SOURCE,
            "food_typical": typical,
            "food_source": food_source,
            "food_confidence": confidence,
            "supplement_max": supplement_max,
        }
        if name == "витамин D":
            row["norm_iu"] = norm * D_IU_PER_MCG
            row["upper_iu"] = None if upper is None else upper * D_IU_PER_MCG
            row["supplement_max_iu"] = (
                None if supplement_max is None else round(supplement_max * D_IU_PER_MCG, 1)
            )
        rows.append(row)
    return rows
