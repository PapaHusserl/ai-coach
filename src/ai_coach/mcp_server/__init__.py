"""mcp_server: MCP-сервер (stdio) для Claude Code, запуск — `python -m ai_coach.mcp_server`."""

from ai_coach.mcp_server.server import build_server, main

__all__ = ["build_server", "main"]
