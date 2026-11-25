"""Повторяющиеся пункты плана на день просмотра: выпадает ли повтор на день и его время в нём."""

from datetime import date, datetime, timedelta
from typing import Any

BIWEEKLY_DAYS = 14


def on_day(row: dict[str, Any], day: date) -> bool:
    """Повтор, начатый раньше, выпадает на day: daily - каждый день, weekly - в тот же день
    недели, biweekly - через две недели."""
    if row["repeat"] is None or row["date"] >= day.isoformat():
        return True
    gap = (day - date.fromisoformat(row["date"])).days
    if row["repeat"] == "daily":
        return True
    return gap % (BIWEEKLY_DAYS if row["repeat"] == "biweekly" else 7) == 0


def moved(row: dict[str, Any], day: date) -> dict[str, Any]:
    """Повтор, начатый раньше day, - то же время суток на day."""
    if row["repeat"] is None or row["date"] >= day.isoformat():
        return row
    start = datetime.fromisoformat(row["start_at"])
    shift = timedelta(days=(day - start.date()).days)
    end = datetime.fromisoformat(row["end_at"])
    values = {"start_at": (start + shift).isoformat(), "end_at": (end + shift).isoformat()}
    return {**row, **values}
