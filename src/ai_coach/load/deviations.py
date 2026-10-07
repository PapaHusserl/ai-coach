"""Отклонения: признаки плохого восстановления, при которых тренер пересчитывает план."""

from typing import Any

WELLBEING_MAX = 2
READINESS_MIN = 33
BAD_HRV_STATUSES = ("LOW", "UNBALANCED")
ATL_OVER_CTL_MAX = 15
SLEEP_MIN_HOURS = 6


def find_deviations(
    wellbeing: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    load: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Отклонения за день. wellbeing — основная (последняя) запись самочувствия дня,
    metrics — строка daily_metrics, load — строка load_series; None — данных нет."""
    found: list[dict[str, Any]] = []
    if wellbeing and wellbeing["score"] <= WELLBEING_MAX:
        found.append({"kind": "wellbeing", "value": wellbeing["score"], "limit": WELLBEING_MAX})
    if metrics:
        readiness = metrics["readiness_score"]
        if readiness is not None and readiness < READINESS_MIN:
            found.append({"kind": "readiness", "value": readiness, "limit": READINESS_MIN})
        status = metrics["hrv_status"]
        if status is not None and status.upper() in BAD_HRV_STATUSES:
            found.append({"kind": "hrv", "value": status, "limit": list(BAD_HRV_STATUSES)})
        sleep = metrics["sleep_seconds"]
        if sleep is not None and sleep < SLEEP_MIN_HOURS * 3600:
            found.append(
                {"kind": "sleep", "value": round(sleep / 3600, 1), "limit": SLEEP_MIN_HOURS}
            )
    if load and load["atl"] - load["ctl"] > ATL_OVER_CTL_MAX:
        found.append(
            {
                "kind": "atl_over_ctl",
                "value": round(load["atl"] - load["ctl"], 1),
                "limit": ATL_OVER_CTL_MAX,
            }
        )
    return found
