"""Разнообразие питания за неделю: в сколько дней была каждая группа продуктов."""

import sqlite3
from datetime import date, timedelta
from typing import Any

from ai_coach.nutrition.groups import FOOD_GROUPS, GROUP_MAX_DAYS, GROUP_MIN_DAYS
from ai_coach.store.journal import list_food, list_food_groups


def variety_week(conn: sqlite3.Connection, monday: str | date) -> dict[str, Any]:
    """Неделя Пн-Вс от monday: days_with_data (дни с живыми записями еды), groups (ключ -> дней
    с группой, все ключи), low (группа ниже порога: group, days, min_days, nutrients), high
    (группа выше планки: group, days, max_days). Пустая неделя - low и high пусты."""
    first = date.fromisoformat(monday) if isinstance(monday, str) else monday
    start, end = first.isoformat(), (first + timedelta(days=6)).isoformat()
    days_with_data = len({row["logged_at"][:10] for row in list_food(conn, start, end)})
    seen: dict[str, set[str]] = {key: set() for key in FOOD_GROUPS}
    for row in list_food_groups(conn, start, end):
        seen[row["group_key"]].add(row["day"])
    groups = {key: len(days) for key, days in seen.items()}
    low: list[dict[str, Any]] = []
    high: list[dict[str, Any]] = []
    if days_with_data:
        low = [
            {
                "group": key,
                "days": groups[key],
                "min_days": minimum,
                "nutrients": list(FOOD_GROUPS[key][1]),
            }
            for key, minimum in GROUP_MIN_DAYS.items()
            if groups[key] < minimum
        ]
        high = [
            {"group": key, "days": groups[key], "max_days": maximum}
            for key, maximum in GROUP_MAX_DAYS.items()
            if groups[key] > maximum
        ]
    return {"days_with_data": days_with_data, "groups": groups, "low": low, "high": high}
