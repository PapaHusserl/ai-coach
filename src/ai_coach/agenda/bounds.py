"""Границы числа в поле формы (min, max): попадание и слова для отказа (проверки - forms.py)."""

from typing import Any

LIMITS = {
    (True, True): "от {0} до {1}",
    (True, False): "не меньше {0}",
    (False, True): "не больше {1}",
}


def within(field: dict[str, Any], value: float) -> bool:
    low, high = field.get("min"), field.get("max")
    return (low is None or value >= low) and (high is None or value <= high)


def limits(field: dict[str, Any]) -> str:
    """Границы словами для отказа; вызывается, когда хотя бы одна граница задана."""
    low, high = field.get("min"), field.get("max")
    return LIMITS[low is not None, high is not None].format(_whole(low), _whole(high))


def _whole(bound: Any) -> Any:
    """Целое по значению без «.0»: 34.0 -> 34, 34.5 остаётся."""
    return int(bound) if isinstance(bound, float) and bound.is_integer() else bound
