"""Счётчики из ~/.claude/todo.json: только чтение, в базу идут числа, не названия."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

CLOSED_STATES = ("done", "dropped")
SOURCE = "todo"


class TodoError(Exception):
    """todo.json не читается (битый JSON, не список)."""


def _records(path: Path) -> list[dict[str, Any]]:
    """Записи todo.json; нет файла - пусто."""
    if not path.is_file():
        return []
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise TodoError("todo не читается: не JSON") from None
    if not isinstance(data, list):
        raise TodoError("todo не читается: корень не список")
    return [cast(dict[str, Any], r) for r in cast(list[Any], data) if isinstance(r, dict)]


def active_items(path: Path) -> list[dict[str, Any]]:
    """Открытые пункты (состояние не done/dropped): id, title, state; doing первыми, затем по
    id. Нет файла - пусто."""
    items = [
        {"id": r.get("id"), "title": str(r.get("title") or ""), "state": str(r.get("state") or "")}
        for r in _records(path)
        if r.get("state") not in CLOSED_STATES
    ]
    return sorted(items, key=lambda item: (item["state"] != "doing", item["id"]))


def read_todo(path: Path, start: date, end: date, today: date) -> list[dict[str, Any]]:
    """Счётчики туду: todo_closed за каждый день start..end включительно (в том числе 0) и
    todo_open снимком на today. Закрытое (done/dropped) относится ко дню updated: updated
    ставится при добавлении и смене состояния. Подзадачи - обычные записи. Нет файла - пусто."""
    if not path.is_file():
        return []
    records = _records(path)
    closed = [str(r.get("updated") or "")[:10] for r in records if r.get("state") in CLOSED_STATES]
    opened = sum(1 for r in records if r.get("state") not in CLOSED_STATES)
    counters: list[dict[str, Any]] = []
    for offset in range((end - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        counters.append(
            {"date": day, "kind": "todo_closed", "value": closed.count(day), "source": SOURCE}
        )
    counters.append(
        {"date": today.isoformat(), "kind": "todo_open", "value": opened, "source": SOURCE}
    )
    return counters
