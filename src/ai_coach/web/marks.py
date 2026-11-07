"""Отметки к пункту плана из пульта: те же store-функции, что у команд тренера, плюс event_id."""

import sqlite3
from datetime import date, datetime
from typing import Any

from ai_coach.store.agenda import ACTIVE, get_event, mark_done, unmark_done
from ai_coach.store.journal import add_focus, add_slip, add_wellbeing
from ai_coach.store.workload import upsert_counter
from ai_coach.web.day import moved, on_day

ALLOWED = {
    "task": ("rating", "feel", "slip"),
    "focus": ("rating", "feel", "slip"),
    "practice": ("done", "feel", "slip"),
    "rest": ("done", "feel", "slip"),
    "checkin": ("checkin",),
}
MIN_SCORE = 1
MAX_SCORE = 5
MAX_HOURS = 24  # как cli/main.py MAX_HOURS
HOURS = ("work", "hobby", "rest")
CHECKIN_SCORES = {
    "mood": "mood",
    "stress": "stress",
    "thoughts": "work_thoughts",
    "hindrance": "hindrance",
    "valuable": "valuable",
}


class MarkError(ValueError):
    """Отметку нельзя записать; текст - пользователю."""


class NoEvent(MarkError):
    """Пункта нет (или он отменён)."""


def _score(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_SCORE <= value <= MAX_SCORE:
        raise MarkError(f"{name}: от {MIN_SCORE} до {MAX_SCORE}.")
    return value


def _optional_score(name: str, payload: dict[str, Any]) -> int | None:
    value = payload.get(name)
    return None if value is None else _score(name, value)


def _hours(name: str, value: Any) -> float:
    ok = isinstance(value, int | float) and not isinstance(value, bool)
    if not ok or not 0 <= value <= MAX_HOURS:
        raise MarkError(f"Часы ({name}) должны быть числом от 0 до {MAX_HOURS}.")
    return float(value)


def _text(payload: dict[str, Any], required: bool = False) -> str:
    value = payload.get("text")
    text = value.strip() if isinstance(value, str) else ""
    if required and not text:
        raise MarkError("Текст не может быть пустым.")
    return text


def _event(conn: sqlite3.Connection, payload: dict[str, Any]) -> tuple[dict[str, Any], date]:
    """Живой пункт и день: повтор - только в свой день."""
    event_id = payload.get("event_id")
    row = get_event(conn, event_id) if isinstance(event_id, int) else None
    if row is None or row["status"] not in ACTIVE:
        raise NoEvent("Пункта нет.")
    try:
        day = date.fromisoformat(str(payload.get("date")))
    except ValueError:
        raise MarkError("date: нужна дата YYYY-MM-DD.") from None
    if not on_day(row, day):
        raise MarkError("Пункта в этот день нет.")
    return moved(row, day), day


def _kinds(row: dict[str, Any], mark: Any) -> None:
    kinds = ALLOWED.get(row["kind"])
    if kinds is None:
        raise MarkError("У этого пункта пока нет окна отметок.")
    if mark not in kinds:
        raise MarkError("У этого пункта нет такой отметки.")


def _checkin(conn: sqlite3.Connection, payload: dict[str, Any], base: dict[str, Any]) -> int:
    flow = payload.get("flow")
    if flow is not None and not (type(flow) is int and flow in (0, 1)):
        raise MarkError("flow: 0 или 1.")
    values = {
        **base,
        "score": _score("score", payload.get("score")),
        "text": _text(payload),
        "flow": flow,
    }
    for name, column in CHECKIN_SCORES.items():
        values[column] = _optional_score(name, payload)
    hours = {k: _hours(k, payload[k]) for k in HOURS if payload.get(k) is not None}
    wellbeing_id = add_wellbeing(conn, values)
    for kind, value in hours.items():
        counter = {"date": base["date"], "kind": f"{kind}_hours", "value": value}
        upsert_counter(conn, {**counter, "source": "manual", "synced_at": base["logged_at"]})
    return wellbeing_id


def save_mark(conn: sqlite3.Connection, payload: dict[str, Any], now: datetime) -> int | None:
    """Записать отметку пункта (без commit); id строки, у done - None. date - день пункта,
    logged_at - min(сейчас, конец пункта): у прошедшего пункта - его конец."""
    row, day = _event(conn, payload)
    mark = payload.get("mark")
    _kinds(row, mark)
    if datetime.fromisoformat(row["start_at"]) > now:
        raise MarkError("Пункт ещё не начался.")
    moment = min(now, datetime.fromisoformat(row["end_at"])).isoformat(sep=" ", timespec="seconds")
    base = {"event_id": row["id"], "date": day.isoformat(), "logged_at": moment}
    if mark == "done":
        done = payload.get("done")
        if done is None:
            unmark_done(conn, row["id"], base["date"])
        elif type(done) is int and done in (0, 1):
            mark_done(conn, row["id"], base["date"], done, moment)
        else:
            raise MarkError("done: 1, 0 или null.")
        return None
    if mark == "rating":
        scores = {k: _score(k, payload.get(k)) for k in ("focus", "fatigue", "effort")}
        return add_focus(conn, {**base, **scores, "text": _text(payload)})
    if mark == "feel":
        values = {**base, "score": _score("score", payload.get("score")), "text": _text(payload)}
        return add_wellbeing(conn, values)
    if mark == "slip":
        return add_slip(conn, {**base, "text": _text(payload, required=True)})
    return _checkin(conn, payload, base)
