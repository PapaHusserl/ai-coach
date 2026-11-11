"""Карточка «Туду» в пульте (шаг П5): открытые пункты ~/.claude/todo.json и их правка.
Те же функции workload.todo, что у `coach todo`."""

import sqlite3
from datetime import date, datetime
from typing import Any

from ai_coach.web.errors import MarkError
from ai_coach.workload import (
    TodoError,
    WorkloadConfigError,
    add_item,
    edit_item,
    load_config,
    move_item,
)
from ai_coach.workload.todo import active_items

TODO_OPS = ("add", "edit", "move")
MOVE_STATES = ("doing", "todo", "done", "dropped")


def todo_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """GET /api/todo: только открытые пункты, doing первыми (conn, day, now не нужны);
    файл или конфиг не читается - пусто и текст в error."""
    try:
        return {"items": active_items(load_config().todo_path), "error": None}
    except (WorkloadConfigError, TodoError) as error:
        return {"items": [], "error": str(error)}


def _id(payload: dict[str, Any]) -> int:
    item_id = payload.get("id")
    if not isinstance(item_id, int) or isinstance(item_id, bool):
        raise MarkError("id: нужно число.")
    return item_id


def _text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise MarkError(f"{key}: нужна строка.")
    return value


def save_todo(conn: sqlite3.Connection, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    """POST /api/todo: op add | edit | move; ответ {id} у add, {} иначе."""
    op = payload.get("op")
    if op not in TODO_OPS:
        raise MarkError("op: add, edit или move.")
    try:
        path = load_config().todo_path
        if op == "add":
            title, note = _text(payload, "title"), _text(payload, "note")
            return {"id": add_item(path, title or "", note or "", now.date())}
        if op == "edit":
            title, note = _text(payload, "title"), _text(payload, "note")
            if title is None and note is None:
                raise MarkError("Нужен title или note.")
            edit_item(path, _id(payload), title, note)
            return {}
        state = payload.get("state")
        if state not in MOVE_STATES:
            raise MarkError("state: doing, todo, done или dropped.")
        move_item(path, _id(payload), state, now.date())
        return {}
    except (WorkloadConfigError, TodoError) as error:
        raise MarkError(str(error)) from None
