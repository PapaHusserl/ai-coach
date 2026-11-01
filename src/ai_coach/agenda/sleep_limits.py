"""Поправка плана дня по сну и сигналу болезни: сегодня при сигнале сна - фокус-блоков на один
меньше и не позже caution_from, завтра - на один меньше при sleep_debt; при illness_risk
(сегодня и завтра) - на один меньше, предел не меняется."""

import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

from ai_coach.load import illness_report, sleep_report
from ai_coach.load.sleep import DEBT_14_H
from ai_coach.workload.service import SATURDAY


def _sleep_reason(signal: dict[str, Any], report: dict[str, Any]) -> str:
    if signal["kind"] == "illness_risk":
        return (
            "фокус: блоков меньше - возможно, заболеваешь (пульс покоя "
            f"{report['rhr']}, HRV {report['hrv']} вне коридора {signal['value']} дня подряд)"
        )
    if signal["kind"] == "short_night":
        night, norm = report["last_night_h"], report["norm_h"]
        return f"фокус: блоков меньше - короткая ночь ({night} ч против нормы {norm})"
    nights = {DEBT_14_H: 14}.get(signal["limit"], 7)
    return f"фокус: блоков меньше - долг сна {signal['value']} ч за {nights} ночей"


def sleep_limits(
    conn: sqlite3.Connection,
    day: date,
    today: date,
    now: datetime,
    focus_until: time,
    focus_max: int,
) -> tuple[time, int, list[str]]:
    """(focus_until, focus_max, причины для skipped - пусто или одна) по сну и болезни: сегодня
    при любом сигнале сна - на блок меньше и не позже caution_from; завтра при sleep_debt - на
    блок меньше; illness_risk - на блок меньше сегодня и завтра (предел только от сна, при двух
    сигналах не минус два, причина по первому: сон, затем болезнь); иначе без поправки. Ночь
    завтрашнего дня неизвестна, поэтому отчёты всегда на today."""
    plain: tuple[time, int, list[str]] = (focus_until, focus_max, [])
    if day.weekday() >= SATURDAY or not today <= day <= today + timedelta(days=1):
        return plain
    report = sleep_report(conn, today.isoformat(), now)
    sleep_signals = [s for s in report["signals"] if day == today or s["kind"] == "sleep_debt"]
    illness = illness_report(conn, today.isoformat(), {}, report)
    signals = sleep_signals + illness["signals"]
    if not signals:
        return plain
    until = datetime.combine(day, focus_until)
    if sleep_signals and day == today and report["caution_from"] is not None:
        # caution_from на следующую дату (подъём после 08:00) предел не режет
        until = min(until, datetime.strptime(report["caution_from"], "%Y-%m-%d %H:%M"))
    reason = _sleep_reason(signals[0], report | {"rhr": illness["rhr"], "hrv": illness["hrv"]})
    return until.time(), focus_max - 1, [reason]
