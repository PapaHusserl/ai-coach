"""День для пульта: события тренера и встречи других календарей, текущие пункты, бар дня.
Читает базу, не пишет."""

import json
import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

from ai_coach.agenda.service import agenda_rows
from ai_coach.profile.service import current_profile, profile_nutrition
from ai_coach.store.agenda import own_uids
from ai_coach.store.journal import evening_done
from ai_coach.store.plans import get_planned_workout
from ai_coach.store.workload import list_calendar_events
from ai_coach.web.food import meal_view, offers_view
from ai_coach.web.header import header_view
from ai_coach.web.marks import COOKING, due, empty_marks, marks_for_day
from ai_coach.web.repeat import moved, on_day
from ai_coach.web.training import fact, plan_view
from ai_coach.workload.service import (
    _clip,  # pyright: ignore[reportPrivateUsage]
    _counted,  # pyright: ignore[reportPrivateUsage]
)

ITEM_FIELDS = (
    "id",
    "kind",
    "title",
    "start_at",
    "end_at",
    "all_day",
    "status",
    "note",
    "workout_id",
)
SECONDS_IN_MINUTE = 60


def _training(conn: sqlite3.Connection, row: dict[str, Any], day: date) -> dict[str, Any] | None:
    """План и факт тренировки пункта; у пункта без тренировки в плане - None."""
    workout = get_planned_workout(conn, row["workout_id"]) if row["workout_id"] else None
    if row["kind"] != "training" or workout is None:
        return None
    return {"plan": plan_view(workout), "fact": fact(conn, workout["id"], day.isoformat())}


def _items(conn: sqlite3.Connection, day: date, now: datetime) -> list[dict[str, Any]]:
    """Пункты тренера дня; у каждого marks (отметки пункта за день) и due (красный)."""
    rows = [r for r in agenda_rows(conn, day.isoformat(), day.isoformat()) if on_day(r, day)]
    rows = sorted((moved(r, day) for r in rows), key=lambda r: (r["start_at"], r["id"]))
    marks = marks_for_day(conn, day.isoformat())
    evening = evening_done(conn, day.isoformat())
    meal = None
    items: list[dict[str, Any]] = []
    for r in rows:
        mine = marks.get(r["id"], empty_marks())
        past = _moment(r, "end_at") <= now
        item = {k: r[k] for k in ITEM_FIELDS} | {"repeat": r["repeat"]}
        training = _training(conn, r, day)
        garmin = training["fact"] if training else None
        item |= {"marks": mine, "due": due(r["kind"], mine, evening, past, r["title"], garmin)}
        if training:
            item["training"] = training
        if r["kind"] == "meal" and r["title"] != COOKING:
            if meal is None:  # остаток один на день, не на пункт
                target = profile_nutrition(
                    conn, day.isoformat(), current_profile(conn, day.isoformat())
                )
                meal = meal_view(conn, day.isoformat(), target)
            item["meal"] = {
                **meal,
                "food": mine["food"],
                "offers": offers_view(conn, r["id"], day.isoformat()),
            }
        items.append(item)
    return items


def recurring(event: dict[str, Any]) -> bool:
    """Повторяется ли событие календаря (по raw_json снимка; нет сведений - нет)."""
    raw: dict[str, Any] = json.loads(event["raw_json"]) if event["raw_json"] else {}
    return bool(raw.get("recurring"))


def _meetings(conn: sqlite3.Connection, day: date) -> list[dict[str, Any]]:
    midnight = datetime.combine(day, time.min)
    next_midnight = midnight + timedelta(days=1)
    before = (day - timedelta(days=1)).isoformat()
    found: list[dict[str, Any]] = []
    own = own_uids(conn)
    for e in list_calendar_events(conn, before, day.isoformat()):
        span = _clip(e, midnight, next_midnight) if _counted(e) and e["uid"] not in own else None
        if span:
            found.append(
                {
                    "id": e["id"],
                    "start_at": span[0].isoformat(),
                    "end_at": span[1].isoformat(),
                    "all_day": e["all_day"],
                    "title": e["title"],
                    "calendar": e["calendar"],
                    "recurring": recurring(e),
                    "editable": e["my_status"] is None,
                }
            )
    return found


def _moment(row: dict[str, Any], key: str) -> datetime:
    return datetime.fromisoformat(row[key])


def day_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """День day на момент now: items (тренер), meetings (встречи), current (идущие сейчас),
    elapsed_min и left_min по рамке от самого раннего начала до самого позднего конца
    (all_day в рамку не входят, повтор своего дня входит)."""
    items = _items(conn, day, now)
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
        "header": header_view(conn, day, now),
    }
