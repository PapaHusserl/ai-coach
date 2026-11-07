"""День для пульта: события тренера и встречи других календарей, текущие пункты, бар дня.
Читает базу, не пишет."""

import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

from ai_coach.agenda.service import agenda_rows
from ai_coach.store.workload import list_calendar_events
from ai_coach.workload.service import (
    _clip,  # pyright: ignore[reportPrivateUsage]
    _counted,  # pyright: ignore[reportPrivateUsage]
)

ITEM_FIELDS = ("id", "kind", "title", "start_at", "end_at", "all_day", "status", "note")
BIWEEKLY_DAYS = 14
SECONDS_IN_MINUTE = 60


def _on_day(row: dict[str, Any], day: date) -> bool:
    """Повтор, начатый раньше, выпадает на day: daily - каждый день, weekly - в тот же день
    недели, biweekly - через две недели."""
    if row["repeat"] is None or row["date"] >= day.isoformat():
        return True
    gap = (day - date.fromisoformat(row["date"])).days
    if row["repeat"] == "daily":
        return True
    return gap % (BIWEEKLY_DAYS if row["repeat"] == "biweekly" else 7) == 0


def _moved(row: dict[str, Any], day: date) -> dict[str, Any]:
    """Повтор, начатый раньше day, - то же время суток на day."""
    if row["repeat"] is None or row["date"] >= day.isoformat():
        return row
    start = datetime.fromisoformat(row["start_at"])
    shift = timedelta(days=(day - start.date()).days)
    end = datetime.fromisoformat(row["end_at"])
    values = {"start_at": (start + shift).isoformat(), "end_at": (end + shift).isoformat()}
    return {**row, **values}


def _items(conn: sqlite3.Connection, day: date) -> list[dict[str, Any]]:
    rows = [r for r in agenda_rows(conn, day.isoformat(), day.isoformat()) if _on_day(r, day)]
    rows = sorted((_moved(r, day) for r in rows), key=lambda r: (r["start_at"], r["id"]))
    return [{k: r[k] for k in ITEM_FIELDS} | {"repeat": r["repeat"]} for r in rows]


def _meetings(conn: sqlite3.Connection, day: date) -> list[dict[str, Any]]:
    midnight = datetime.combine(day, time.min)
    next_midnight = midnight + timedelta(days=1)
    before = (day - timedelta(days=1)).isoformat()
    found: list[dict[str, Any]] = []
    for e in list_calendar_events(conn, before, day.isoformat()):
        span = _clip(e, midnight, next_midnight) if _counted(e) else None
        if span:
            found.append(
                {
                    "id": e["id"],
                    "start_at": span[0].isoformat(),
                    "end_at": span[1].isoformat(),
                    "all_day": e["all_day"],
                    "title": e["title"],
                    "calendar": e["calendar"],
                }
            )
    return found


def _moment(row: dict[str, Any], key: str) -> datetime:
    return datetime.fromisoformat(row[key])


def day_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """День day на момент now: items (тренер), meetings (встречи), current (идущие сейчас),
    elapsed_min и left_min по рамке от самого раннего начала до самого позднего конца
    (all_day в рамку не входят, повтор своего дня входит)."""
    items = _items(conn, day)
    meetings = _meetings(conn, day)
    current = [
        (row["start_at"], source, row["id"])
        for source, rows in (("item", items), ("meeting", meetings))
        for row in rows
        if not row["all_day"] and _moment(row, "start_at") <= now < _moment(row, "end_at")
    ]
    framed = [r for r in items if not r["all_day"]]
    framed += [r for r in meetings if not r["all_day"]]
    elapsed = left = 0
    if framed:
        first = min(_moment(r, "start_at") for r in framed)
        last = max(_moment(r, "end_at") for r in framed)
        total = int((last - first).total_seconds() // SECONDS_IN_MINUTE)
        elapsed = min(max(int((now - first).total_seconds() // SECONDS_IN_MINUTE), 0), total)
        left = total - elapsed
    return {
        "date": day.isoformat(),
        "now": now.isoformat(timespec="seconds"),
        "items": items,
        "meetings": meetings,
        "current": [{"source": s, "id": i} for _, s, i in sorted(current)],
        "elapsed_min": elapsed,
        "left_min": left,
    }
