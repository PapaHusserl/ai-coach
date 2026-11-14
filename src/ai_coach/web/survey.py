"""Опросники чек-ина (coach_events.survey): какие отметки принимает пункт и когда он «красный»."""

from typing import Any

SURVEY_MARKS = {
    "evening": ("checkin",),
    "feel": ("feel",),
    "focus": ("rating",),
    "none": ("done",),
}


def marks_of(survey: str | None) -> tuple[str, ...]:
    """Отметки опросника; NULL - старый чек-ин (анкета вечера); неизвестное имя - пусто."""
    return SURVEY_MARKS.get(survey or "evening", ())


def checkin_due(survey: str | None, marks: dict[str, Any], evening: bool) -> bool:
    """Прошедший чек-ин без отметки своего опросника: вечерний - нет чек-ина вечера за день,
    feel - нет самочувствия пункта, focus - нет оценки, none - нет «сделал / пропустил»."""
    missing = {
        "evening": not evening,
        "feel": not marks["feel"],
        "focus": not marks["ratings"],
        "none": marks["done"] is None,
    }
    return missing.get(survey or "evening", False)
