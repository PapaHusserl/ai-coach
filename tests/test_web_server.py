"""HTTP-сервер пульта: /api/day, /static, методы, ошибки (шаг П1, партия 2)."""

import http.client
import json
import socket
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import quote

import pytest
from workload_fakes import coach_event

from ai_coach.store.agenda import add_event
from ai_coach.store.db import open_db
from ai_coach.web import server as server_module
from ai_coach.web.server import lan_address, make_server


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "coach.db"


@pytest.fixture
def port(db_path: Path) -> Iterator[int]:
    server = make_server("127.0.0.1", 0, db_path)
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


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH"])
def test_non_get_is_405(port: int, method: str) -> None:
    status, _ = request(port, "/api/day", method)
    assert status == 405


def post(
    port: int,
    body: bytes | dict[str, Any],
    path: str = "/api/mark",
    origin: str | None = "same",
    length: int | None = None,
) -> tuple[int, bytes]:
    """POST; origin "same" - Origin = Host сервера, None - без Origin."""
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    headers = {"Content-Length": str(len(raw) if length is None else length)}
    if origin is not None:
        headers["Origin"] = f"http://127.0.0.1:{port}" if origin == "same" else origin
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("POST", path, body=raw, headers=headers)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def add_task(db_path: Path, kind: str = "task") -> int:
    now = datetime.now()
    values = coach_event(
        kind=kind,
        date=now.date().isoformat(),
        start_at=(now - timedelta(hours=1)).isoformat(timespec="seconds"),
        end_at=(now + timedelta(hours=1)).isoformat(timespec="seconds"),
    )
    conn = open_db(db_path)
    try:
        event_id = add_event(conn, values)
        conn.commit()
    finally:
        conn.close()
    return event_id


def mark_body(event_id: int, **fields: Any) -> dict[str, Any]:
    return {"event_id": event_id, "date": datetime.now().date().isoformat()} | fields


def test_post_mark_writes_and_answers_id(port: int, db_path: Path) -> None:
    event_id = add_task(db_path)
    body = mark_body(event_id, mark="rating", focus=4, fatigue=2, effort=3)
    status, answer = post(port, body)
    assert status == 200
    conn = open_db(db_path)
    try:
        [row] = conn.execute("SELECT * FROM focus_log").fetchall()
    finally:
        conn.close()
    assert json.loads(answer) == {"id": row["id"]}
    assert (row["event_id"], row["focus"]) == (event_id, 4)


def test_post_ok_is_json_and_error_is_plain_text(port: int, db_path: Path) -> None:
    event_id = add_task(db_path)
    types = []
    for body in (mark_body(event_id, mark="feel", score=3), mark_body(event_id, mark="slip")):
        raw = json.dumps(body).encode()
        headers = {"Content-Length": str(len(raw)), "Origin": f"http://127.0.0.1:{port}"}
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            conn.request("POST", "/api/mark", body=raw, headers=headers)
            types.append(conn.getresponse().getheader("Content-Type"))
        finally:
            conn.close()
    assert types == ["application/json; charset=utf-8", "text/plain; charset=utf-8"]


def test_post_done_answers_null_id(port: int, db_path: Path) -> None:
    event_id = add_task(db_path, "practice")
    status, answer = post(port, mark_body(event_id, mark="done", done=1))
    assert (status, json.loads(answer)) == (200, {"id": None})
    conn = open_db(db_path)
    try:
        assert conn.execute("SELECT done FROM done_log").fetchone()["done"] == 1
    finally:
        conn.close()


@pytest.mark.parametrize("origin", [None, "http://evil.example", "http://127.0.0.1:1"])
def test_post_without_own_origin_is_403_and_writes_nothing(
    port: int, db_path: Path, origin: str | None
) -> None:
    event_id = add_task(db_path)
    body = mark_body(event_id, mark="feel", score=3)
    status, _ = post(port, body, origin=origin)
    assert status == 403
    conn = open_db(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM wellbeing_log").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize("body", [b"not json", b"[1]", b"\xff"])
def test_post_bad_body_is_400(port: int, body: bytes) -> None:
    assert post(port, body)[0] == 400


def test_post_without_length_is_400(port: int) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest("POST", "/api/mark")
        conn.putheader("Origin", f"http://127.0.0.1:{port}")
        conn.endheaders()
        assert conn.getresponse().status == 400
    finally:
        conn.close()


def test_post_body_over_limit_is_413(port: int) -> None:
    status, _ = post(port, b"{}", length=64 * 1024 + 1)
    assert status == 413


def test_post_body_at_limit_is_read(port: int) -> None:
    body = b"{" + b" " * (64 * 1024 - 2) + b"}"
    assert post(port, body)[0] == 404


def test_post_other_path_is_404(port: int) -> None:
    assert post(port, {}, path="/api/day")[0] == 404


def test_post_mark_error_is_400_with_text(port: int, db_path: Path) -> None:
    event_id = add_task(db_path)
    status, answer = post(port, mark_body(event_id, mark="slip", text=""))
    assert status == 400
    assert answer.decode() == "Текст не может быть пустым."


def test_post_error_is_written_to_stderr(
    port: int, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    event_id = add_task(db_path)
    post(port, mark_body(event_id, mark="slip", text=""))
    assert "POST /api/mark 400 Текст не может быть пустым." in capsys.readouterr().err


def test_post_ok_writes_nothing_to_stderr(
    port: int, db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    event_id = add_task(db_path)
    post(port, mark_body(event_id, mark="feel", score=3))
    assert capsys.readouterr().err == ""


def test_post_missing_event_is_404(port: int) -> None:
    status, _ = post(port, mark_body(999, mark="feel", score=3))
    assert status == 404


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


class Reply(NamedTuple):
    headers: list[tuple[str, str]]
    body: bytes

    def header(self, name: str) -> str | None:
        return next((v for k, v in self.headers if k.lower() == name.lower()), None)


def fetch(port: int, path: str, method: str = "GET") -> Reply:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path)
        response = conn.getresponse()
        return Reply(response.getheaders(), response.read())
    finally:
        conn.close()


def test_not_found_is_plain_text_with_message(port: int) -> None:
    reply = fetch(port, "/nope")
    assert reply.header("Content-Type") == "text/plain; charset=utf-8"
    assert reply.body.decode() == "Не найдено."


def test_static_not_found_is_plain_text_with_message(port: int) -> None:
    reply = fetch(port, "/static/nope.js")
    assert reply.header("Content-Type") == "text/plain; charset=utf-8"
    assert reply.body.decode() == "Не найдено."


def test_method_not_allowed_message(port: int) -> None:
    reply = fetch(port, "/api/day", "PUT")
    assert reply.header("Content-Type") == "text/plain; charset=utf-8"
    assert reply.body.decode() == "Только GET."


def test_bad_date_message(port: int) -> None:
    reply = fetch(port, "/api/day?date=" + quote("мусор"))
    assert reply.body.decode() == "date: нужна дата YYYY-MM-DD."


def test_header_names_canonical_case_and_length(port: int) -> None:
    reply = fetch(port, "/api/day?date=2026-11-07")
    names = [k for k, _ in reply.headers]
    assert "Content-Type" in names
    assert "Content-Length" in names
    assert reply.header("Content-Length") == str(len(reply.body))


def test_api_day_content_type_json(port: int) -> None:
    reply = fetch(port, "/api/day?date=2026-11-07")
    assert reply.header("Content-Type") == "application/json; charset=utf-8"


def test_api_day_keeps_cyrillic_unescaped(port: int, db_path: Path) -> None:
    conn = open_db(db_path)
    add_event(
        conn,
        coach_event(
            date="2026-11-07",
            start_at="2026-11-07T09:00:00",
            end_at="2026-11-07T10:00:00",
            title="Пробежка",
        ),
    )
    conn.commit()
    conn.close()
    raw = fetch(port, "/api/day?date=2026-11-07").body
    assert "Пробежка".encode() in raw
    assert b"\\u" not in raw


def test_root_is_html_content_type(port: int) -> None:
    reply = fetch(port, "/")
    assert reply.header("Content-Type") == "text/html; charset=utf-8"


def test_static_trailing_slash_is_404(port: int) -> None:
    status, _ = request(port, "/static/pult.js/")
    assert status == 404


class _Calls:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.packages: list[str] = []
        self.parts: list[tuple[str, ...]] = []

    def files(self, package: str) -> "_Calls":
        self.packages.append(package)
        return self

    def joinpath(self, *parts: str) -> Path:
        self.parts.append(parts)
        return self.root.joinpath(*parts)


@pytest.fixture
def fake_static(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Calls:
    root = tmp_path / "pkg"
    (root / "static").mkdir(parents=True)
    calls = _Calls(root)
    monkeypatch.setattr(server_module.resources, "files", calls.files)
    return calls


def test_static_lookup_in_package_static_dir(port: int, fake_static: _Calls) -> None:
    (fake_static.root / "static" / "index.html").write_text("<p>x</p>")
    status, body = request(port, "/")
    assert status == 200
    assert body == b"<p>x</p>"
    assert fake_static.packages == ["ai_coach.web"]
    assert fake_static.parts == [("static", "index.html")]


def test_static_unknown_suffix_is_octet_stream(port: int, fake_static: _Calls) -> None:
    (fake_static.root / "static" / "data.bin").write_bytes(b"\x00\x01")
    reply = fetch(port, "/static/data.bin")
    assert reply.header("Content-Type") == "application/octet-stream; charset=utf-8"
    assert reply.body == b"\x00\x01"


def test_static_dotfile_is_404_even_if_exists(port: int, fake_static: _Calls) -> None:
    (fake_static.root / "static" / ".secret").write_text("x")
    status, _ = request(port, "/static/.secret")
    assert status == 404


class _FakeSocket:
    created: list[tuple[Any, ...]] = []
    connected: list[Any] = []
    closed = 0
    fail = False

    def __init__(self, *args: Any) -> None:
        type(self).created.append(args)

    def connect(self, address: Any) -> None:
        type(self).connected.append(address)
        if type(self).fail:
            raise OSError("нет сети")

    def getsockname(self) -> tuple[str, int]:
        return ("192.168.1.5", 54321)

    def close(self) -> None:
        type(self).closed += 1


@pytest.fixture
def fake_socket(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSocket]:
    _FakeSocket.created = []
    _FakeSocket.connected = []
    _FakeSocket.closed = 0
    _FakeSocket.fail = False
    monkeypatch.setattr(server_module.socket, "socket", _FakeSocket)
    return _FakeSocket


def test_lan_address_returns_host_part(fake_socket: type[_FakeSocket]) -> None:
    assert lan_address() == "192.168.1.5"
    assert fake_socket.closed == 1


def test_lan_address_probes_udp_without_sending(fake_socket: type[_FakeSocket]) -> None:
    lan_address()
    assert fake_socket.created == [(socket.AF_INET, socket.SOCK_DGRAM)]
    assert fake_socket.connected == [("10.255.255.255", 1)]


def test_lan_address_no_network_is_none_and_closes(fake_socket: type[_FakeSocket]) -> None:
    fake_socket.fail = True
    assert lan_address() is None
    assert fake_socket.closed == 1


def test_static_css_content_type(port: int) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/static/pult.css")
        response = conn.getresponse()
        response.read()
        assert response.getheader("Content-Type") == "text/css; charset=utf-8"
    finally:
        conn.close()


def test_post_other_path_text(port: int) -> None:
    assert post(port, {}, path="/api/day")[1].decode() == "Не найдено."


def test_post_foreign_origin_text(port: int) -> None:
    status, answer = post(port, {}, origin="http://evil.example")
    assert (status, answer.decode()) == (403, "Запись только со страницы пульта.")


def test_post_without_length_text(port: int) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest("POST", "/api/mark")
        conn.putheader("Origin", f"http://127.0.0.1:{port}")
        conn.endheaders()
        assert conn.getresponse().read().decode() == "Нужно тело запроса."
    finally:
        conn.close()


def test_post_over_limit_text(port: int) -> None:
    status, answer = post(port, b"{}", length=64 * 1024 + 1)
    assert (status, answer.decode()) == (413, "Тело слишком большое.")


def test_post_not_object_text(port: int) -> None:
    status, answer = post(port, b"[1]")
    assert (status, answer.decode()) == (400, "Нужен JSON-объект.")
