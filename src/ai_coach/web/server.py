"""HTTP-сервер пульта на стандартной библиотеке: GET /, /static/*, /api/day?date=, /api/week?date=
(неделя Пн-Вс и нагрузка вкладки «Тренировки»); пишет в базу
только POST /api/mark (отметки пункта, Origin = Host, Р1 = 2 П2), на каждый запрос своё
соединение. Без ключа доступа: решение Влада (Р6 = 1)."""

import json
import socket
import sqlite3
import sys
from collections.abc import Callable
from datetime import date, datetime
from email.message import Message
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from io import BufferedIOBase
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from ai_coach.store.db import open_db
from ai_coach.web import training
from ai_coach.web.day import day_view
from ai_coach.web.errors import MarkError, NoEvent
from ai_coach.web.marks import save_mark

MAX_BODY = 64 * 1024
STATIC_PREFIX = "/static/"
TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".woff2": "font/woff2",
}


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


def _content_type(kind: str) -> str:
    """Заголовок Content-Type: у текста charset, у бинарного шрифта его нет."""
    return kind if kind.startswith("font/") else f"{kind}; charset=utf-8"


def _refusal(path: str, headers: Message) -> tuple[int, str] | None:
    """Ответ-отказ до чтения тела: не тот путь, чужой Origin, нет или слишком большое тело."""
    origin = headers.get("Origin")
    length = headers.get("Content-Length", "")
    if urlsplit(path).path != "/api/mark":
        return HTTPStatus.NOT_FOUND, "Не найдено."
    if origin is None or urlsplit(origin).netloc != headers.get("Host"):
        return HTTPStatus.FORBIDDEN, "Запись только со страницы пульта."
    if not (length.isascii() and length.isdigit()):
        return HTTPStatus.BAD_REQUEST, "Нужно тело запроса."
    if int(length) > MAX_BODY:
        return HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Тело слишком большое."
    return None


def mark_reply(
    db: str | Path | None, path: str, headers: Message, rfile: BufferedIOBase
) -> tuple[int, str]:
    """POST /api/mark: (статус, тело ответа). Пишет отметку пункта в базу."""
    refusal = _refusal(path, headers)
    if refusal:
        return refusal
    try:
        payload = json.loads(rfile.read(int(headers["Content-Length"])))
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        return HTTPStatus.BAD_REQUEST, "Нужен JSON-объект."
    conn = open_db(db)
    try:
        with conn:
            mark_id = save_mark(conn, cast(dict[str, Any], payload), datetime.now())
    except MarkError as error:
        status = HTTPStatus.NOT_FOUND if isinstance(error, NoEvent) else HTTPStatus.BAD_REQUEST
        return status, str(error)
    finally:
        conn.close()
    return HTTPStatus.OK, json.dumps({"id": mark_id})


def week_view(conn: sqlite3.Connection, day: date, now: datetime) -> dict[str, Any]:
    """GET /api/week: неделя Пн-Вс дня day и нагрузка за 14 дней до него (now не нужен)."""
    return training.week(conn, day.isoformat()) | {"load": training.load(conn, day.isoformat())}


def make_server(host: str, port: int, db: str | Path | None = None) -> ThreadingHTTPServer:
    """Сервер пульта; порт 0 - любой свободный. db - путь к базе (по умолчанию как у coach)."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", _content_type(content_type))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def text(self, status: int, message: str) -> None:
            self.send(status, message.encode(), "text/plain")

        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            if parts.path == "/":
                self.static("index.html")
            elif parts.path == "/api/day":
                self.api(parse_qs(parts.query), day_view)
            elif parts.path == "/api/week":
                self.api(parse_qs(parts.query), week_view)
            elif parts.path.startswith(STATIC_PREFIX):
                self.static(parts.path[len(STATIC_PREFIX) :])
            else:
                self.text(HTTPStatus.NOT_FOUND, "Не найдено.")

        def api(self, query: dict[str, list[str]], build: Callable[..., dict[str, Any]]) -> None:
            """GET с ?date= (нет - сегодня): build(conn, day, now) JSON-ом; кривая дата - 400."""
            now = datetime.now()
            try:
                day = date.fromisoformat(query["date"][0]) if "date" in query else now.date()
            except ValueError:
                self.text(HTTPStatus.BAD_REQUEST, "date: нужна дата YYYY-MM-DD.")
                return
            conn = open_db(db)
            try:
                view = build(conn, day, now)
            finally:
                conn.close()
            body = json.dumps(view, ensure_ascii=False).encode()
            self.send(HTTPStatus.OK, body, "application/json")

        def static(self, name: str) -> None:
            file = resources.files("ai_coach.web").joinpath("static", name)
            if not name or "/" in name or name.startswith(".") or not file.is_file():
                self.text(HTTPStatus.NOT_FOUND, "Не найдено.")
                return
            kind = TYPES.get(Path(name).suffix, "application/octet-stream")
            self.send(HTTPStatus.OK, file.read_bytes(), kind)

        def refuse(self) -> None:
            self.text(HTTPStatus.METHOD_NOT_ALLOWED, "Только GET.")

        def do_POST(self) -> None:
            status, body = mark_reply(db, self.path, self.headers, self.rfile)
            if status != HTTPStatus.OK:
                print(f"POST {self.path} {int(status)} {body}", file=sys.stderr)
            self.send(status, body.encode(), "application/json" if status == 200 else "text/plain")

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = refuse

    return ThreadingHTTPServer((host, port), Handler)
