"""Отклик ночи на вечер и день (Н6): пары «вечер D - ночь D+1», группы с фактором и без.

Связь, не причина: болезнь из пар исключена (illness_report), остальное - нет. Окно -
RESPONSE_DAYS вечеров до day; ночи до первой ночи API не берутся (пульс покоя импорта - другой
источник).
"""

import sqlite3
from datetime import date, timedelta
from statistics import median
from typing import Any

from ai_coach.load.illness import illness_report
from ai_coach.load.overload import EVENING_WORK_MIN, TOTAL_HIGH, day_entries, evening_hours
from ai_coach.store.garmin_data import first_api_night, list_recovery_days, list_sleep_nights

RESPONSE_DAYS = 90
RESPONSE_MIN_DAYS = 10
ILLNESS_SIGNALS = ("illness_risk", "illness_rest", "illness_return", "illness_light")


def _next_day(iso: str) -> str:
    return (date.fromisoformat(iso) + timedelta(days=1)).isoformat()


def night_pairs(
    days: list[dict[str, Any]], nights: list[dict[str, Any]], sick: set[str]
) -> list[dict[str, Any]]:
    """Пары {date, day, hrv, rhr, sleep_min}: date - вечер D, day - строка дня D, отклик - ночь
    D+1. Пары нет без ночи D+1, без её HRV или пульса покоя и если D или D+1 в sick."""
    by_date = {n["date"]: n for n in nights}
    found: list[dict[str, Any]] = []
    for day in days:
        iso = day["date"]
        after = _next_day(iso)
        night = by_date.get(after)
        if night is None or night["hrv"] is None or night["rhr"] is None:
            continue
        if iso in sick or after in sick:
            continue
        found.append(
            {
                "date": iso,
                "day": day,
                "hrv": night["hrv"],
                "rhr": night["rhr"],
                "sleep_min": night["sleep_min"],
            }
        )
    return found


def _difference(with_pairs: list[dict[str, Any]], without: list[dict[str, Any]], key: str) -> Any:
    """Медиана key у with_pairs минус медиана у without; нет значения в группе - None."""
    mine = [p[key] for p in with_pairs if p[key] is not None]
    other = [p[key] for p in without if p[key] is not None]
    if not mine or not other:
        return None
    return median(mine) - median(other)


def response(
    with_pairs: list[dict[str, Any]], without_pairs: list[dict[str, Any]]
) -> dict[str, Any]:
    """{with, without (число пар), hrv, rhr (разница медиан, один знак), sleep_min (целые минуты),
    enough}; None - группа пуста или значения нет ни у одной пары. enough - в каждой группе не
    меньше RESPONSE_MIN_DAYS пар."""
    hrv = _difference(with_pairs, without_pairs, "hrv")
    rhr = _difference(with_pairs, without_pairs, "rhr")
    sleep = _difference(with_pairs, without_pairs, "sleep_min")
    return {
        "with": len(with_pairs),
        "without": len(without_pairs),
        "hrv": None if hrv is None else round(hrv, 1),
        "rhr": None if rhr is None else round(rhr, 1),
        "sleep_min": None if sleep is None else int(round(sleep)),
        "enough": min(len(with_pairs), len(without_pairs)) >= RESPONSE_MIN_DAYS,
    }


def _nights(conn: sqlite3.Connection, first: str, last: str) -> list[dict[str, Any]]:
    """Ночи API first..last: date, hrv, rhr, sleep_min (нет сна - None)."""
    start = first_api_night(conn)
    if start is None:
        return []
    sleep = {n["date"]: n["sleep_seconds"] for n in list_sleep_nights(conn, first, last)}
    return [
        {
            "date": r["date"],
            "hrv": r["hrv"],
            "rhr": r["rhr"],
            "sleep_min": None if sleep.get(r["date"]) is None else sleep[r["date"]] / 60,
        }
        for r in list_recovery_days(conn, max(first, start), last)
    ]


def _sick_dates(
    conn: sqlite3.Connection, pairs: list[dict[str, Any]], tss: dict[str, float]
) -> set[str]:
    """Даты D и D+1 пар, где у illness_report есть фаза болезни или сигнал illness_*."""
    dates = {p["date"] for p in pairs} | {_next_day(p["date"]) for p in pairs}
    sick: set[str] = set()
    for iso in dates:
        report = illness_report(conn, iso, tss, sleep={"signals": []})
        kinds = {s["kind"] for s in report["signals"]}
        if report["episode"]["phase"] or kinds & set(ILLNESS_SIGNALS):
            sick.add(iso)
    return sick


def recovery_report(conn: sqlite3.Connection, day: str, tss: dict[str, float]) -> dict[str, Any]:
    """{factors: [{factor, with, without, hrv, rhr, sleep_min, enough}]} - evening_work,
    claude_evening, heavy_day; отклик - ночь D+1 после вечера D за RESPONSE_DAYS вечеров до day.
    Для evening_work день без счётчика экрана в группы не идёт; для claude_evening - без счётчика
    Claude; медиана Claude - по всем дням окна со счётчиком."""
    last = date.fromisoformat(day)
    first = (last - timedelta(days=RESPONSE_DAYS)).isoformat()
    days = day_entries(conn, first, (last - timedelta(days=1)).isoformat(), tss)
    nights = _nights(conn, first, day)
    candidates = night_pairs(days, nights, set())
    pairs = night_pairs(days, nights, _sick_dates(conn, candidates, tss))
    prompts = [d["claude_prompts_evening"] for d in days if d["claude_prompts_evening"] is not None]
    middle = median(prompts) if prompts else 0
    # фактор -> {дата пары: есть ли фактор}; день без данных фактора в группы не идёт
    flags: dict[str, dict[str, bool]] = {"evening_work": {}, "claude_evening": {}, "heavy_day": {}}
    for p in pairs:
        row = p["day"]
        if row["screen_work_evening_hours"] is not None:
            flags["evening_work"][p["date"]] = evening_hours(row) >= EVENING_WORK_MIN
        if row["claude_prompts_evening"] is not None:
            flags["claude_evening"][p["date"]] = row["claude_prompts_evening"] > middle
        flags["heavy_day"][p["date"]] = row["total"] >= TOTAL_HIGH
    factors: list[dict[str, Any]] = []
    for name, marks in flags.items():
        found = [p for p in pairs if p["date"] in marks]
        with_pairs = [p for p in found if marks[p["date"]]]
        without = [p for p in found if not marks[p["date"]]]
        factors.append({"factor": name, **response(with_pairs, without)})
    return {"factors": factors}
