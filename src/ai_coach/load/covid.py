"""Отметка COVID у серии болезни: константы лестниц и признаки серии с отметкой."""

from collections.abc import Collection
from datetime import date

COVID_REST_DAYS = 5  # у тяжёлой серии с отметкой COVID возврат не раньше 6-го дня серии
COVID_LIGHT_DAYS = 5  # дней лёгкого режима у лёгкой серии с отметкой COVID


def series_marked(marks: Collection[str], first: date, day: date) -> bool:
    """Есть отметка COVID с датой от первого дня серии по day."""
    return any(first.isoformat() <= mark <= day.isoformat() for mark in marks)


def rest_floor(first: date, last: date, is_marked: bool) -> int:
    """Не раньше какого дня после last возврат у серии: у серии с отметкой - 6-й день серии."""
    return COVID_REST_DAYS - (last - first).days if is_marked else 0


def in_light(first: date, day: date, is_marked: bool) -> bool:
    """День day - в дни лёгкого режима лёгкой серии с отметкой (дни серии 1..COVID_LIGHT_DAYS)."""
    return is_marked and (day - first).days < COVID_LIGHT_DAYS
