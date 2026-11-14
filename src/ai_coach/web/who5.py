"""WHO-5 из пульта: запись замера чек-ина с опросником who5 и замер дня для строки пункта."""

import sqlite3
from typing import Any

from ai_coach.load.who5 import ITEM_MAX, ITEM_MIN, ITEMS_COUNT, who5_score
from ai_coach.store.journal import add_who5, list_who5
from ai_coach.web.errors import MarkError


def _answer(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not ITEM_MIN <= value <= ITEM_MAX:
        raise MarkError(f"{name}: от {ITEM_MIN} до {ITEM_MAX}.")
    return value


def save_who5(conn: sqlite3.Connection, payload: dict[str, Any], base: dict[str, Any]) -> int:
    """Записать замер WHO-5 (без commit): q1-q5 целые ITEM_MIN..ITEM_MAX, балл как у coach who5;
    дата и время - из base (день пункта); id строки who5_log."""
    if who5_view(conn, base["date"]):
        raise MarkError("WHO-5 за день уже записан.")
    names = [f"q{n}" for n in range(1, ITEMS_COUNT + 1)]
    answers = [_answer(name, payload.get(name)) for name in names]
    text = payload.get("text")
    values = {
        "date": base["date"],
        "logged_at": base["logged_at"],
        **dict(zip(names, answers, strict=True)),
        "score": who5_score(answers),
        "text": text.strip() or None if isinstance(text, str) else None,
    }
    return add_who5(conn, values)


def who5_view(conn: sqlite3.Connection, day: str) -> dict[str, Any] | None:
    """Последний замер WHO-5 дня day (из пульта или от тренера): score, logged_at; нет - None."""
    found = list_who5(conn, day, day)
    if not found:
        return None
    last = found[-1]
    return {"score": last["score"], "logged_at": last["logged_at"]}
