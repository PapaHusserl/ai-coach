"""Шаг Н29, партия 1: часть дня по часам."""

from datetime import datetime

import pytest

DAY = "2026-10-07"


@pytest.mark.parametrize(
    ("clock", "part"),
    [
        ("04:00", "morning"),
        ("11:59", "morning"),
        ("12:00", "day"),
        ("18:59", "day"),
        ("19:00", "evening"),
        ("23:59", "evening"),
        ("00:30", "evening"),
        ("03:59", "evening"),
    ],
)
def test_day_part_boundaries(clock: str, part: str) -> None:
    from ai_coach.decisions import day_part

    assert day_part(datetime.fromisoformat(f"{DAY} {clock}:00")) == part
