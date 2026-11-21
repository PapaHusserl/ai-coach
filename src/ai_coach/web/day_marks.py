"""Чтение отметок дня: что отмечено у пунктов и какие пункты красные (запись — web/marks.py)."""

import json
import sqlite3
from typing import Any

from ai_coach.store.agenda import list_done
from ai_coach.store.forms import list_form_log
from ai_coach.store.journal import list_focus, list_food, list_slip, list_wellbeing
from ai_coach.web.marks import COOKING
from ai_coach.web.survey import checkin_due, is_form


def empty_marks() -> dict[str, Any]:
    return {"ratings": [], "feel": [], "slips": [], "done": None, "food": [], "forms": []}


def marks_for_day(conn: sqlite3.Connection, day: str) -> dict[int, dict[str, Any]]:
    """Отметки дня по пунктам: event_id -> ratings, feel, slips, food, forms (по времени), done
    (None - нет). Самочувствие, на которое ссылается ответ формы, лежит в forms, не в feel."""
    found: dict[int, dict[str, Any]] = {}

    def of(event_id: int) -> dict[str, Any]:
        return found.setdefault(event_id, empty_marks())

    for r in list_focus(conn, day, day):
        if r["event_id"] is not None:
            keys = ("focus", "fatigue", "effort", "text", "logged_at")
            of(r["event_id"])["ratings"].append({k: r[k] for k in keys})
    answers = list_form_log(conn, day, day)
    of_forms = {r["wellbeing_id"] for r in answers}
    for r in answers:
        entry = {"values": json.loads(r["values_json"]), "score": r["score"], "text": r["text"]}
        of(r["event_id"])["forms"].append({**entry, "logged_at": f"{r['date']} {r['time']}"})
    for r in list_wellbeing(conn, day, day):
        if r["event_id"] is not None and r["id"] not in of_forms:
            keys = ("score", "text", "mood", "stress", "fatigue", "irritability", "logged_at")
            of(r["event_id"])["feel"].append({k: r[k] for k in keys})
    for r in list_slip(conn, day, day):
        if r["event_id"] is not None:
            of(r["event_id"])["slips"].append({k: r[k] for k in ("text", "logged_at")})
    for r in list_done(conn, day, day):
        of(r["event_id"])["done"] = {"done": r["done"], "logged_at": r["logged_at"]}
    for r in list_food(conn, day, day):
        if r["event_id"] is not None:
            keys = ("id", "text", "kcal", "logged_at")
            of(r["event_id"])["food"].append({k: r[k] for k in keys})
    return found


def due(
    kind: str,
    marks: dict[str, Any],
    evening: bool,
    past: bool,
    title: str = "",
    fact: dict[str, Any] | None = None,
    survey: str | None = None,
    who5: bool = False,
) -> bool:
    """Прошедший заполняемый пункт без отметки (красный): task/focus - нет оценки, practice/rest -
    нет «сделал/пропустил», training - то же и нет факта Garmin done/different (Р3), meal - нет
    записи еды (у «Готовки» окна нет), checkin - нет отметки его опросника (web/survey.py)."""
    no_done = marks["done"] is None
    no_rating = not marks["ratings"]
    missing = {
        "task": no_rating,
        "focus": no_rating,
        "practice": no_done,
        "rest": no_done,
        "training": no_done and (fact is None or fact["kind"] == "skipped"),
        "meal": title != COOKING and not marks["food"],
        "checkin": checkin_due(survey, marks, evening, who5),
    }
    no_form = is_form(survey) and not marks["forms"] and not (kind == "meal" and title == COOKING)
    return past and (missing.get(kind, False) or no_form)
