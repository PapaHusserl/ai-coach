"""wellbeing_day(moment): вчера, если время раньше EVENING_CUTOFF (04:00), иначе сегодня."""

from datetime import datetime

import pytest

from ai_coach.store.journal import wellbeing_day


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        ("2026-10-11 00:00:00", "2026-10-10"),
        ("2026-10-11 01:51:00", "2026-10-10"),
        ("2026-10-11 03:59:59", "2026-10-10"),
        ("2026-10-11 04:00:00", "2026-10-11"),
        ("2026-10-11 12:00:00", "2026-10-11"),
        ("2026-10-11 23:59:59", "2026-10-11"),
        ("2026-11-01 00:00:00", "2026-10-31"),
        ("2026-11-01 04:00:00", "2026-11-01"),
        ("2026-03-01 03:00:00", "2026-02-28"),
        ("2027-01-01 02:00:00", "2026-12-31"),
    ],
)
def test_wellbeing_day(moment: str, expected: str) -> None:
    assert wellbeing_day(datetime.fromisoformat(moment)) == expected
