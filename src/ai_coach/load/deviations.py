"""Отклонения: признаки плохого восстановления, при которых тренер пересчитывает план."""

import statistics
from typing import Any

# Ниже своей нормы: медиана за BELOW_DAYS прошлых дней, нужно BELOW_MIN_DAYS дней, порог BELOW_DROP.
# Догадка до калибровки v2.9.
BELOW_DAYS = 14
BELOW_MIN_DAYS = 7
BELOW_DROP = 1
WELLBEING_MAX = 2
MOOD_MAX = 2
STRESS_MIN = 4
READINESS_MIN = 33
BAD_HRV_STATUSES = ("LOW", "UNBALANCED", "BELOW")
ATL_OVER_CTL_MAX = 15
SLEEP_MIN_HOURS = 6
# Явные симптомы простуды (ряд WURSS-24): основа (подстрока текста в нижнем регистре) -> слово.
SYMPTOMS = (
    ("горл", "горло"),
    ("насморк", "насморк"),
    ("сопл", "сопли"),
    ("температур", "температура"),
    ("кашл", "кашель"),
    ("кашел", "кашель"),
    ("залож", "заложенность"),
    ("чиха", "чихание"),
    ("чихн", "чихание"),
    ("перш", "першение"),
    ("осип", "осиплость"),
    ("охрип", "осиплость"),
    ("озноб", "озноб"),
    ("зноб", "озноб"),
    ("ломот", "ломота"),
    ("ломит", "ломота"),
    ("простуд", "простуда"),
    ("простыл", "простуда"),
)


def find_symptoms(texts: list[str]) -> list[str]:
    """Слова-симптомы из текстов самочувствия: без повторов, в порядке SYMPTOMS."""
    low = " ".join(texts).lower()
    found: list[str] = []
    for stem, word in SYMPTOMS:
        if stem in low and word not in found:
            found.append(word)
    return found


def main_wellbeing(marks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Основная запись дня (последняя); mood и stress - последние непустые за день, чтобы вечерняя
    оценка не терялась от более поздней записи без неё. Записей нет - None."""
    if not marks:
        return None
    main = dict(marks[-1])
    for key in ("mood", "stress"):
        given = [m[key] for m in marks if m[key] is not None]
        main[key] = given[-1] if given else None
    main["texts"] = [m["text"] for m in marks if m["text"]]
    return main


def wellbeing_norms(marks: list[dict[str, Any]]) -> dict[str, float]:
    """Своя норма оценок: медиана значений дня по записям прошлых дней; дней со значением меньше
    BELOW_MIN_DAYS - ключа нет."""
    by_day: dict[str, list[dict[str, Any]]] = {}
    for mark in marks:
        by_day.setdefault(mark["date"], []).append(mark)
    days = [main_wellbeing(day_marks) for day_marks in by_day.values()]
    norms: dict[str, float] = {}
    for key, name in (("score", "score"), ("mood", "mood")):
        values = [day[key] for day in days if day and day[key] is not None]
        if len(values) >= BELOW_MIN_DAYS:
            norms[name] = statistics.median(values)
    return norms


def find_below(wellbeing: dict[str, Any], norms: dict[str, float]) -> list[dict[str, Any]]:
    """Оценки дня на BELOW_DROP и больше ниже своей нормы; по оценке, у которой сработал
    абсолютный порог, строки нет."""
    found: list[dict[str, Any]] = []
    for key, kind, top in (
        ("score", "wellbeing_below", WELLBEING_MAX),
        ("mood", "mood_below", MOOD_MAX),
    ):
        value = wellbeing.get(key)
        if value is None or value <= top or key not in norms:
            continue
        if norms[key] - value >= BELOW_DROP:
            found.append({"kind": kind, "value": value, "limit": norms[key]})
    return found


def find_deviations(
    wellbeing: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    load: dict[str, Any] | None,
    norms: dict[str, float] | None = None,
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
    if wellbeing and norms:
        found.extend(find_below(wellbeing, norms))
    symptoms = find_symptoms(wellbeing.get("texts", [])) if wellbeing else []
    if symptoms:
        found.append({"kind": "symptoms", "value": symptoms, "limit": None})
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
