from datetime import datetime

import pytest

from ai_coach.load.stress import STRESS_WINDOW_MIN, stress_at

MOMENT = datetime(2026, 10, 7, 14, 0, 0)


def point(local: str, level: int | None) -> dict[str, object]:
    # метка Garmin - epoch в мс; местное время берётся из системного пояса
    return {"ts_ms": int(datetime.fromisoformat(local).timestamp() * 1000), "level": level}


def test_window_is_15_minutes() -> None:
    assert STRESS_WINDOW_MIN == 15


def test_average_of_points_in_window() -> None:
    points = [
        point("2026-10-07 13:57:00", 20),
        point("2026-10-07 14:00:00", 40),
        point("2026-10-07 14:03:00", 60),
    ]
    assert stress_at(points, MOMENT) == 40


def test_points_outside_window_are_ignored() -> None:
    points = [
        point("2026-10-07 13:40:00", 90),
        point("2026-10-07 14:00:00", 30),
        point("2026-10-07 14:20:00", 90),
    ]
    assert stress_at(points, MOMENT) == 30


def test_window_edges_are_included() -> None:
    points = [point("2026-10-07 13:45:00", 20), point("2026-10-07 14:15:00", 40)]
    assert stress_at(points, MOMENT) == 30


def test_point_just_past_window_is_ignored() -> None:
    points = [point("2026-10-07 14:00:00", 20), point("2026-10-07 14:15:10", 90)]
    assert stress_at(points, MOMENT) == 20


def test_level_one_is_a_measurement() -> None:
    assert stress_at([point("2026-10-07 14:00:00", 1)], MOMENT) == 1


@pytest.mark.parametrize("bad", [-1, -2, 0, None])
def test_levels_without_measurement_are_excluded(bad: int | None) -> None:
    points = [point("2026-10-07 13:57:00", bad), point("2026-10-07 14:00:00", 50)]
    assert stress_at(points, MOMENT) == 50


def test_no_points_in_window_is_none() -> None:
    assert stress_at([point("2026-10-07 10:00:00", 50)], MOMENT) is None


def test_only_unmeasured_points_is_none() -> None:
    assert stress_at([point("2026-10-07 14:00:00", -1)], MOMENT) is None


def test_empty_points_is_none() -> None:
    assert stress_at([], MOMENT) is None


def test_average_is_rounded_to_integer() -> None:
    points = [point("2026-10-07 14:00:00", 20), point("2026-10-07 14:03:00", 42)]
    result = stress_at(points, MOMENT)
    assert result == 31
    assert isinstance(result, int)


def test_window_crosses_midnight() -> None:
    moment = datetime(2026, 10, 8, 0, 5, 0)
    points = [point("2026-10-07 23:55:00", 20), point("2026-10-08 00:10:00", 40)]
    assert stress_at(points, moment) == 30
