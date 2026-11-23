"""Спайк (П7, партия 8): таблица порогов погодного сигнала по копии базы.

Запуск: uv run python spikes/weather/threshold_table.py <копия базы>
Для каждого дня ряда weather_hours до вчера (days_with_hours: старый прогноз не в счёт)
считает от 07:00 падение давления и рост/падение температуры за 24 часа (pressure_ahead,
temperature_ahead) и печатает две таблицы: строки - пороги, столбцы - «дней выше порога» и
«из них с оценкой <= 2». Только счёт.
Температура: столбцы «рост» и «падение» отдельно (Решения п. 55) и общий «рост или падение»
(дневной прогрев в счёте).
"""

import sys
from datetime import date, datetime, time, timedelta

from ai_coach.load.weather_signal import pressure_ahead, temperature_ahead
from ai_coach.store.db import open_db
from ai_coach.store.weather import days_with_hours, list_weather_hours

PRESSURE_LIMITS = (3, 4, 5, 6, 8, 10)
TEMPERATURE_LIMITS = (5, 7, 10, 12, 15)
LOW_SCORE = 2


def main(path: str) -> None:
    conn = open_db(path)
    first = conn.execute("SELECT MIN(substr(time, 1, 10)) FROM weather_hours").fetchone()[0]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    days = sorted(days_with_hours(conn, first, yesterday))
    low = {
        r[0] for r in conn.execute("SELECT date FROM wellbeing_log WHERE score <= ?", (LOW_SCORE,))
    }
    drops: dict[str, float] = {}
    rises: dict[str, float] = {}
    falls: dict[str, float] = {}
    for day in days:
        now = datetime.combine(date.fromisoformat(day), time(7, 0))
        end = (now.date() + timedelta(days=1)).isoformat()
        hours = list_weather_hours(conn, day, end)
        pressure = pressure_ahead(hours, now)
        temperature = temperature_ahead(hours, now)
        if pressure is None or temperature is None:
            continue
        drops[day] = pressure[0]
        rises[day], falls[day] = temperature[0][0], temperature[1][0]
    swings = {day: max(rises[day], falls[day]) for day in rises}
    print(f"дней в таблице: {len(drops)}")
    for title, limits, unit, columns in (
        ("давление, падение", PRESSURE_LIMITS, "гПа", (("падение", drops),)),
        (
            "температура",
            TEMPERATURE_LIMITS,
            "°C",
            (("рост", rises), ("падение", falls), ("рост или падение", swings)),
        ),
    ):
        head = " | ".join(
            f"{name}: дней выше порога | из них с оценкой <= {LOW_SCORE}" for name, _ in columns
        )
        print(f"\n{title}\nпорог | {head}")
        for limit in limits:
            cells = []
            for _, values in columns:
                above = [d for d, v in values.items() if round(v, 1) > limit]
                cells += [len(above), sum(d in low for d in above)]
            print(f"{limit} {unit} | " + " | ".join(map(str, cells)))


if __name__ == "__main__":
    main(sys.argv[1])
