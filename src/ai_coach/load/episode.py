"""Болезнь: фразы из ответов форм для разбора симптомов."""

from typing import Any

CELSIUS_UNITS = ("°C", "°С")  # латинская и кириллическая C


def form_phrases(fields: list[dict[str, Any]], answers: dict[str, Any]) -> list[str]:
    """Ответ формы -> фразы в порядке полей: number с °C - «температура N», yesno true - подпись,
    choice - «подпись вариант»; остальное и поля без ответа - ничего."""
    phrases: list[str] = []
    for field in fields:
        answer = answers.get(field["key"])
        if answer is None:
            continue
        kind = field["type"]
        if kind == "number" and field.get("unit") in CELSIUS_UNITS:
            phrases.append(f"температура {answer}")
        elif kind == "yesno" and answer is True:
            phrases.append(field["label"])
        elif kind == "choice":
            phrases.append(f"{field['label']} {answer}")
    return phrases
