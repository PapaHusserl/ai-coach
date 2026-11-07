"""HTTP-сервер пульта: /api/day, /static, методы, ошибки (шаг П1, партия 2)."""

import http.client
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import pytest

from ai_coach.web.server import make_server


@pytest.fixture
def port(tmp_path: Path) -> Iterator[int]:
    server = make_server("127.0.0.1", 0, tmp_path / "coach.db")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def request(port: int, path: str, method: str = "GET") -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def test_api_day_returns_json(port: int) -> None:
    status, body = request(port, "/api/day?date=2026-11-07")
    assert status == 200
    data = json.loads(body)
    assert data["items"] == []
    assert data["meetings"] == []


def test_api_day_without_date_is_today(port: int) -> None:
    status, body = request(port, "/api/day")
    assert status == 200
    assert "items" in json.loads(body)


def test_api_day_garbage_date_is_400_with_text(port: int) -> None:
    status, body = request(port, "/api/day?date=" + quote("мусор"))
    assert status == 400
    assert "date" in body.decode()


def test_static_dotdot_is_404(port: int) -> None:
    status, _ = request(port, "/static/../x")
    assert status == 404


def test_static_missing_file_is_404(port: int) -> None:
    status, _ = request(port, "/static/nope.js")
    assert status == 404


def test_unknown_path_is_404(port: int) -> None:
    status, _ = request(port, "/nope")
    assert status == 404


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_non_get_is_405(port: int, method: str) -> None:
    status, _ = request(port, "/api/day", method)
    assert status == 405


def test_head_is_501_with_empty_body(port: int) -> None:
    status, body = request(port, "/", "HEAD")
    assert status == 501
    assert body == b""


def test_root_is_html_without_credentials(port: int) -> None:
    status, _ = request(port, "/")
    assert status == 200


def test_root_serves_index_page(port: int) -> None:
    _, body = request(port, "/")
    page = body.decode()
    assert 'id="rows"' in page
    assert "/static/pult.js" in page


def test_static_serves_real_script(port: int) -> None:
    status, body = request(port, "/static/pult.js")
    assert status == 200
    assert b"formatClock" in body


def test_static_script_content_type(port: int) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/static/pult.js")
        response = conn.getresponse()
        response.read()
        assert response.getheader("Content-Type") == "text/javascript; charset=utf-8"
    finally:
        conn.close()


def test_static_css_content_type(port: int) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/static/pult.css")
        response = conn.getresponse()
        response.read()
        assert response.getheader("Content-Type") == "text/css; charset=utf-8"
    finally:
        conn.close()
