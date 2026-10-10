"""Инструмент MCP: общая нагрузка и сигналы перегруза (отдельно от tools.py из-за размера)."""

import datetime as dt
import sqlite3
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from ai_coach.load import overload_report
from ai_coach.load.overload import OVERLOAD_DAYS
from ai_coach.mcp_server.tools import load, period


def overload(conn: sqlite3.Connection, date: str) -> dict[str, Any]:
    """Общая нагрузка за 7 дней до date включительно и сигналы перегруза (пороги и веса — в
    load/overload.py): total (нагрузка date), days (date, total, ручные часы), signals (kind,
    value, limit; пустой список — перегруза нет). Нет нагрузки тренировок — TSS считается
    нулём, причина — в load_error."""
    period(date, date)
    first = dt.date.fromisoformat(date) - dt.timedelta(days=OVERLOAD_DAYS - 1)
    try:
        rows = load(conn, first.isoformat(), date)["rows"]
    except ToolError as error:
        return {**overload_report(conn, date, {}), "load_error": str(error)}
    return overload_report(conn, date, {r["date"]: r["tss"] for r in rows})
