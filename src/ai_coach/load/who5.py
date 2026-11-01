"""Опросник благополучия WHO-5: балл, «пора» и сигналы для сводки.

Пять утверждений о последних двух неделях, каждое 0-5 (5 - всё время, 0 - никогда); балл =
сумма × 4, от 0 до 100. Авторское право - ВОЗ, CC BY-NC-SA 3.0 IGO (WHO-UCN-MSD-MHE-2024.01);
тексты утверждений лежат в .claude/agents/coach-help/who5.md (перевод ВОЗ, вариант 1999 г.).
Английские оригиналы, для сверки:
1. I have felt cheerful and in good spirits.
2. I have felt calm and relaxed.
3. I have felt active and vigorous.
4. I woke up feeling fresh and rested.
5. My daily life has been filled with things that interest me.
Пороги - Topp et al. 2015, Psychother Psychosom 84:167-176: 50 и ниже - скрининг депрессии,
28 и ниже - уровень большой депрессии, значимое изменение - 10 баллов. Фиксированы, v2.9 не
калибрует.
"""

import sqlite3
from datetime import date, timedelta
from typing import Any

from ai_coach.store.journal import last_who5

ITEMS_COUNT = 5
ITEM_MIN = 0
ITEM_MAX = 5
SCALE = 4
PERIOD_DAYS = 14
LOW_SCORE = 28
REDUCED_SCORE = 50
DROP_POINTS = 10


def who5_score(items: list[int]) -> int:
    """Балл 0-100: сумма ответов × SCALE."""
    return sum(items) * SCALE


def who5_signals(score: int, prev_score: int | None, days_since: int) -> list[dict[str, Any]]:
    """Сигналы последнего замера (формат {kind, value, limit} как у find_overload), пока он
    свежий (меньше PERIOD_DAYS дней): who5_low (28 и ниже) или who5_reduced (28 < балл <= 50,
    вместе не выдаются), who5_drop - падение к прошлому замеру на DROP_POINTS и больше."""
    if days_since >= PERIOD_DAYS:
        return []
    signals: list[dict[str, Any]] = []
    if score <= LOW_SCORE:
        signals.append({"kind": "who5_low", "value": score, "limit": LOW_SCORE})
    elif score <= REDUCED_SCORE:
        signals.append({"kind": "who5_reduced", "value": score, "limit": REDUCED_SCORE})
    if prev_score is not None and prev_score - score >= DROP_POINTS:
        signals.append({"kind": "who5_drop", "value": prev_score - score, "limit": DROP_POINTS})
    return signals


def who5_report(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """WHO-5 на day: last_date, score, prev_date, prev_score, delta (к прошлому), days_since,
    due (замеров нет или прошло PERIOD_DAYS дней), low_until (last_date + PERIOD_DAYS при
    who5_low, иначе None), signals. Нет замеров - поля None, due True."""
    found = last_who5(conn, day, 2)
    if not found:
        return {
            "last_date": None,
            "score": None,
            "prev_date": None,
            "prev_score": None,
            "delta": None,
            "days_since": None,
            "due": True,
            "low_until": None,
            "signals": [],
        }
    last = found[0]
    prev = found[1] if len(found) > 1 else None
    prev_score = prev["score"] if prev else None
    last_day = date.fromisoformat(last["date"])
    days_since = (date.fromisoformat(day) - last_day).days
    signals = who5_signals(last["score"], prev_score, days_since)
    low = any(s["kind"] == "who5_low" for s in signals)
    return {
        "last_date": last["date"],
        "score": last["score"],
        "prev_date": prev["date"] if prev else None,
        "prev_score": prev_score,
        "delta": last["score"] - prev_score if prev_score is not None else None,
        "days_since": days_since,
        "due": days_since >= PERIOD_DAYS,
        "low_until": (last_day + timedelta(days=PERIOD_DAYS)).isoformat() if low else None,
        "signals": signals,
    }
