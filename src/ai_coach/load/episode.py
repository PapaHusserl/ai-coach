"""Болезнь: фразы из ответов форм для разбора симптомов; серия болезни по дням и фаза."""

from collections.abc import Callable, Mapping
from datetime import date, timedelta
from typing import Any

from ai_coach.load.symptom_text import find_fever, find_symptoms

CELSIUS_UNITS = ("°C", "°С")  # латинская и кириллическая C
# Тяжёлые слова серии (кроме температуры): оба есть в SYMPTOMS.
SEVERE_WORDS = ("ломота", "озноб")
REST_DAYS = 2  # чистых дней покоя подряд до возврата
REST_MAX_DAYS = 3  # потолок покоя: на следующий день возврат без условий
RETURN_DAYS = 7  # дней лестницы возврата
EPISODE_DAYS = 21  # глубина поиска серии: от today - 20 по today
GAP_MAX_DAYS = 1  # дней без симптома между соседними днями болезни, которые серию не рвут


def form_phrases(fields: list[dict[str, Any]], answers: dict[str, Any]) -> list[str]:
    """Ответ формы -> фразы в порядке полей: number с °C - «температура N», yesno true - подпись,
    choice - «подпись вариант»; остальное и поля без ответа - ничего."""
    phrases: list[str] = []
    for field in fields:
        answer = answers.get(field["key"])
        if answer is None:
            continue
        kind = field["type"]
        if kind == "number" and field.get("unit") in CELSIUS_UNITS:
            phrases.append(f"температура {answer}")
        elif kind == "yesno" and answer is True:
            phrases.append(field["label"])
        elif kind == "choice":
            phrases.append(f"{field['label']} {answer}")
    return phrases


def sick_days(texts: dict[str, list[str]], recorded: set[str]) -> dict[str, dict[str, Any]]:
    """Признаки по датам из texts и recorded: record (есть строка журнала), symptoms, fever (не ниже
    порога), severe (температура или слово из SEVERE_WORDS)."""
    result: dict[str, dict[str, Any]] = {}
    for iso in sorted(set(texts) | recorded):
        phrases = texts.get(iso, [])
        symptoms = find_symptoms(phrases)
        fever = find_fever(phrases)
        severe = fever is not None or any(word in symptoms for word in SEVERE_WORDS)
        result[iso] = {
            "record": iso in recorded,
            "symptoms": symptoms,
            "fever": fever,
            "severe": severe,
        }
    return result


def _return_start(n: int, clean: Callable[[int], bool]) -> tuple[int | None, bool]:
    """Номер дня после последнего дня болезни, с которого начинается возврат, и признак потолка;
    n - сколько дней прошло. None - покой ещё идёт. clean(k) - чист ли k-й день покоя."""
    streak = 0
    for k in range(1, min(REST_MAX_DAYS, n - 1) + 1):
        streak = streak + 1 if clean(k) else 0
        if streak >= REST_DAYS:
            return k + 1, False
    if n > REST_MAX_DAYS:
        return REST_MAX_DAYS + 1, True
    return None, False


def _phase(n: int, start: int | None) -> str | None:
    if n == 0:
        return "ill"
    if start is None:
        return "rest"
    return "return" if n - start < RETURN_DAYS else None


def _alive(last: date, day: date, is_clean: Callable[[date], bool]) -> bool:
    """День day попадает на покой или возврат тяжёлой серии, закончившейся в last."""
    n = (day - last).days
    start, _ = _return_start(n, lambda k: is_clean(last + timedelta(days=k)))
    return _phase(n, start) in ("rest", "return")


def _series(
    days: dict[str, dict[str, Any]], today: date, is_clean: Callable[[date], bool]
) -> tuple[date, date, bool] | None:
    """Последняя серия болезни в окне: (первый день, последний день, тяжёлая)."""
    window = [today - timedelta(days=i) for i in range(EPISODE_DAYS - 1, -1, -1)]
    series: tuple[date, date, bool] | None = None
    for day in window:
        found = days.get(day.isoformat())
        if not found or not found["symptoms"]:
            continue
        severe = found["severe"]
        if series is not None:
            first, last, was_severe = series
            gap = (day - last).days - 1
            joined = gap <= GAP_MAX_DAYS or (was_severe and _alive(last, day, is_clean))
            if joined:
                series = (first, day, was_severe or severe)
                continue
        series = (day, day, severe)
    return series


def _reasons(record: bool, out: bool | None) -> list[str]:
    reasons = [] if record else ["no_record"]
    if out is None:
        reasons.append("no_night")
    elif out:
        reasons.append("corridor")
    return reasons


def episode_state(
    days: dict[str, dict[str, Any]], flags: Mapping[str, Mapping[str, bool | None]], today: str
) -> dict[str, Any]:
    """Фаза болезни на today (ill / rest / return / None) и счётчики; ключи всегда те же."""
    now = date.fromisoformat(today)

    def reasons_of(day: date) -> list[str]:
        iso = day.isoformat()
        return _reasons(days.get(iso, {}).get("record", False), flags.get(iso, {}).get("out"))

    def is_clean(day: date) -> bool:
        return not reasons_of(day)

    state: dict[str, Any] = {
        "phase": None,
        "severe": False,
        "sick_first": None,
        "sick_last": None,
        "clean_days": 0,
        "rest_day": None,
        "rest_step": None,
        "return_day": None,
        "until": None,
        "by_cap": False,
        "not_clean": [],
    }
    series = _series(days, now, is_clean)
    if series is None:
        return state
    first, last, severe = series
    state.update(severe=severe, sick_first=first.isoformat(), sick_last=last.isoformat())
    if not severe:
        return state
    n = (now - last).days
    start, by_cap = _return_start(n, lambda k: is_clean(last + timedelta(days=k)))
    state["phase"] = _phase(n, start)
    if state["phase"] == "rest":
        _fill_rest(state, n, last, now, reasons_of)
    elif state["phase"] == "return" and start is not None:
        state["return_day"] = n - start + 1
        state["until"] = (last + timedelta(days=start + RETURN_DAYS - 1)).isoformat()
        state["by_cap"] = by_cap
    return state


def _fill_rest(
    state: dict[str, Any],
    n: int,
    last: date,
    now: date,
    reasons_of: Callable[[date], list[str]],
) -> None:
    streak = 0
    for k in range(1, n):
        streak = streak + 1 if not reasons_of(last + timedelta(days=k)) else 0
    reasons = reasons_of(now)
    state["rest_day"] = n
    state["rest_step"] = streak + 1
    state["not_clean"] = reasons
    if not reasons:
        state["clean_days"] = streak + 1
    elif "corridor" not in reasons:
        state["clean_days"] = streak
