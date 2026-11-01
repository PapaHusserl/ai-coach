"""Сигнал «возможно, заболеваешь»: пульс покоя и HRV против личного коридора.

Коридор - среднее за CENTER_DAYS предыдущих дней ± SWC_K × SD за BASELINE_DAYS предыдущих дней
(Plews; сегодняшний день в центр и базу не входит). День вне коридора - пульс покоя выше и HRV
ниже; STREAK_DAYS таких дней подряд - сигнал illness_risk. Сон и вчерашняя тренировка - контекст,
сигнал не меняют. Константы - догадка: калибруются в v2.9, как пороги load/sleep.py.
"""

import sqlite3
from datetime import date, timedelta
from statistics import mean, pstdev
from typing import Any

from ai_coach.load.sleep import sleep_report
from ai_coach.store.garmin_data import list_recovery_days

CENTER_DAYS = 7
MIN_CENTER_DAYS = 4
BASELINE_DAYS = 28
MIN_BASELINE_DAYS = 14
SWC_K = 0.5
STREAK_DAYS = 2
SHOWN_DAYS = 7


def _values(rows: list[dict[str, Any]], day: date, days: int, key: str) -> list[float]:
    """Значения key (не None) за days дней до day, самого day не включая."""
    first, last = (day - timedelta(days=days)).isoformat(), (day - timedelta(days=1)).isoformat()
    return [r[key] for r in rows if first <= r["date"] <= last and r[key] is not None]


def corridor(rows: list[dict[str, Any]], day: date, key: str) -> dict[str, float] | None:
    """{mean7, swc}: среднее key за CENTER_DAYS предыдущих дней и SWC_K × SD за BASELINE_DAYS;
    данных меньше MIN_CENTER_DAYS в центре или MIN_BASELINE_DAYS в базе - None."""
    center = _values(rows, day, CENTER_DAYS, key)
    base = _values(rows, day, BASELINE_DAYS, key)
    if len(center) < MIN_CENTER_DAYS or len(base) < MIN_BASELINE_DAYS:
        return None
    return {"mean7": mean(center), "swc": SWC_K * pstdev(base)}


def _edge(found: dict[str, float] | None, sign: int) -> float | None:
    """Граница коридора round(mean7 + sign × swc, 1); нет коридора - None."""
    if found is None:
        return None
    return round(found["mean7"] + sign * found["swc"], 1)


def day_flags(
    row: dict[str, Any],
    rhr_corridor: dict[str, float] | None,
    hrv_corridor: dict[str, float] | None,
) -> dict[str, bool | None]:
    """{rhr_high, hrv_low, out}: пульс покоя строго выше границы mean7 + swc, HRV строго ниже
    mean7 - swc (границы округлены до одного знака, как в отчёте), out - оба. Нет значения или
    коридора - всё None."""
    rhr, hrv = row.get("rhr"), row.get("hrv")
    high_from, low_from = _edge(rhr_corridor, 1), _edge(hrv_corridor, -1)
    if rhr is None or hrv is None or high_from is None or low_from is None:
        return {"rhr_high": None, "hrv_low": None, "out": None}
    high, low = rhr > high_from, hrv < low_from
    return {"rhr_high": high, "hrv_low": low, "out": high and low}


def out_streak(flags_by_date: dict[str, dict[str, bool | None]], day: str) -> int:
    """Дней подряд с out True, считая с day назад; день без данных или в коридоре прерывает."""
    streak, current = 0, date.fromisoformat(day)
    while flags_by_date.get(current.isoformat(), {}).get("out") is True:
        streak += 1
        current -= timedelta(days=1)
    return streak


def illness_signals(report: dict[str, Any]) -> list[dict[str, Any]]:
    """illness_risk - дней вне коридора подряд не меньше STREAK_DAYS; формат {kind, value,
    limit} как у sleep_signals."""
    streak = report["streak"]
    if streak >= STREAK_DAYS:
        return [{"kind": "illness_risk", "value": streak, "limit": STREAK_DAYS}]
    return []


def _edges(found: dict[str, float] | None, sign: int) -> tuple[float | None, float | None]:
    """(центр, граница коридора mean7 + sign × swc), один знак; нет коридора - (None, None)."""
    if found is None:
        return None, None
    return round(found["mean7"], 1), _edge(found, sign)


def _recent(
    rows: list[dict[str, Any]], today: date
) -> tuple[list[dict[str, Any]], dict[str, dict[str, bool | None]]]:
    """Последние SHOWN_DAYS дней по возрастанию: (date, rhr, hrv, out) и флаги по датам."""
    by_date = {r["date"]: r for r in rows}
    shown: list[dict[str, Any]] = []
    flags: dict[str, dict[str, bool | None]] = {}
    for back in range(SHOWN_DAYS - 1, -1, -1):
        current = today - timedelta(days=back)
        stamp = current.isoformat()
        row = by_date.get(stamp, {"date": stamp, "rhr": None, "hrv": None})
        found = day_flags(row, corridor(rows, current, "rhr"), corridor(rows, current, "hrv"))
        flags[stamp] = found
        shown.append({"date": stamp, "rhr": row["rhr"], "hrv": row["hrv"], "out": found["out"]})
    return shown, flags


def _context(
    conn: sqlite3.Connection,
    day: str,
    tss: dict[str, float] | None,
    sleep: dict[str, Any] | None,
) -> dict[str, Any]:
    """confounders (short_night, trained_yesterday), tss_yesterday и sleep_debt."""
    report = sleep if sleep is not None else sleep_report(conn, day)
    kinds = {s["kind"] for s in report["signals"]}
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    spent = (tss or {}).get(yesterday)
    confounders = [
        name
        for name, found in (
            ("short_night", "short_night" in kinds),
            ("trained_yesterday", bool(spent)),
        )
        if found
    ]
    return {"confounders": confounders, "tss_yesterday": spent, "sleep_debt": "sleep_debt" in kinds}


def illness_report(
    conn: sqlite3.Connection,
    day: str,
    tss: dict[str, float] | None = None,
    sleep: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Пульс покоя и HRV на day против коридора: rhr, hrv, *_mean7, rhr_high_from / hrv_low_from
    (границы коридора, None - данных мало), rhr_high, hrv_low, out_today, streak (дней вне
    коридора подряд, не больше SHOWN_DAYS), baseline_days (дней базы с пульсом и HRV), days
    (SHOWN_DAYS дней: date, rhr, hrv, out), confounders, tss_yesterday, sleep_debt, signals. tss -
    TSS по дням, sleep - готовый sleep_report (нет - считается здесь)."""
    today = date.fromisoformat(day)
    first = (today - timedelta(days=BASELINE_DAYS + SHOWN_DAYS - 1)).isoformat()
    rows = list_recovery_days(conn, first, day)
    base_first = (today - timedelta(days=BASELINE_DAYS)).isoformat()
    shown, flags = _recent(rows, today)
    rhr_mean7, rhr_high_from = _edges(corridor(rows, today, "rhr"), 1)
    hrv_mean7, hrv_low_from = _edges(corridor(rows, today, "hrv"), -1)
    report: dict[str, Any] = {
        "date": day,
        "rhr": shown[-1]["rhr"],
        "rhr_mean7": rhr_mean7,
        "rhr_high_from": rhr_high_from,
        "rhr_high": flags[day]["rhr_high"],
        "hrv": shown[-1]["hrv"],
        "hrv_mean7": hrv_mean7,
        "hrv_low_from": hrv_low_from,
        "hrv_low": flags[day]["hrv_low"],
        "out_today": flags[day]["out"],
        "streak": out_streak(flags, day),
        "baseline_days": len(
            [
                r
                for r in rows
                if base_first <= r["date"] < day and r["rhr"] is not None and r["hrv"] is not None
            ]
        ),
        "days": shown,
        **_context(conn, day, tss, sleep),
    }
    return {**report, "signals": illness_signals(report)}
