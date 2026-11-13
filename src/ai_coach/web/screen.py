"""GET /api/screen: часы экрана за день из ActivityWatch, живое чтение (шаг П6); в базу не пишет."""

import sqlite3
from datetime import date, datetime
from typing import Any

from ai_coach.workload.config import WorkloadConfigError, load_config
from ai_coach.workload.screen import AwReader, ScreenError, read_screen

KINDS = {
    "work": "screen_work_hours",
    "hobby": "screen_hobby_hours",
    "browser": "screen_browser_hours",
}


def screen_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """Часы работы, хобби и браузера за день или {"missing": "config" | "silent" | "empty"}
    (нет [screen] или битый конфиг / ActivityWatch не отвечает / за день нет событий окон).
    conn и now не нужны: сигнатура GET_VIEWS."""
    try:
        config = load_config()
    except WorkloadConfigError:
        return {"missing": "config"}
    if config.screen is None:
        return {"missing": "config"}
    try:
        rows, _ = read_screen(AwReader(config.screen), config.screen, day, day)
    except ScreenError:
        return {"missing": "silent"}
    if not rows:
        return {"missing": "empty"}
    hours = {row["kind"]: row["value"] for row in rows}
    return {name: hours.get(kind, 0.0) for name, kind in KINDS.items()}
