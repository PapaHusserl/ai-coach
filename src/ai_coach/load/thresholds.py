"""Пороговый пульс по видам спорта: из Garmin, иначе считаем сами (source=derived)."""

import sqlite3
from datetime import date, timedelta
from typing import Any

from ai_coach.load.sports import SPORT_TYPE_KEYS
from ai_coach.store.garmin_data import last_threshold, last_zones_max_hr, max_hr

# Смещение порога от бегового (ударов в минуту); константы, не из Garmin.
OFFSET_FROM_RUN = {"run": 0, "bike": 7, "swim": 12}
THRESHOLD_SPORTS = tuple(OFFSET_FROM_RUN)
MAX_HR_SHARE = 0.89
MAX_HR_DAYS = 365


def _top_hr(conn: sqlite3.Connection, sport: str, end: str) -> int | None:
    """Максимальный пульс вида: из зон Garmin, иначе максимум бега и вело за год до end."""
    from_zones = last_zones_max_hr(conn, sport, end)
    if from_zones:
        return from_zones
    start = (date.fromisoformat(end) - timedelta(days=MAX_HR_DAYS)).isoformat()
    return max_hr(conn, start, end, SPORT_TYPE_KEYS["run"] + SPORT_TYPE_KEYS["bike"])


def resolve_thresholds(conn: sqlite3.Connection, end: str) -> dict[str, dict[str, Any]]:
    """{вид: {lthr, source, date}} на дату end. Производные пороги не хранятся.

    Порог вида — последняя запись из базы (garmin_lt или garmin_zones), побеждает более
    новая дата. Нет — беговой минус смещение; нет бегового — 0.89 * max HR вида (зоны
    Garmin, иначе активности); нет и его — вида в ответе нет."""
    result: dict[str, dict[str, Any]] = {}
    for sport in THRESHOLD_SPORTS:
        row = last_threshold(conn, sport, end)
        if row:
            result[sport] = {
                "lthr": row["lthr"],
                "source": row["source"],
                "date": row["calendar_date"],
            }
    run = result.get("run")
    for sport, offset in OFFSET_FROM_RUN.items():
        if sport in result:
            continue
        if run:
            result[sport] = {"lthr": run["lthr"] - offset, "source": "derived", "date": run["date"]}
            continue
        top = _top_hr(conn, sport, end)
        if top:
            result[sport] = {"lthr": round(top * MAX_HR_SHARE), "source": "derived", "date": None}
    return result
