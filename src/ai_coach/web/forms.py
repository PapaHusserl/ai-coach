"""Форма под пунктом из пульта: определение формы и запись ответа (чтение - day_marks.py)."""

import json
import sqlite3
from typing import Any, cast

from ai_coach.agenda.draft import FORM_PREFIX, AgendaError
from ai_coach.agenda.forms import check_answers
from ai_coach.store.forms import add_form_entry, get_form
from ai_coach.store.journal import add_wellbeing
from ai_coach.web.errors import MarkError
from ai_coach.web.survey import is_form

SCORE = "score"  # готовое поле «Самочувствие»: оценка и текст идут в журнал самочувствия


def form_view(conn: sqlite3.Connection, survey: str | None) -> dict[str, Any] | None:
    """Определение формы пункта {name, title, fields}, в том числе снятой; нет формы - None."""
    if survey is None or not is_form(survey):
        return None
    row = get_form(conn, survey.removeprefix(FORM_PREFIX))
    if row is None:
        return None
    return {"name": row["name"], "title": row["title"], "fields": json.loads(row["fields_json"])}


def save_form(
    conn: sqlite3.Connection, payload: dict[str, Any], base: dict[str, Any], survey: str | None
) -> int:
    """Записать ответ формы (без commit): все проверки до первой записи. Поле score и текст -
    запись самочувствия, остальное - form_log; id строки form_log."""
    form = form_view(conn, survey)
    if form is None:
        raise MarkError("У этого пункта нет такой отметки.")
    given = payload.get("values")
    if not isinstance(given, dict):
        raise MarkError("values: нужен объект с ответами.")
    try:
        answers = check_answers(form["fields"], cast(dict[str, Any], given))
    except AgendaError as error:
        raise MarkError(f"Ответ формы не принят: {error}") from None
    raw = payload.get("text")
    text = raw.strip() if isinstance(raw, str) else ""
    wellbeing_id = None
    if SCORE in answers:
        wellbeing_id = add_wellbeing(conn, {**base, "score": answers.pop(SCORE), "text": text})
    entry = {
        "date": base["date"],
        "time": base["logged_at"][11:],
        "event_id": base["event_id"],
        "form": form["name"],
        "values_json": json.dumps(answers, ensure_ascii=False),
        "text": None if wellbeing_id else text or None,
        "wellbeing_id": wellbeing_id,
    }
    return add_form_entry(conn, entry)
