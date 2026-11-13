"""Инструмент MCP: журнал решений на будущее (отдельно от tools.py из-за размера)."""

import sqlite3
from datetime import datetime
from typing import Any

from ai_coach.decisions import day_part, decision_stats
from ai_coach.mcp_server import tools
from ai_coach.store.decisions import list_decisions
from ai_coach.store.plans import actual_of

PLAN_RESULT = {"done": "kept", "skipped": "missed", "different": "missed"}


def _part(stamp: str | None) -> str | None:
    return None if stamp is None else day_part(datetime.fromisoformat(stamp))


def _result(conn: sqlite3.Connection, row: dict[str, Any]) -> str | None:
    """workout: из plan_actual при чтении (done - kept, skipped и different - missed)."""
    if row["kind"] != "workout":
        return row["result"] if row["kind"] == "text" else None
    actual = actual_of(conn, row["ref_id"]) if row["status"] == "yes" else None
    return None if actual is None else PLAN_RESULT.get(actual["kind"])


def decisions(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict[str, Any]:
    """Решения на будущее, у которых created_at или decided_at в периоде (до 92 дней):
    id, kind (text/workout/phase), ref_id, text, target_date, created_at, status
    (open/yes/no/dropped), decided_at, result (kept/missed: у слов - отметка пользователя,
    у тренировки - из плана/факта, у фазы null), created_part, decided_part (morning/day/evening).
    stats - по решениям с decided_at в периоде, по части дня решения: yes, no, dropped, kept,
    missed. Выводов нет."""
    tools.period(date_from, date_to)
    found = [
        row | {"result": _result(conn, row)} for row in list_decisions(conn, date_from, date_to)
    ]
    shown = [
        row | {"created_part": _part(row["created_at"]), "decided_part": _part(row["decided_at"])}
        for row in found
    ]
    decided = [r for r in found if r["decided_at"] and date_from <= r["decided_at"][:10] <= date_to]
    return tools.cap(shown, newest=True) | {"stats": decision_stats(decided)}
