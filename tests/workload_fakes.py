"""Помощники для тестов нагрузки: подмена читателя календаря, файлы туду и груминга.

Всё синтетическое, macOS и EventKit не нужны.
"""

import hashlib
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any


def raw_event(**fields: Any) -> dict[str, Any]:
    """Событие так, как его отдаёт CalendarReader.read: время местное, без часового пояса."""
    base: dict[str, Any] = {
        "uid": "e1",
        "calendar": "Work",
        "title": "Синтетическая встреча",
        "start_at": "2026-10-07T10:00:00",
        "end_at": "2026-10-07T11:00:00",
        "all_day": False,
        "status": "confirmed",
        "my_status": "accepted",
        "raw_json": {},
    }
    return base | fields


def stored_event(category: str = "work", /, **fields: Any) -> dict[str, Any]:
    """Событие в виде, готовом для replace_calendar_window."""
    event = raw_event(**fields)
    event.setdefault("date", event["start_at"][:10])
    event["category"] = category
    event.setdefault("raw_json", {})
    event.setdefault("synced_at", "2026-10-08T10:00:00")
    return event


class FakeCalendar:
    """Подмена CalendarReader: read(start, end) -> события, чей день начала в окне."""

    def __init__(self, events: list[dict[str, Any]] | None = None, error: Exception | None = None):
        self.events = events or []
        self.error = error
        self.calls: list[tuple[date, date]] = []

    def read(self, date_from: date, date_to: date) -> list[dict[str, Any]]:
        self.calls.append((date_from, date_to))
        if self.error is not None:
            raise self.error
        return [
            e
            for e in self.events
            if date_from.isoformat() <= e["start_at"][:10] <= date_to.isoformat()
        ]


def write_config(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def write_todo(path: Path, items: list[dict[str, Any]]) -> Path:
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return path


def todo_item(
    item_id: int, state: str, updated: str, created: str = "2026-10-01"
) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": f"Синтетическая задача {item_id}",
        "note": "",
        "state": state,
        "created": created,
        "updated": updated,
    }


def write_hb(root: Path, done: dict[str, str], pending: dict[str, str]) -> Path:
    """Каталог hb-watch: {имя файла: 'YYYY-MM-DD HH:MM' mtime} для done/ и pending/."""
    for folder, files in (("done", done), ("pending", pending)):
        (root / folder).mkdir(parents=True, exist_ok=True)
        for name, stamp in files.items():
            path = root / folder / name
            path.write_text("pr: 1\n", encoding="utf-8")
            moment = datetime.strptime(stamp, "%Y-%m-%d %H:%M").timestamp()
            os.utime(path, (moment, moment))
    return root


def tree_state(*roots: Path) -> dict[str, tuple[str, float]]:
    """Хэш содержимого и mtime каждого файла под путями — для проверки «только чтение»."""
    state: dict[str, tuple[str, float]] = {}
    for root in roots:
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for p in files:
            state[str(p)] = (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime)
    return state


def coach_event(**fields: Any) -> dict[str, Any]:
    """Значения для store.agenda.add_event: черновик задачи «буду работать» (синтетика)."""
    base: dict[str, Any] = {
        "kind": "task",
        "title": "Синтетическая задача коуча",
        "date": "2026-10-10",
        "start_at": "2026-10-10T10:00:00",
        "end_at": "2026-10-10T12:00:00",
        "all_day": 0,
        "category": "work",
        "created_at": "2026-10-09T09:00:00",
    }
    return base | fields


class FakeCalendarWriter:
    """Подмена CalendarWriter: write(event) -> uid, remove(uid, future). Календарь не нужен.

    error - исключение на любой вызов; foreign - uid, которых нет в календаре коуча
    (remove по ним падает CalendarError, как у настоящего писателя)."""

    def __init__(self, error: Exception | None = None, foreign: tuple[str, ...] = ()):
        self.error = error
        self.foreign = foreign
        self.written: list[dict[str, Any]] = []
        self.removed: list[tuple[str, bool]] = []

    def write(self, event: dict[str, Any]) -> str:
        if self.error is not None:
            raise self.error
        self.written.append(dict(event))
        return f"fake-uid-{len(self.written)}"

    def remove(self, uid: str, future: bool = False) -> None:
        if self.error is not None:
            raise self.error
        if uid in self.foreign:
            from ai_coach.workload.calendar_eventkit import CalendarError

            raise CalendarError("событие не в календаре коуча")
        self.removed.append((uid, future))


class FlakyCommitConn:
    """Обёртка над соединением: первые `fail` вызовов commit() падают OperationalError."""

    def __init__(self, conn: Any, fail: int = 1):
        self._conn = conn
        self.fail = fail

    def commit(self) -> None:
        if self.fail > 0:
            self.fail -= 1
            raise sqlite3.OperationalError("disk I/O error")
        self._conn.commit()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)
