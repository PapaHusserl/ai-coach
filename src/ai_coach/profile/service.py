"""Профиль спортсмена: проверка и запись значений, текущее состояние на дату.

Ручное значение главнее Garmin: Garmin берётся, только если ручного по ключу нет.
Функции записи НЕ делают commit (как в store). При ошибке проверки — ValueError.
"""

import sqlite3
from datetime import date
from typing import Any

from ai_coach.goals import list_goals
from ai_coach.profile.nutrition import NutritionInput, nutrition
from ai_coach.store.garmin_data import last_rest_hr, list_activities
from ai_coach.store.journal import list_weights
from ai_coach.store.profile import (
    add_profile_entry,
    last_garmin_entry,
    list_profile_entries,
)

SEX = ("m", "f")
ACTIVITY_LEVELS = ("sedentary", "light", "moderate", "active")
WEIGHT_GOALS = ("lose", "keep", "gain")
ENUMS = {"sex": SEX, "activity_level": ACTIVITY_LEVELS, "weight_goal": WEIGHT_GOALS}
TEXT_KEYS = ("injuries", "limitations", "equipment", "schedule", "preferences", "diet")
FLOAT_RANGES = {
    "height_cm": (100.0, 250.0),
    "weight": (20.0, 300.0),
    "target_weight_kg": (20.0, 300.0),
    "weekly_rate_kg": (0.05, 2.0),
}
INT_RANGES = {"max_hr": (100, 230), "kcal_target": (800, 6000)}
MAX_TEXT = 1000
MAX_AGE = 120
# Ключи, которые пишет только sync из Garmin или которые считаются сами
GARMIN_ONLY = ("weight",)
READ_ONLY = ("resting_hr",)
SETTABLE = (
    "sex",
    "birth_date",
    "height_cm",
    "activity_level",
    "max_hr",
    *TEXT_KEYS,
    "target_weight_kg",
    "weight_goal",
    "weekly_rate_kg",
    "kcal_target",
)
# Обязательные ключи для опроса; вес — отдельно (weight_log или Garmin)
REQUIRED = (
    "sex",
    "birth_date",
    "height_cm",
    "weight",
    "activity_level",
    "schedule",
    "equipment",
    "injuries",
    "weight_goal",
)


def _enum(key: str, text: str, allowed: tuple[str, ...]) -> str:
    if text not in allowed:
        raise ValueError(f"{key}: допустимо {', '.join(allowed)}, получено {text!r}")
    return text


def _birth_date(text: str, today: date) -> str:
    try:
        born = date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"birth_date: нужна дата YYYY-MM-DD, получено {text!r}") from None
    if not 0 <= _age(born, today) <= MAX_AGE:
        raise ValueError(f"birth_date: дата вне разумного диапазона, получено {text!r}")
    return born.isoformat()


def _number(key: str, text: str) -> float:
    try:
        return float(text.replace(",", "."))
    except ValueError:
        raise ValueError(f"{key}: нужно число, получено {text!r}") from None


def _canonical(number: float) -> str:
    return str(int(number)) if number == int(number) else str(number)


def _text(key: str, text: str) -> str:
    if not text or len(text) > MAX_TEXT:
        raise ValueError(f"{key}: текст от 1 до {MAX_TEXT} символов")
    return text


def _numeric(key: str, text: str) -> str:
    number = _number(key, text)
    if key in FLOAT_RANGES:
        low, high = FLOAT_RANGES[key]
        if not low <= number <= high:
            raise ValueError(f"{key}: от {low:g} до {high:g}, получено {text!r}")
        return _canonical(number)
    low, high = INT_RANGES[key]
    if not low <= number <= high or number != int(number):
        raise ValueError(f"{key}: целое от {low} до {high}, получено {text!r}")
    return _canonical(number)


def check_value(key: str, value: str, today: date) -> str:
    """Проверенное значение в каноническом виде (текст для базы). Неизвестный ключ,
    ключ только для чтения или плохое значение — ValueError."""
    text = value.strip()
    if key in READ_ONLY:
        raise ValueError(f"{key}: только чтение, берётся из Garmin")
    if key not in SETTABLE and key not in GARMIN_ONLY:
        raise ValueError(f"Неизвестный ключ {key!r}. Допустимые: {', '.join(SETTABLE)}")
    if key in ENUMS:
        return _enum(key, text, ENUMS[key])
    if key == "birth_date":
        return _birth_date(text, today)
    if key in TEXT_KEYS:
        return _text(key, text)
    return _numeric(key, text)


def typed(key: str, text: str) -> Any:
    """Значение из базы: числа — числами, остальное — текстом."""
    if key in FLOAT_RANGES:
        return float(text)
    if key in INT_RANGES:
        return int(text)
    return text


def set_value(
    conn: sqlite3.Connection,
    key: str,
    value: str,
    source: str,
    now: str,
    raw: Any = None,
) -> bool:
    """Проверка и одна запись в profile_log. True — записано. То же значение из Garmin
    повторно не пишется (sync идемпотентен), вернётся False. Вес вручную не задаётся —
    это `coach weight`."""
    if source not in ("manual", "garmin"):
        raise ValueError(f"source: manual или garmin, получено {source!r}")
    if source == "manual" and key in GARMIN_ONLY:
        raise ValueError("Вес записывается командой coach weight")
    checked = check_value(key, value, date.fromisoformat(now[:10]))
    if source == "garmin":
        last = last_garmin_entry(conn, key)
        if last is not None and last["value"] == checked:
            return False
    values = {"key": key, "value": checked, "source": source, "logged_at": now, "raw_json": raw}
    add_profile_entry(conn, values)
    return True


def _age(born: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (born.month, born.day)
    return today.year - born.year - (0 if had_birthday else 1)


def _current_entries(conn: sqlite3.Connection, day: str) -> dict[str, dict[str, Any]]:
    """key -> {value, source, logged_at} на конец дня: последняя ручная запись, иначе
    последняя из Garmin."""
    manual: dict[str, dict[str, Any]] = {}
    garmin: dict[str, dict[str, Any]] = {}
    for row in list_profile_entries(conn, day):
        found = manual if row["source"] == "manual" else garmin
        found[row["key"]] = row
    result: dict[str, dict[str, Any]] = {}
    for key, row in {**garmin, **manual}.items():
        value = typed(key, row["value"])
        result[key] = {"value": value, "source": row["source"], "logged_at": row["logged_at"]}
    return result


def _weight_kg(conn: sqlite3.Connection, day: str, values: dict[str, Any]) -> dict[str, Any] | None:
    """Вес {value, source, logged_at}: свежее из последнего weight_log (manual) и Garmin
    (ключ weight); при равных временах — ручной."""
    weights = list_weights(conn, "0000-01-01", day)
    garmin = values.get("weight")
    if not weights:
        return garmin
    last = weights[-1]
    manual = {"value": last["weight_kg"], "source": "manual", "logged_at": last["measured_at"]}
    if garmin is None:
        return manual
    newer = last["measured_at"].replace("T", " ") >= garmin["logged_at"].replace("T", " ")
    return manual if newer else garmin


def current_profile(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Профиль на конец дня day (YYYY-MM-DD): values — key -> {value, source, logged_at};
    age (из birth_date) и weight_kg — вычисляемые, None если данных нет; missing — пустые
    обязательные ключи, плюс "goals", если нет активных целей."""
    values = _current_entries(conn, day)
    age = None
    if "birth_date" in values:
        age = _age(date.fromisoformat(values["birth_date"]["value"]), date.fromisoformat(day))
    weight = _weight_kg(conn, day, values)
    if weight is not None:
        values["weight"] = weight
    weight_kg = weight["value"] if weight is not None else None
    missing = [key for key in REQUIRED if key not in values]
    if not list_goals(conn, "active"):
        missing.append("goals")
    return {"values": values, "age": age, "weight_kg": weight_kg, "missing": missing}


def resting_hr(conn: sqlite3.Connection, day: str) -> int | None:
    """Пульс покоя из сна Garmin (последний на день), только чтение."""
    found = last_rest_hr(conn, day)
    return found[1] if found else None


def profile_history(conn: sqlite3.Connection, day: str) -> dict[str, list[dict[str, Any]]]:
    """Все записи профиля до конца дня day по ключам, по времени; без raw_json."""
    result: dict[str, list[dict[str, Any]]] = {}
    for row in list_profile_entries(conn, day):
        item = {k: row[k] for k in ("value", "source", "logged_at")}
        result.setdefault(row["key"], []).append(item)
    return result


def profile_nutrition(
    conn: sqlite3.Connection, day: str, current: dict[str, Any]
) -> dict[str, Any]:
    """КБЖУ-цель на день (nutrition.nutrition) по текущему профилю; калории активностей дня —
    сумма calories из activities."""
    values = current["values"]

    def value(key: str) -> Any:
        return values[key]["value"] if key in values else None

    day_activities = list_activities(conn, day, day)
    burned = sum(a["calories"] or 0 for a in day_activities)
    minutes = sum((a["duration_s"] or 0) / 60 for a in day_activities)
    return nutrition(
        NutritionInput(
            sex=value("sex"),
            age=current["age"],
            height_cm=value("height_cm"),
            weight_kg=current["weight_kg"],
            activity_level=value("activity_level"),
            weight_goal=value("weight_goal"),
            weekly_rate_kg=value("weekly_rate_kg"),
            kcal_target=value("kcal_target"),
            activity_kcal=burned,
            activity_minutes=minutes,
        )
    )
