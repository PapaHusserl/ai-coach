"""Шаг П12, партия 2: agenda/forms.py — check_form (определение формы) и check_answers (ответы)."""

from typing import Any

import pytest

from ai_coach.agenda.draft import AgendaError
from ai_coach.agenda.forms import check_answers, check_form

SCORE = {"key": "score", "type": "scale", "label": "Самочувствие"}
TEMPERATURE = {
    "key": "temperature",
    "type": "number",
    "label": "Температура",
    "unit": "°C",
    "min": 34,
    "max": 43,
}
STOOL = {
    "key": "stool",
    "type": "choice",
    "label": "Стул",
    "options": ["норма", "жидкий", "твёрдый"],
}


def form(**extra: Any) -> dict[str, Any]:
    base = {"name": "temp", "title": "Температура", "fields": [SCORE, TEMPERATURE]}
    return base | extra


def with_field(**extra: Any) -> dict[str, Any]:
    """Форма с одним полем «Стул» (выбор), у которого правятся значения."""
    return form(fields=[STOOL | extra])


# check_form


def test_form_with_scale_and_number_is_accepted() -> None:
    check_form(form())


@pytest.mark.parametrize("name", ["my temp", "темп", "feel", "1temp", "a" * 25, ""])
def test_bad_form_name_is_refused(name: str) -> None:
    with pytest.raises(AgendaError):
        check_form(form(name=name))


def test_empty_title_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(title=" "))


def test_two_fields_with_one_key_are_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[TEMPERATURE, TEMPERATURE]))


def test_unknown_field_type_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[SCORE | {"type": "text"}]))


def test_form_without_fields_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[]))


def test_form_with_too_many_fields_is_refused() -> None:
    fields = [{"key": f"n{i}", "type": "yesno", "label": f"Вопрос {i}"} for i in range(9)]
    with pytest.raises(AgendaError):
        check_form(form(fields=fields))


def test_form_with_eight_fields_is_accepted() -> None:
    fields = [{"key": f"n{i}", "type": "yesno", "label": f"Вопрос {i}"} for i in range(8)]
    check_form(form(fields=fields))


def test_number_with_min_above_max_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[TEMPERATURE | {"min": 43, "max": 34}]))


def test_choice_with_three_options_is_accepted() -> None:
    check_form(with_field())


def test_choice_with_two_and_six_options_is_accepted() -> None:
    check_form(with_field(options=["да", "нет"]))
    check_form(with_field(options=[f"вариант {i}" for i in range(6)]))


@pytest.mark.parametrize(
    "options",
    [
        ["один"],
        [f"вариант {i}" for i in range(7)],
        ["норма", "норма"],
        ["норма", ""],
        ["норма", "в" * 25],
        [],
    ],
)
def test_bad_choice_options_are_refused(options: list[str]) -> None:
    with pytest.raises(AgendaError):
        check_form(with_field(options=options))


def test_choice_without_options_key_is_refused() -> None:
    field = {"key": "stool", "type": "choice", "label": "Стул"}
    with pytest.raises(AgendaError):
        check_form(form(fields=[field]))


def test_options_on_number_field_are_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[TEMPERATURE | {"options": ["а", "б"]}]))


# полюса шкалы, unit, required

MOOD = {"key": "mood", "type": "scale", "label": "Настроение", "low": "плохо", "high": "хорошо"}


def test_scale_with_poles_is_accepted() -> None:
    check_form(form(fields=[MOOD]))


def test_score_scale_without_poles_is_accepted() -> None:
    check_form(form(fields=[SCORE]))


@pytest.mark.parametrize("missing", ["low", "high"])
def test_scale_without_a_pole_is_refused(missing: str) -> None:
    field = {k: v for k, v in MOOD.items() if k != missing}
    with pytest.raises(AgendaError):
        check_form(form(fields=[field]))


def test_scale_without_poles_is_refused() -> None:
    field = {"key": "mood", "type": "scale", "label": "Настроение"}
    with pytest.raises(AgendaError):
        check_form(form(fields=[field]))


@pytest.mark.parametrize("pole", [{"low": ""}, {"high": " "}])
def test_scale_with_empty_pole_is_refused(pole: dict[str, str]) -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[MOOD | pole]))


@pytest.mark.parametrize("pole", ["low", "high"])
def test_score_with_a_pole_is_refused(pole: str) -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[SCORE | {pole: "как-то"}]))


@pytest.mark.parametrize(
    "field",
    [
        TEMPERATURE | {"low": "холодно"},
        TEMPERATURE | {"high": "жарко"},
        STOOL | {"low": "а"},
        {"key": "cough", "type": "yesno", "label": "Кашель", "high": "сильный"},
    ],
)
def test_poles_on_other_types_are_refused(field: dict[str, Any]) -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[field]))


@pytest.mark.parametrize(
    "field",
    [
        MOOD | {"unit": "балл"},
        STOOL | {"unit": "шт"},
        {"key": "cough", "type": "yesno", "label": "Кашель", "unit": "раз"},
        SCORE | {"unit": "балл"},
    ],
)
def test_unit_outside_number_is_refused(field: dict[str, Any]) -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[field]))


@pytest.mark.parametrize("required", [True, False])
def test_required_boolean_is_accepted(required: bool) -> None:
    check_form(form(fields=[TEMPERATURE | {"required": required}]))


# пределы длины: название 24, подпись поля 40, полюс 24, единица 8


def test_title_of_24_chars_is_accepted() -> None:
    check_form(form(title="н" * 24))


def test_title_of_25_chars_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(title="н" * 25))


def test_label_of_40_chars_is_accepted() -> None:
    check_form(form(fields=[TEMPERATURE | {"label": "п" * 40}]))


def test_label_of_41_chars_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[TEMPERATURE | {"label": "п" * 41}]))


@pytest.mark.parametrize("pole", ["low", "high"])
def test_pole_of_24_chars_is_accepted(pole: str) -> None:
    check_form(form(fields=[MOOD | {pole: "п" * 24}]))


@pytest.mark.parametrize("pole", ["low", "high"])
def test_pole_of_25_chars_is_refused(pole: str) -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[MOOD | {pole: "п" * 25}]))


def test_unit_of_8_chars_is_accepted() -> None:
    check_form(form(fields=[TEMPERATURE | {"unit": "е" * 8}]))


def test_unit_of_9_chars_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[TEMPERATURE | {"unit": "е" * 9}]))


@pytest.mark.parametrize("required", ["да", 1, 0, None, "false"])
def test_required_not_boolean_is_refused(required: Any) -> None:
    with pytest.raises(AgendaError):
        check_form(form(fields=[TEMPERATURE | {"required": required}]))


# тексты отказов: какое правило и в каком поле сработало (Н48, выжившие мутанты)

NO_TYPE = {"key": "mood", "type": "text", "label": "Настроение"}


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (form(name="my temp"), "name формы: латиница"),
        (form(name="feel"), "готового опросника"),
        (form(title=" "), "title формы: непустой текст до 24 знаков"),
        (form(fields=[]), "В форме от 1 до 8 полей"),
        (form(fields=None), "В форме от 1 до 8 полей"),
        (form(fields=[TEMPERATURE, TEMPERATURE]), "^Ключи полей не должны повторяться[.]$"),
        (form(fields=["temp"]), "Поле формы - объект"),
        (form(fields=[SCORE | {"key": "1"}]), "key поля: латиница"),
        (form(fields=[NO_TYPE]), r"mood: type из \['number'.*получено: 'text'"),
        (form(fields=[SCORE | {"type": "number"}]), "score: готовый вопрос, только type=scale"),
        (form(fields=[TEMPERATURE | {"label": " "}]), "temperature: label: непустой текст до 40"),
        (form(fields=[TEMPERATURE | {"required": "да"}]), "temperature: required - true или false"),
        (form(fields=[TEMPERATURE | {"unit": " "}]), "temperature: unit: непустой текст до 8"),
        (form(fields=[STOOL | {"unit": "шт"}]), "stool: unit только у number"),
        (form(fields=[SCORE | {"low": "а"}]), "score: low и high только у шкалы не score"),
        (
            form(fields=[{"key": "mood", "type": "scale", "label": "Настроение"}]),
            "mood: у шкалы нужны полюса low и high",
        ),
        (form(fields=[MOOD | {"low": " "}]), "mood: low: непустой текст до 24"),
    ],
)
def test_refusal_names_the_broken_rule(bad: dict[str, Any], message: str) -> None:
    with pytest.raises(AgendaError, match=message):
        check_form(bad)


# check_answers


FIELDS = [SCORE, TEMPERATURE, STOOL | {"required": False}]


def test_valid_answers_are_returned() -> None:
    answers = {"score": 4, "temperature": 37.2, "stool": "жидкий"}
    assert check_answers(FIELDS, answers) == answers


def test_integer_in_number_field_is_accepted() -> None:
    assert check_answers(FIELDS, {"score": 4, "temperature": 37})["temperature"] == 37


def test_optional_field_may_be_skipped() -> None:
    assert "stool" not in check_answers(FIELDS, {"score": 4, "temperature": 37.2})


@pytest.mark.parametrize("temperature", ["37.2", True, 33.9, 43.1, None])
def test_bad_number_is_refused(temperature: Any) -> None:
    with pytest.raises(AgendaError):
        check_answers(FIELDS, {"score": 4, "temperature": temperature})


@pytest.mark.parametrize("score", [0, 6, 4.5, "4", True])
def test_bad_scale_value_is_refused(score: Any) -> None:
    with pytest.raises(AgendaError):
        check_answers(FIELDS, {"score": score, "temperature": 37.2})


def test_missing_required_field_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_answers(FIELDS, {"score": 4})


def test_extra_key_is_refused() -> None:
    with pytest.raises(AgendaError):
        check_answers(FIELDS, {"score": 4, "temperature": 37.2, "pulse": 60})


@pytest.mark.parametrize("stool", ["иной", 1, ["норма", "жидкий"]])
def test_choice_outside_list_is_refused(stool: Any) -> None:
    with pytest.raises(AgendaError):
        check_answers(FIELDS, {"score": 4, "temperature": 37.2, "stool": stool})


def test_yesno_takes_boolean_only() -> None:
    fields = [{"key": "cough", "type": "yesno", "label": "Кашель"}]
    assert check_answers(fields, {"cough": False}) == {"cough": False}
    with pytest.raises(AgendaError):
        check_answers(fields, {"cough": "да"})
