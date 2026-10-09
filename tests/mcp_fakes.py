"""Помощники для тестов MCP: вызов инструмента сервера без сети и stdio.

Сервер открывает базу на каждый вызов, поэтому данные тестов коммитятся перед вызовом.
"""

import asyncio
import json
import sqlite3
from typing import Any

from ai_coach.mcp_server import build_server


def db_file(conn: sqlite3.Connection) -> str:
    return conn.execute("PRAGMA database_list").fetchone()["file"]


def tool_names(conn: sqlite3.Connection) -> set[str]:
    server = build_server(db_file(conn))
    return {tool.name for tool in asyncio.run(server.list_tools())}


def _result(conn: sqlite3.Connection, name: str, arguments: dict[str, Any]) -> Any:
    conn.commit()
    server = build_server(db_file(conn))
    return asyncio.run(server.call_tool(name, arguments))


def call(conn: sqlite3.Connection, name: str, /, **arguments: Any) -> Any:
    """Данные ответа (объект); отказ инструмента — исключение ToolError."""
    result = _result(conn, name, arguments)
    data = result.structured_content  # type: ignore[union-attr]
    if data is None:
        return json.loads(result.content[0].text)  # type: ignore[union-attr]
    return data["result"] if set(data) == {"result"} else data


def call_text(conn: sqlite3.Connection, name: str, /, **arguments: Any) -> str:
    """Весь ответ одной строкой — для проверки размера и отсутствия лишних полей."""
    return json.dumps(call(conn, name, **arguments), ensure_ascii=False)


def rows(conn: sqlite3.Connection, name: str, /, **arguments: Any) -> list[dict[str, Any]]:
    return call(conn, name, **arguments)["rows"]


def call_content(conn: sqlite3.Connection, name: str, /, **arguments: Any) -> list[Any]:
    """Все блоки content ответа (текст, картинки); отказ инструмента — ToolError."""
    return list(_result(conn, name, arguments).content)
