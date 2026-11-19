"""Сигнал «возможно, заболеваешь»: пульс покоя и HRV против личного коридора.

Коридор - среднее за CENTER_DAYS предыдущих дней ± SWC_K × SD за BASELINE_DAYS предыдущих дней
(Plews; сегодняшний день в центр и базу не входит). День вне коридора - пульс покоя выше или HRV
ниже; STREAK_DAYS таких дней подряд - сигнал illness_risk, первый день - слабый corridor_out. Сон
и вчерашняя тренировка - контекст, сигнал не меняют. Константы проверены на данных
2026-10-12…11-17 (калибровка v2.9).
"""

import json
import sqlite3
from datetime import date, timedelta
from statistics import mean, pstdev
from typing import Any

from ai_coach.load.episode import (
    EPISODE_DAYS,
    HRV_STREAK_DAYS,
    REST_DAYS,
    RETURN_DAYS,
    episode_state,
    form_phrases,
    sick_days,
    status_streak,
    vitals_flags,
)
from ai_coach.load.sleep import sleep_report
from ai_coach.store.forms import get_form, list_form_log
from ai_coach.store.garmin_data import list_recovery_days
from ai_coach.store.journal import list_wellbeing

CENTER_DAYS = 7
MIN_CENTER_DAYS = 4
BASELINE_DAYS = 28
MIN_BASELINE_DAYS = 14
SWC_K = 0.75
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
    mean7 - swc (границы округлены до одного знака, как в отчёте), out - любой из двух. Нет
    значения или коридора - всё None."""
    rhr, hrv = row.get("rhr"), row.get("hrv")
    high_from, low_from = _edge(rhr_corridor, 1), _edge(hrv_corridor, -1)
    if rhr is None or hrv is None or high_from is None or low_from is None:
        return {"rhr_high": None, "hrv_low": None, "out": None}
    high, low = rhr > high_from, hrv < low_from
    return {"rhr_high": high, "hrv_low": low, "out": high or low}


def out_streak(flags_by_date: dict[str, dict[str, bool | None]], day: str) -> int:
    """Дней подряд с out True, считая с day назад; день без данных или в коридоре прерывает."""
    streak, current = 0, date.fromisoformat(day)
    while flags_by_date.get(current.isoformat(), {}).get("out") is True:
        streak += 1
        current -= timedelta(days=1)
    return streak


def _phase_signals(episode: dict[str, Any] | None) -> list[dict[str, Any]]:
    """illness_rest (value - день покоя, why - причины незачёта сегодня) и illness_return
    (value - день возврата); в остальных фазах - ничего."""
    if episode is None:
        return []
    if episode["phase"] == "rest":
        return [
            {
                "kind": "illness_rest",
                "value": episode["rest_step"],
                "limit": REST_DAYS,
                "why": list(episode["not_clean"]),
            }
        ]
    if episode["phase"] == "return":
        return [{"kind": "illness_return", "value": episode["return_day"], "limit": RETURN_DAYS}]
    return []


def illness_signals(report: dict[str, Any]) -> list[dict[str, Any]]:
    """illness_risk - дней вне коридора подряд не меньше STREAK_DAYS; первый день - слабый
    corridor_out; затем hrv_streak (статус HRV плохой не меньше HRV_STREAK_DAYS дней подряд) и
    сигнал фазы после болезни (illness_rest / illness_return); формат {kind, value, limit} как у
    sleep_signals."""
    streak = report["streak"]
    signals: list[dict[str, Any]] = []
    if streak >= STREAK_DAYS:
        signals.append({"kind": "illness_risk", "value": streak, "limit": STREAK_DAYS})
    elif streak == 1:
        signals.append({"kind": "corridor_out", "value": 1, "limit": STREAK_DAYS})
    bad_hrv = report.get("hrv_streak", 0)
    if bad_hrv >= HRV_STREAK_DAYS:
        signals.append({"kind": "hrv_streak", "value": bad_hrv, "limit": HRV_STREAK_DAYS})
    return signals + _phase_signals(report.get("episode"))


def form_texts(conn: sqlite3.Connection, start: str, end: str) -> dict[str, list[str]]:
    """Дата -> фразы ответов форм за start..end: определение формы берётся один раз на имя
    (снятая читается), ответ без формы пропускается, свой текст ответа без записи
    самочувствия идёт в список."""
    texts: dict[str, list[str]] = {}
    forms: dict[str, dict[str, Any] | None] = {}
    for entry in list_form_log(conn, start, end):
        if entry["form"] not in forms:
            forms[entry["form"]] = get_form(conn, entry["form"])
        form = forms[entry["form"]]
        if form is None:
            continue
        found = texts.setdefault(entry["date"], [])
        found += form_phrases(json.loads(form["fields_json"]), json.loads(entry["values_json"]))
        if entry["wellbeing_id"] is None and entry["text"]:
            found.append(entry["text"])
    return texts


def _episode(
    conn: sqlite3.Connection, day: str, flags: dict[str, dict[str, bool | None]]
) -> dict[str, Any]:
    """Фаза болезни на day: тексты записей и форм за EPISODE_DAYS дней, флаги коридора."""
    start = (date.fromisoformat(day) - timedelta(days=EPISODE_DAYS - 1)).isoformat()
    marks = list_wellbeing(conn, start, day)
    texts = form_texts(conn, start, day)
    for mark in marks:
        if mark["text"]:
            texts.setdefault(mark["date"], []).append(mark["text"])
    return episode_state(sick_days(texts, {m["date"] for m in marks}), flags, day)


def _edges(found: dict[str, float] | None, sign: int) -> tuple[float | None, float | None]:
    """(центр, граница коридора mean7 + sign × swc), один знак; нет коридора - (None, None)."""
    if found is None:
        return None, None
    return round(found["mean7"], 1), _edge(found, sign)


def _recent(
    rows: list[dict[str, Any]], today: date, days: int
) -> tuple[list[dict[str, Any]], dict[str, dict[str, bool | None]]]:
    """Последние days дней по возрастанию: (date, rhr, hrv, out) и флаги по датам (day_flags и
    vitals_flags: кожа, дыхание, SpO2)."""
    by_date = {r["date"]: r for r in rows}
    shown: list[dict[str, Any]] = []
    flags: dict[str, dict[str, bool | None]] = {}
    for back in range(days - 1, -1, -1):
        current = today - timedelta(days=back)
        stamp = current.isoformat()
        row = by_date.get(stamp, {"date": stamp, "rhr": None, "hrv": None})
        found = day_flags(row, corridor(rows, current, "rhr"), corridor(rows, current, "hrv"))
        skin_from = _edge(corridor(rows, current, "skin_temp"), 1)
        resp_from = _edge(corridor(rows, current, "respiration"), 1)
        flags[stamp] = {**found, **vitals_flags(row, skin_from, resp_from)}
        shown.append({"date": stamp, "rhr": row["rhr"], "hrv": row["hrv"], "out": found["out"]})
    return shown, flags


def _vitals(
    rows: list[dict[str, Any]], today: date, flags: dict[str, bool | None]
) -> dict[str, Any]:
    """Метрики ночи за today: значение, граница нормы (None - коридора нет) и флаг (None - не
    проверялась); у SpO2 границы нет, порог SPO2_MIN."""
    row = {r["date"]: r for r in rows}.get(today.isoformat(), {})
    skin_from = _edge(corridor(rows, today, "skin_temp"), 1)
    resp_from = _edge(corridor(rows, today, "respiration"), 1)
    return {
        "skin_temp": row.get("skin_temp"),
        "skin_temp_high_from": skin_from,
        "skin_temp_high": flags["skin_temp"],
        "respiration": row.get("respiration"),
        "respiration_high_from": resp_from,
        "respiration_high": flags["respiration"],
        "spo2": row.get("spo2"),
        "spo2_low": flags["spo2"],
    }


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
    (SHOWN_DAYS дней: date, rhr, hrv, out), hrv_streak (дней плохого статуса HRV подряд), vitals
    (кожа, дыхание, SpO2 ночи: значение, граница, флаг), episode (фаза болезни, см.
    episode_state), confounders, tss_yesterday, sleep_debt, signals. tss - TSS по дням, sleep -
    готовый sleep_report (нет - считается здесь)."""
    today = date.fromisoformat(day)
    first = (today - timedelta(days=BASELINE_DAYS + EPISODE_DAYS - 1)).isoformat()
    rows = list_recovery_days(conn, first, day)
    base_first = (today - timedelta(days=BASELINE_DAYS)).isoformat()
    window, flags = _recent(rows, today, EPISODE_DAYS)
    shown = window[-SHOWN_DAYS:]
    shown_flags = {r["date"]: flags[r["date"]] for r in shown}
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
        "streak": out_streak(shown_flags, day),
        "baseline_days": len(
            [
                r
                for r in rows
                if base_first <= r["date"] < day and r["rhr"] is not None and r["hrv"] is not None
            ]
        ),
        "days": shown,
        "hrv_streak": status_streak({r["date"]: r["status"] for r in rows}, day),
        "vitals": _vitals(rows, today, flags[day]),
        "episode": _episode(conn, day, flags),
        **_context(conn, day, tss, sleep),
    }
    return {**report, "signals": illness_signals(report)}
