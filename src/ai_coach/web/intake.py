"""Блок «Добавки к приёму» в окне еды: курсы и добавки дня, отметка «принял» (шаг П8)."""

import sqlite3
from datetime import date, datetime
from typing import Any

from ai_coach.meds import meds_for_day
from ai_coach.sport_nutrition import has_training, supplements_for_day
from ai_coach.store.intake import delete_intake, list_intake, log_intake
from ai_coach.web.errors import MarkError

KINDS = ("supplement", "med")
KEYS = ("id", "name", "dose", "unit", "time_note")


def intake_view(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Курсы дня, затем добавки дня: kind, id, name, dose, unit, time_note, taken (есть приём
    за день своего вида). Один список на день, у каждого пункта еды он общий."""
    taken = {k: {r["item_id"] for r in list_intake(conn, day, day, k)} for k in KINDS}
    courses = [{"kind": "med"} | {k: m[k] for k in KEYS} for m in meds_for_day(conn, day)]
    supplements = [
        {"kind": "supplement"} | {k: s[k] for k in KEYS}
        for s in supplements_for_day(conn, has_training(conn, day))
    ]
    return [row | {"taken": row["id"] in taken[row["kind"]]} for row in courses + supplements]


def _day(payload: dict[str, Any], now: datetime) -> str:
    try:
        value = date.fromisoformat(payload["date"])
    except (KeyError, TypeError, ValueError):
        raise MarkError("Дата должна быть YYYY-MM-DD.") from None
    if value > now.date():
        raise MarkError("Приём отмечается за сегодня и прошлые дни.")
    return value.isoformat()


def save_intake(conn: sqlite3.Connection, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    """POST /api/intake {kind, item_id, date, taken: 1 | 0}: taken 1 - приём по норме (повторный
    не двоится), 0 - снять все живые приёмы дня у этой позиции. Позиции нет в блоке дня - отказ."""
    kind, item_id, taken = payload.get("kind"), payload.get("item_id"), payload.get("taken")
    day = _day(payload, now)
    if kind not in KINDS or type(item_id) is not int:
        raise MarkError("Такой позиции нет.")
    if type(taken) is not int or taken not in (0, 1):
        raise MarkError("taken: 1 или 0.")
    found = [r for r in intake_view(conn, day) if (r["kind"], r["id"]) == (kind, item_id)]
    if not found:
        raise MarkError("Такой позиции в блоке этого дня нет.")
    if taken and not found[0]["taken"]:
        values = {"item_id": item_id, "date": day, "taken_at": now.isoformat(" ", "seconds")}
        log_intake(conn, values, kind)
    if not taken:
        stamp = now.isoformat(" ", "seconds")
        for row in list_intake(conn, day, day, kind):
            if row["item_id"] == item_id:
                delete_intake(conn, row["id"], stamp, kind)
    return {"taken": taken}
