"""Долг сна и время от подъёма.

Личная норма - медиана ночей за NORM_DAYS дней; долг - сумма (норма - сон) за 7 и 14 ночей,
со знаком (минус - выспался); дневной сон гасит долг, в норму и короткую ночь не входит.
Пороги - константы и пока догадка: калибруются в v2.9, как TOTAL_HIGH в load/overload.py.
Ночь без данных (sleep_seconds 0 или NULL) не считается ни в норму, ни в долг.
"""

import sqlite3
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any

from ai_coach.store.garmin_data import list_sleep_nights

NORM_DAYS = 90
NORM_MIN_NIGHTS = 20
DEBT_WINDOWS = (7, 14)
SHORT_NIGHT_H = 1.0
DEBT_7_H = 3.0
DEBT_14_H = 5.0
AWAKE_LIMIT_H = 16
TIME_FORMAT = "%Y-%m-%d %H:%M"


def night_hours(row: dict[str, Any]) -> float | None:
    """Часы ночного сна строки; 0 и NULL - нет данных."""
    seconds = row.get("sleep_seconds")
    return seconds / 3600 if seconds else None


def _window(nights: list[dict[str, Any]], today: date, days: int) -> list[dict[str, Any]]:
    """Ночи с данными за days дней до today включительно."""
    first = (today - timedelta(days=days - 1)).isoformat()
    return [n for n in nights if first <= n["date"] <= today.isoformat() and night_hours(n)]


def sleep_norm(nights: list[dict[str, Any]], today: date) -> dict[str, Any] | None:
    """{norm_h, nights}: медиана ночей за NORM_DAYS дней; ночей меньше NORM_MIN_NIGHTS - None."""
    hours = [night_hours(n) or 0.0 for n in _window(nights, today, NORM_DAYS)]
    if len(hours) < NORM_MIN_NIGHTS:
        return None
    return {"norm_h": round(median(hours), 2), "nights": len(hours)}


def sleep_debt(
    nights: list[dict[str, Any]], today: date, norm_h: float | None, days: int
) -> dict[str, Any]:
    """{debt_h, nights}: сумма (норма - ночь - дневной сон) за days ночей с данными; нет нормы -
    debt_h None."""
    found = _window(nights, today, days)
    if norm_h is None:
        return {"debt_h": None, "nights": len(found)}
    total = sum(norm_h - (night_hours(n) or 0) - (n.get("nap_seconds") or 0) / 3600 for n in found)
    return {"debt_h": round(total, 1), "nights": len(found)}


def awake_hours(sleep_end: str | None, at: datetime) -> float | None:
    """Часы от подъёма до at, один знак; раньше подъёма - 0.0."""
    if sleep_end is None:
        return None
    seconds = (at - datetime.fromisoformat(sleep_end)).total_seconds()
    return max(0.0, round(seconds / 3600, 1))


def sleep_signals(report: dict[str, Any]) -> list[dict[str, Any]]:
    """short_night (ночь короче нормы на SHORT_NIGHT_H и больше) и sleep_debt (долг за 7 или 14
    ночей не меньше порога); формат {kind, value, limit} как у find_overload."""
    signals: list[dict[str, Any]] = []
    last, norm = report["last_night_h"], report["norm_h"]
    gap = round(norm - last, 2) if last is not None and norm is not None else None
    if gap is not None and gap >= SHORT_NIGHT_H:
        signals.append({"kind": "short_night", "value": gap, "limit": SHORT_NIGHT_H})
    debt_7, debt_14 = report["debt_7_h"], report["debt_14_h"]
    if debt_7 is not None and debt_7 >= DEBT_7_H:
        signals.append({"kind": "sleep_debt", "value": debt_7, "limit": DEBT_7_H})
    elif debt_14 is not None and debt_14 >= DEBT_14_H:
        signals.append({"kind": "sleep_debt", "value": debt_14, "limit": DEBT_14_H})
    return signals


def _debts(nights: list[dict[str, Any]], today: date, norm_h: float | None) -> dict[str, Any]:
    found = {days: sleep_debt(nights, today, norm_h, days) for days in DEBT_WINDOWS}
    return {
        "debt_7_h": found[7]["debt_h"],
        "nights_7": found[7]["nights"],
        "debt_14_h": found[14]["debt_h"],
        "nights_14": found[14]["nights"],
    }


def _wake(sleep_end: str | None, day: str, now: datetime | None) -> dict[str, Any]:
    """wake_at, caution_from (подъём + AWAKE_LIMIT_H) и awake_h (только если day - сегодня)."""
    if sleep_end is None:
        return {"wake_at": None, "awake_h": None, "caution_from": None}
    wake = datetime.fromisoformat(sleep_end)
    caution = wake + timedelta(hours=AWAKE_LIMIT_H)
    awake = (
        awake_hours(sleep_end, now) if now is not None and now.date().isoformat() == day else None
    )
    return {
        "wake_at": wake.strftime(TIME_FORMAT),
        "awake_h": awake,
        "caution_from": caution.strftime(TIME_FORMAT),
    }


def sleep_report(conn: sqlite3.Connection, day: str, now: datetime | None = None) -> dict[str, Any]:
    """Сон на day: date, norm_h, norm_nights, last_night_h, nap_h, debt_7_h/nights_7,
    debt_14_h/nights_14, wake_at, awake_h, caution_from (YYYY-MM-DD HH:MM), signals
    (sleep_signals). Нет нормы - долги None, сигналов нет."""
    today = date.fromisoformat(day)
    nights = list_sleep_nights(conn, (today - timedelta(days=NORM_DAYS - 1)).isoformat(), day)
    norm = sleep_norm(nights, today)
    norm_h = norm["norm_h"] if norm else None
    by_date: dict[str, dict[str, Any]] = {n["date"]: n for n in nights}
    row = by_date.get(day, {})
    last = night_hours(row)
    report = {
        "date": day,
        "norm_h": norm_h,
        "norm_nights": norm["nights"] if norm else len(_window(nights, today, NORM_DAYS)),
        "last_night_h": round(last, 2) if last is not None else None,
        "nap_h": round((row.get("nap_seconds") or 0) / 3600, 1),
        **_debts(nights, today, norm_h),
        **_wake(row.get("sleep_end"), day, now),
    }
    return {**report, "signals": sleep_signals(report)}
