"""Пороги плохого восстановления: константы модуля ai_coach.load.deviations и
find_deviations(wellbeing, metrics, load) -> список {"kind", ...}; None — данных нет."""

from typing import Any

import pytest

from ai_coach.load import deviations
from ai_coach.load.deviations import find_deviations

HOUR = 3600


def metrics(**values: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"readiness_score": None, "hrv_status": None, "sleep_seconds": None}
    return {**row, **values}


def kinds(wellbeing: Any = None, day: Any = None, load: Any = None) -> list[str]:
    return [d["kind"] for d in find_deviations(wellbeing, day, load)]


def test_thresholds_are_module_constants() -> None:
    assert deviations.WELLBEING_MAX == 2
    assert deviations.READINESS_MIN == 33
    assert deviations.ATL_OVER_CTL_MAX == 15
    assert deviations.SLEEP_MIN_HOURS == 6
    assert set(deviations.BAD_HRV_STATUSES) == {"LOW", "UNBALANCED"}


def test_no_data_no_deviations() -> None:
    assert find_deviations(None, None, None) == []


def test_empty_metrics_no_deviations() -> None:
    assert kinds(day=metrics()) == []


def test_good_day_has_no_deviations() -> None:
    day = metrics(readiness_score=70, hrv_status="BALANCED", sleep_seconds=8 * HOUR)
    assert kinds({"score": 4}, day, {"atl": 50, "ctl": 45}) == []


@pytest.mark.parametrize("score", [1, 2])
def test_low_wellbeing_is_a_deviation(score: int) -> None:
    assert kinds({"score": score}) == ["wellbeing"]


def test_wellbeing_3_is_fine() -> None:
    assert kinds({"score": 3}) == []


def test_readiness_32_is_a_deviation_33_is_fine() -> None:
    assert kinds(day=metrics(readiness_score=32)) == ["readiness"]
    assert kinds(day=metrics(readiness_score=33)) == []


@pytest.mark.parametrize("status", ["LOW", "UNBALANCED"])
def test_bad_hrv_status_is_a_deviation(status: str) -> None:
    assert kinds(day=metrics(hrv_status=status)) == ["hrv"]


@pytest.mark.parametrize("status", ["BALANCED", "POOR", "NO_STATUS"])
def test_other_hrv_status_is_fine(status: str) -> None:
    assert kinds(day=metrics(hrv_status=status)) == []


def test_atl_minus_ctl_over_15_is_a_deviation() -> None:
    assert kinds(load={"atl": 65.5, "ctl": 50}) == ["atl_over_ctl"]


def test_atl_minus_ctl_exactly_15_is_fine() -> None:
    assert kinds(load={"atl": 65, "ctl": 50}) == []


def test_ctl_above_atl_is_fine() -> None:
    assert kinds(load={"atl": 10, "ctl": 50}) == []


def test_sleep_under_6_hours_is_a_deviation() -> None:
    assert kinds(day=metrics(sleep_seconds=6 * HOUR - 1)) == ["sleep"]


def test_sleep_exactly_6_hours_is_fine() -> None:
    assert kinds(day=metrics(sleep_seconds=6 * HOUR)) == []


def test_several_deviations_are_all_reported() -> None:
    day = metrics(readiness_score=10, sleep_seconds=4 * HOUR)
    assert sorted(kinds({"score": 1}, day)) == ["readiness", "sleep", "wellbeing"]
