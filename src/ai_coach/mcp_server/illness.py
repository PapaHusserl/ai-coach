"""Инструмент MCP: сигнал «возможно, заболеваешь» (отдельно от tools.py из-за размера)."""

import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.load import illness_report
from ai_coach.mcp_server.tools import load, period, shift_day


def illness(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Пульс покоя и HRV на date против личного коридора, дней вне коридора подряд и сигнал
    illness_risk (формулы и пороги — в load/illness.py). TSS вчера берётся из нагрузки
    тренировок; нет нагрузки — TSS не известен, причина в load_error."""
    period(date, date)
    try:
        rows = load(conn, shift_day(date, -1), date)["rows"]
    except ToolError as error:
        return {**illness_report(conn, date, {}), "load_error": str(error)}
    return illness_report(conn, date, {r["date"]: r["tss"] for r in rows})
