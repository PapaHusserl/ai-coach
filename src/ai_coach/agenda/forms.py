"""Формы тренера: проверка определения (check_form) и ответов пользователя (check_answers).

Определение: name (латиница, цифры, _, с буквы, до MAX_NAME знаков, не имя готового опросника),
title, fields - от 1 до MAX_FIELDS полей {key, type, label, required?, unit?, min?, max?,
low?, high?, options?}. Типы FIELD_TYPES: number (с границами min, max и единицей unit), scale
(целое 1-5; полюса low и high обязательны, у score не задаются), yesno, choice (один вариант из
OPTIONS_MIN-OPTIONS_MAX, подпись до OPTION_MAX знаков). Ключ score - только шкала.
"""

import math
import re
from typing import Any, cast

from ai_coach.agenda.draft import SURVEYS, AgendaError

MIN_SCORE = 1
MAX_SCORE = 5
FIELD_TYPES = ("number", "scale", "yesno", "choice")
KNOWN_FIELDS = ("score",)  # готовые вопросы: score - «Самочувствие» из журнала самочувствия
MAX_NAME = 24
MAX_FIELDS = 8
MAX_TITLE = 24
MAX_LABEL = 40
MAX_POLE = 24
MAX_UNIT = 8
OPTIONS_MIN = 2
OPTIONS_MAX = 6
OPTION_MAX = 24
IDENT = re.compile(rf"[A-Za-z][A-Za-z0-9_]{{0,{MAX_NAME - 1}}}")


def _ident(value: Any, what: str) -> str:
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise AgendaError(
            f"{what}: латиница, цифры и _, с буквы, до {MAX_NAME} знаков, получено: {value!r}"
        )
    return value


def _text(value: Any, what: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AgendaError(f"{what}: непустой текст до {limit} знаков, получено: {value!r}")


def _options(field: dict[str, Any]) -> None:
    raw: Any = field.get("options")
    if field["type"] != "choice":
        if raw is not None:
            raise AgendaError(f"{field['key']}: options только у choice.")
        return
    options = cast(list[Any], raw) if isinstance(raw, list) else []
    if not OPTIONS_MIN <= len(options) <= OPTIONS_MAX:
        raise AgendaError(f"{field['key']}: у choice от {OPTIONS_MIN} до {OPTIONS_MAX} вариантов.")
    for option in options:
        _text(option, f"{field['key']}: вариант", OPTION_MAX)
    if len(set(options)) < len(options):
        raise AgendaError(f"{field['key']}: варианты не должны повторяться.")


def _poles(field: dict[str, Any]) -> None:
    """Полюса шкалы: у scale low и high обязательны, у score не задаются; у остальных - отказ."""
    key = field["key"]
    poles = [name for name in ("low", "high") if name in field]
    if field["type"] != "scale" or key in KNOWN_FIELDS:
        if poles:
            raise AgendaError(f"{key}: low и high только у шкалы не score.")
        return
    if len(poles) < 2:
        raise AgendaError(f"{key}: у шкалы нужны полюса low и high.")
    for name in poles:
        _text(field[name], f"{key}: {name}", MAX_POLE)


def _number_limits(field: dict[str, Any]) -> None:
    low, high = field.get("min"), field.get("max")
    for bound in (low, high):
        if bound is not None and (isinstance(bound, bool) or not isinstance(bound, int | float)):
            raise AgendaError(f"{field['key']}: min и max - числа, получено: {bound!r}")
    if low is not None and high is not None and low > high:
        raise AgendaError(f"{field['key']}: min больше max.")


def _field(given: Any) -> str:
    if not isinstance(given, dict):
        raise AgendaError(f"Поле формы - объект, получено: {given!r}")
    field = cast(dict[str, Any], given)
    key = _ident(field.get("key"), "key поля")
    if field.get("type") not in FIELD_TYPES:
        raise AgendaError(f"{key}: type из {list(FIELD_TYPES)}, получено: {field.get('type')!r}")
    if key in KNOWN_FIELDS and field["type"] != "scale":
        raise AgendaError(f"{key}: готовый вопрос, только type=scale.")
    _text(field.get("label"), f"{key}: label", MAX_LABEL)
    if "required" in field and not isinstance(field["required"], bool):
        raise AgendaError(f"{key}: required - true или false.")
    _options(field)
    _poles(field)
    if field["type"] == "number":
        _number_limits(field)
        if "unit" in field:
            _text(field["unit"], f"{key}: unit", MAX_UNIT)
    elif "unit" in field:
        raise AgendaError(f"{key}: unit только у number.")
    return key


def check_form(form: dict[str, Any]) -> None:
    """Определение формы (name, title, fields) годится, иначе AgendaError."""
    if _ident(form.get("name"), "name формы") in SURVEYS:
        raise AgendaError(f"name формы не может быть именем готового опросника {list(SURVEYS)}.")
    _text(form.get("title"), "title формы", MAX_TITLE)
    raw: Any = form.get("fields")
    fields = cast(list[Any], raw) if isinstance(raw, list) else []
    if not 1 <= len(fields) <= MAX_FIELDS:
        raise AgendaError(f"В форме от 1 до {MAX_FIELDS} полей.")
    keys = [_field(field) for field in fields]
    if len(set(keys)) < len(keys):
        raise AgendaError("Ключи полей не должны повторяться.")


def _within(field: dict[str, Any], value: float) -> bool:
    low, high = field.get("min"), field.get("max")
    return (low is None or value >= low) and (high is None or value <= high)


def _answer(field: dict[str, Any], value: Any) -> Any:
    key, kind = field["key"], field["type"]
    if kind == "yesno":
        ok = isinstance(value, bool)
    elif kind == "choice":
        ok = isinstance(value, str) and value in field["options"]
    elif kind == "scale":
        ok = isinstance(value, int) and not isinstance(value, bool)
        ok = ok and MIN_SCORE <= value <= MAX_SCORE
    else:
        ok = isinstance(value, int | float) and not isinstance(value, bool)
        ok = ok and math.isfinite(value)
        ok = ok and _within(field, value)
    if not ok:
        raise AgendaError(f"{key}: ответ не подходит полю ({kind}), получено: {value!r}")
    return value


def check_answers(fields: list[dict[str, Any]], answers: dict[str, Any]) -> dict[str, Any]:
    """Ответы по полям формы: тип, границы, вариант из списка, обязательность (required, по
    умолчанию да); лишний ключ - отказ. Возвращает ответы без пропущенных необязательных."""
    known = {field["key"] for field in fields}
    extra = sorted(set(answers) - known)
    if extra:
        raise AgendaError(f"В форме нет полей: {extra}.")
    result: dict[str, Any] = {}
    for field in fields:
        if field["key"] in answers:
            result[field["key"]] = _answer(field, answers[field["key"]])
        elif field.get("required", True):
            raise AgendaError(f"{field['key']}: обязательное поле.")
    return result
