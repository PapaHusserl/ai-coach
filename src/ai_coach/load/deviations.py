"""Отклонения: признаки плохого восстановления, при которых тренер пересчитывает план."""

from typing import Any

WELLBEING_MAX = 2
MOOD_MAX = 2
STRESS_MIN = 4
READINESS_MIN = 33
BAD_HRV_STATUSES = ("LOW", "UNBALANCED")
ATL_OVER_CTL_MAX = 15
SLEEP_MIN_HOURS = 6


def main_wellbeing(marks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Основная запись дня (последняя); mood и stress - последние непустые за день, чтобы вечерняя
    оценка не терялась от более поздней записи без неё. Записей нет - None."""
    if not marks:
        return None
    main = dict(marks[-1])
    for key in ("mood", "stress"):
        given = [m[key] for m in marks if m[key] is not None]
        main[key] = given[-1] if given else None
    return main


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
    if wellbeing and wellbeing.get("mood") is not None and wellbeing["mood"] <= MOOD_MAX:
        found.append({"kind": "mood", "value": wellbeing["mood"], "limit": MOOD_MAX})
    if wellbeing and wellbeing.get("stress") is not None and wellbeing["stress"] >= STRESS_MIN:
        found.append({"kind": "stress", "value": wellbeing["stress"], "limit": STRESS_MIN})
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
