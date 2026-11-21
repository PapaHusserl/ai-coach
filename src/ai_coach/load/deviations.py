"""Отклонения: признаки плохого восстановления, при которых тренер пересчитывает план."""

import statistics
from typing import Any

# SYMPTOMS и NEGATIONS_* живут в symptom_text.py; здесь они же - для справки и тестов.
from ai_coach.load.symptom_text import FEVER_FROM as FEVER_FROM
from ai_coach.load.symptom_text import NEGATIONS_AFTER as NEGATIONS_AFTER
from ai_coach.load.symptom_text import NEGATIONS_BEFORE as NEGATIONS_BEFORE
from ai_coach.load.symptom_text import SYMPTOMS as SYMPTOMS
from ai_coach.load.symptom_text import find_fever, find_symptoms

# Ниже своей нормы: медиана за BELOW_DAYS прошлых дней, нужно BELOW_MIN_DAYS дней, порог BELOW_DROP.
# Проверено v2.9 на окне 2026-10-12…11-17.
BELOW_DAYS = 14
BELOW_MIN_DAYS = 7
BELOW_DROP = 1
WELLBEING_MAX = 2
MOOD_MAX = 2
STRESS_MIN = 4
FATIGUE_MIN = 4
IRRITABILITY_MIN = 4
# Вечерние строки, которые утром следующего дня переносятся с ключом day (Н38, Р7).
EVENING_KINDS = ("mood", "stress", "mood_below", "fatigue", "irritability")
# Вечерние оценки: заданы за сегодня - вчерашние строки не переносятся.
EVENING_SCORES = ("mood", "stress", "fatigue", "irritability")
READINESS_MIN = 33
BAD_HRV_STATUSES = ("LOW", "UNBALANCED", "BELOW")
ATL_OVER_CTL_MAX = 15
SLEEP_MIN_HOURS = 6


def main_wellbeing(marks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Основная запись дня (последняя); mood, stress, fatigue и irritability - последние непустые за
    день, чтобы вечерняя оценка не терялась от более поздней записи без неё. Записей нет - None."""
    if not marks:
        return None
    main = dict(marks[-1])
    for key in EVENING_SCORES:
        given = [m[key] for m in marks if m.get(key) is not None]
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


def _score_rows(wellbeing: dict[str, Any] | None) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if not wellbeing:
        return found
    if wellbeing["score"] <= WELLBEING_MAX:
        found.append({"kind": "wellbeing", "value": wellbeing["score"], "limit": WELLBEING_MAX})
    if wellbeing.get("mood") is not None and wellbeing["mood"] <= MOOD_MAX:
        found.append({"kind": "mood", "value": wellbeing["mood"], "limit": MOOD_MAX})
    if wellbeing.get("stress") is not None and wellbeing["stress"] >= STRESS_MIN:
        found.append({"kind": "stress", "value": wellbeing["stress"], "limit": STRESS_MIN})
    for key, top in (("fatigue", FATIGUE_MIN), ("irritability", IRRITABILITY_MIN)):
        if wellbeing.get(key) is not None and wellbeing[key] >= top:
            found.append({"kind": key, "value": wellbeing[key], "limit": top})
    return found


def evening_rows(rows: list[dict[str, Any]], day: str) -> list[dict[str, Any]]:
    """Вечерние строки (EVENING_KINDS) вчерашнего дня с ключом day; прочие коды не переносятся."""
    return [{**row, "day": day} for row in rows if row["kind"] in EVENING_KINDS]


def _text_rows(texts: list[str]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    symptoms = find_symptoms(texts)
    if symptoms:
        found.append({"kind": "symptoms", "value": symptoms, "limit": None})
    fever = find_fever(texts)
    if fever is not None:
        found.append({"kind": "fever", "value": fever, "limit": FEVER_FROM})
    return found


def _metrics_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    readiness = metrics["readiness_score"]
    if readiness is not None and readiness < READINESS_MIN:
        found.append({"kind": "readiness", "value": readiness, "limit": READINESS_MIN})
    status = metrics["hrv_status"]
    if status is not None and status.upper() in BAD_HRV_STATUSES:
        found.append({"kind": "hrv", "value": status, "limit": list(BAD_HRV_STATUSES)})
    sleep = metrics["sleep_seconds"]
    if sleep is not None and sleep < SLEEP_MIN_HOURS * 3600:
        found.append({"kind": "sleep", "value": round(sleep / 3600, 1), "limit": SLEEP_MIN_HOURS})
    return found


def find_deviations(
    wellbeing: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    load: dict[str, Any] | None,
    norms: dict[str, float] | None = None,
    phrases: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Отклонения за день. wellbeing — основная (последняя) запись самочувствия дня,
    metrics — строка daily_metrics, load — строка load_series; None — данных нет.
    phrases — фразы из ответов форм дня: идут в разбор симптомов вместе с текстами записи."""
    found = _score_rows(wellbeing)
    if wellbeing and norms:
        found.extend(find_below(wellbeing, norms))
    own: list[str] = wellbeing.get("texts", []) if wellbeing else []
    found.extend(_text_rows(own + (phrases or [])))
    if metrics:
        found.extend(_metrics_rows(metrics))
    if load and load["atl"] - load["ctl"] > ATL_OVER_CTL_MAX:
        found.append(
            {
                "kind": "atl_over_ctl",
                "value": round(load["atl"] - load["ctl"], 1),
                "limit": ATL_OVER_CTL_MAX,
            }
        )
    return found
