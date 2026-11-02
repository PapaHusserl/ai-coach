"""Стресс Garmin в момент: среднее замеров вокруг времени отметки.

Замеры (stressValuesArray) - раз в несколько минут, метка времени - epoch GMT в мс; местное время
берётся из системного пояса. Уровень <= 0 (нет замера или покой без данных) не считается.
Окно STRESS_WINDOW_MIN - догадка, как пороги в load/sleep.py.
"""

from datetime import datetime
from typing import Any

STRESS_WINDOW_MIN = 15


def stress_at(
    points: list[dict[str, Any]], moment: datetime, window_min: int = STRESS_WINDOW_MIN
) -> int | None:
    """Среднее level > 0 замеров в окне ±window_min минут от moment (местное время), целое;
    нет замеров - None."""
    levels = [
        p["level"]
        for p in points
        if p["level"] is not None
        and p["level"] > 0
        and abs((datetime.fromtimestamp(p["ts_ms"] / 1000) - moment).total_seconds())
        <= window_min * 60
    ]
    return round(sum(levels) / len(levels)) if levels else None
