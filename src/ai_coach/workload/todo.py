"""~/.claude/todo.json: счётчики в базу (числа, не названия) и запись пунктов."""

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

CLOSED_STATES = ("done", "dropped")
SOURCE = "todo"
# Разрешённые переходы: модель скила whats-up (~/.claude/skills/whats-up/todo.py, MOVES).
MOVES: dict[str, tuple[str, ...]] = {
    "todo": ("doing", "done", "dropped"),
    "doing": ("todo", "done", "dropped"),
    "done": ("todo",),
    "dropped": ("todo",),
}


class TodoError(Exception):
    """todo.json не читается (битый JSON, не список) или правка невозможна."""


def _raw(path: Path) -> list[Any]:
    """Все элементы корневого списка todo.json как есть; нет файла - пусто."""
    if not path.is_file():
        return []
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise TodoError("todo не читается: не JSON") from None
    if not isinstance(data, list):
        raise TodoError("todo не читается: корень не список")
    return cast(list[Any], data)


def _records(path: Path) -> list[dict[str, Any]]:
    """Записи todo.json; нет файла - пусто."""
    return [cast(dict[str, Any], r) for r in _raw(path) if isinstance(r, dict)]


def _save(path: Path, data: list[Any]) -> None:
    """Атомарная запись: временный файл рядом и os.replace, формат как у скила."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _find(data: list[Any], item_id: int) -> dict[str, Any]:
    for r in data:
        if isinstance(r, dict) and cast(dict[str, Any], r).get("id") == item_id:
            return cast(dict[str, Any], r)
    raise TodoError(f"Нет задачи #{item_id}")


def _title(title: str) -> str:
    title = title.strip()
    if not title:
        raise TodoError("пустое название")
    return title


def add_item(path: Path, title: str, note: str, today: date) -> int:
    """Новый пункт в состоянии todo; id = max + 1. Возвращает id."""
    title = _title(title)
    data = _raw(path)
    ids = [
        i
        for r in data
        if isinstance(r, dict) and isinstance(i := cast(dict[str, Any], r).get("id"), int)
    ]
    new_id = max(ids, default=0) + 1
    day = today.isoformat()
    data.append(
        {
            "id": new_id,
            "title": title,
            "note": note,
            "state": "todo",
            "created": day,
            "updated": day,
        }
    )
    _save(path, data)
    return new_id


def move_item(path: Path, item_id: int, state: str, today: date) -> None:
    """Перевести пункт в состояние state по MOVES; updated = today."""
    data = _raw(path)
    record = _find(data, item_id)
    current = str(record.get("state") or "")
    allowed = MOVES.get(current, ())
    if state not in allowed:
        raise TodoError(f"Нельзя {current} -> {state} (можно: {', '.join(allowed)})")
    record["state"] = state
    record["updated"] = today.isoformat()
    _save(path, data)


def edit_item(path: Path, item_id: int, title: str | None, note: str | None) -> None:
    """Поменять название и/или заметку; updated не трогаем (закрытие остаётся в своём дне)."""
    data = _raw(path)
    record = _find(data, item_id)
    if title is not None:
        record["title"] = _title(title)
    if note is not None:
        record["note"] = note
    _save(path, data)


def active_items(path: Path, include_closed: bool = False) -> list[dict[str, Any]]:
    """Открытые пункты (состояние не done/dropped; с include_closed - все): id, title, note, state;
    doing первыми, затем по id. Нет файла - пусто."""
    items = [
        {
            "id": r.get("id"),
            "title": str(r.get("title") or ""),
            "note": str(r.get("note") or ""),
            "state": str(r.get("state") or ""),
        }
        for r in _records(path)
        if include_closed or r.get("state") not in CLOSED_STATES
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
