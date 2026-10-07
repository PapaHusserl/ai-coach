"""Калории и БЖУ: чистые функции, без базы. Это оценка, не медицинский совет."""

from dataclasses import dataclass
from typing import Any

ACTIVITY_FACTORS = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
DEFAULT_ACTIVITY = "light"
LOSE_DEFICIT = (0.15, 0.20)
LOSE_DEFAULT = 0.175
GAIN_SURPLUS = (0.05, 0.15)
GAIN_DEFAULT = 0.10
KCAL_PER_KG = 7700
DAYS = 7
MINUTES_PER_DAY = 1440
PROTEIN_LOSE = 2.0
PROTEIN_OTHER = 1.8
FAT = 0.9
FAT_MIN = 0.8
KCAL_PROTEIN = 4
KCAL_FAT = 9
KCAL_CARBS = 4
FORMULA = "BMR Mifflin-St Jeor x коэффициент активности + калории активностей дня"


def bmr(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor: м +5, ж -161."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "m" else base - 161


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _share(goal: str, rate: float | None, tdee: float, notes: list[str]) -> float:
    """Доля от TDEE: минус при lose, плюс при gain, 0 при keep. weekly_rate_kg задаёт долю
    (кг в неделю * 7700 / 7 ккал в день), но в пределах диапазона (зажим — в notes)."""
    if goal == "keep":
        return 0.0
    low, high = LOSE_DEFICIT if goal == "lose" else GAIN_SURPLUS
    if rate is None:
        return LOSE_DEFAULT if goal == "lose" else GAIN_DEFAULT
    wanted = rate * KCAL_PER_KG / DAYS / tdee
    share = _clamp(wanted, low, high)
    if share != wanted:
        notes.append(f"weekly_rate_kg вне допустимого, доля {share:.0%} вместо {wanted:.0%}")
    return share


def _macros(kcal: float, weight_kg: float, goal: str) -> tuple[float, float, float]:
    protein = (PROTEIN_LOSE if goal == "lose" else PROTEIN_OTHER) * weight_kg
    fat = FAT * weight_kg
    if kcal - protein * KCAL_PROTEIN - fat * KCAL_FAT < 0:
        fat = FAT_MIN * weight_kg
    carbs = max(0.0, (kcal - protein * KCAL_PROTEIN - fat * KCAL_FAT) / KCAL_CARBS)
    return protein, fat, carbs


@dataclass
class NutritionInput:
    """Данные для расчёта. sex (m/f), age, height_cm, weight_kg обязательны (None - не
    хватает). Необязательно: activity_level (иначе light), weight_goal (иначе keep),
    weekly_rate_kg, kcal_target (ручное, главнее расчёта). activity_kcal и activity_minutes -
    калории и длительность активностей дня."""

    sex: Any
    age: Any
    height_cm: Any
    weight_kg: Any
    activity_level: str | None = None
    weight_goal: str | None = None
    weekly_rate_kg: float | None = None
    kcal_target: float | None = None
    activity_kcal: float = 0
    activity_minutes: float = 0


def nutrition(data: NutritionInput) -> dict[str, Any]:
    """Цели на день. Не хватает обязательного — kcal_target None и missing со списком.
    Из калорий активностей вычитается BMR за их время (он уже в коэффициенте активности),
    не ниже 0."""
    sex, age, height_cm, weight_kg = data.sex, data.age, data.height_cm, data.weight_kg
    activity_level, weight_goal = data.activity_level, data.weight_goal
    activity_kcal = data.activity_kcal
    body = {"sex": sex, "age": age, "height_cm": height_cm, "weight_kg": weight_kg}
    missing = [key for key, value in body.items() if value is None]
    if missing:
        return {"kcal_target": None, "missing": missing}
    notes: list[str] = []
    if activity_level is None:
        activity_level = DEFAULT_ACTIVITY
        notes.append(f"activity_level не задан, взят {DEFAULT_ACTIVITY}")
    if weight_goal is None:
        weight_goal = "keep"
        notes.append("weight_goal не задан, взят keep")
    base = bmr(sex, weight_kg, height_cm, age)
    rest = base * ACTIVITY_FACTORS[activity_level]
    if data.activity_minutes > 0:
        activity_kcal = max(0.0, activity_kcal - base / MINUTES_PER_DAY * data.activity_minutes)
        notes.append("из калорий тренировок вычтен BMR за время тренировки")
    today = rest + activity_kcal
    sign = 1 if weight_goal == "gain" else -1
    kcal = today * (1 + sign * _share(weight_goal, data.weekly_rate_kg, today, notes))
    if weight_goal == "lose":
        kcal = max(kcal, base)
    if data.kcal_target is not None:
        kcal = data.kcal_target
        notes.append("kcal_target задан вручную")
    protein, fat, carbs = _macros(kcal, weight_kg, weight_goal)
    if carbs == 0:
        notes.append("углеводы 0, БЖУ превышают цель")
    return {
        "bmr": round(base),
        "tdee_rest": round(rest),
        "tdee_today": round(today),
        "kcal_target": round(kcal),
        "protein_g": round(protein),
        "fat_g": round(fat),
        "carbs_g": round(carbs),
        "formula": FORMULA,
        "assumptions": notes,
    }
