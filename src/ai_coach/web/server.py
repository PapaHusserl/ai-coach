"""HTTP-сервер пульта на стандартной библиотеке: GET /, /static/*, /api/day?date=. Только читает
базу, на каждый запрос своё соединение. Без ключа доступа: решение Влада (Р6 = 1)."""

import json
import socket
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from ai_coach.store.db import open_db
from ai_coach.web.day import day_view

STATIC_PREFIX = "/static/"
TYPES = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
STUB = "<!doctype html><meta charset=utf-8><title>Пульт</title><p>Пульт: /api/day</p>"


def lan_address() -> str | None:
    """Адрес этого компьютера в локальной сети (UDP-connect, ничего не отправляется)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def make_server(host: str, port: int, db: str | Path | None = None) -> ThreadingHTTPServer:
    """Сервер пульта; порт 0 - любой свободный. db - путь к базе (по умолчанию как у coach)."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def text(self, status: int, message: str) -> None:
            self.send(status, message.encode(), "text/plain")

        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            if parts.path == "/":
                self.send(HTTPStatus.OK, STUB.encode(), "text/html")
            elif parts.path == "/api/day":
                self.api_day(parse_qs(parts.query))
            elif parts.path.startswith(STATIC_PREFIX):
                self.static(parts.path[len(STATIC_PREFIX) :])
            else:
                self.text(HTTPStatus.NOT_FOUND, "Не найдено.")

        def api_day(self, query: dict[str, list[str]]) -> None:
            now = datetime.now()
            try:
                day = date.fromisoformat(query["date"][0]) if "date" in query else now.date()
            except ValueError:
                self.text(HTTPStatus.BAD_REQUEST, "date: нужна дата YYYY-MM-DD.")
                return
            conn = open_db(db)
            try:
                view = day_view(conn, day, now)
            finally:
                conn.close()
            self.send(
                HTTPStatus.OK, json.dumps(view, ensure_ascii=False).encode(), "application/json"
            )

        def static(self, name: str) -> None:
            file = resources.files("ai_coach.web").joinpath("static", name)
            if not name or "/" in name or name.startswith(".") or not file.is_file():
                self.text(HTTPStatus.NOT_FOUND, "Не найдено.")
                return
            kind = TYPES.get(Path(name).suffix, "application/octet-stream")
            self.send(HTTPStatus.OK, file.read_bytes(), kind)

        def refuse(self) -> None:
            self.text(HTTPStatus.METHOD_NOT_ALLOWED, "Только GET.")

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = refuse

    return ThreadingHTTPServer((host, port), Handler)
