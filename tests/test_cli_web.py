"""coach web: хост по умолчанию, занятый порт, вывод (шаг П1, партия 2, Р2, Р6, Р11)."""

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.cli import web as web_cli

runner = CliRunner()


class FakeServer:
    closed = False

    def serve_forever(self) -> None:
        raise KeyboardInterrupt

    def server_close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_COACH_DB", str(tmp_path / "coach.db"))


@pytest.fixture
def made(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    def fake_make(host: str, port: int, *rest: Any) -> FakeServer:
        calls.append((host, port))
        return FakeServer()

    monkeypatch.setattr(web_cli, "make_server", fake_make)
    monkeypatch.setattr(web_cli, "lan_address", lambda: "192.168.1.5")
    return calls


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    urls: list[str] = []
    monkeypatch.setattr(web_cli.webbrowser, "open", lambda url: urls.append(url))
    return urls


@pytest.fixture
def busy_port() -> Iterator[int]:
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen()
    yield blocker.getsockname()[1]
    blocker.close()


def test_default_host_is_all_interfaces(made: list[tuple[Any, ...]], opened: list[str]) -> None:
    result = runner.invoke(main.app, ["web"])
    assert result.exit_code == 0
    assert made == [("0.0.0.0", 8765)]


def test_prints_addresses_and_no_password_note(
    made: list[tuple[Any, ...]], opened: list[str]
) -> None:
    result = runner.invoke(main.app, ["web"])
    assert "http://127.0.0.1:8765/" in result.output
    assert "http://192.168.1.5:8765/" in result.output
    assert "без пароля" in result.output


def test_ctrl_c_prints_stop_message(made: list[tuple[Any, ...]], opened: list[str]) -> None:
    result = runner.invoke(main.app, ["web"])
    assert "Пульт остановлен." in result.output


def test_opens_browser_by_default(made: list[tuple[Any, ...]], opened: list[str]) -> None:
    runner.invoke(main.app, ["web"])
    assert opened == ["http://127.0.0.1:8765/"]


def test_no_open_skips_browser(made: list[tuple[Any, ...]], opened: list[str]) -> None:
    runner.invoke(main.app, ["web", "--no-open"])
    assert opened == []


def test_local_host_hides_lan_address(made: list[tuple[Any, ...]], opened: list[str]) -> None:
    result = runner.invoke(main.app, ["web", "--host", "127.0.0.1", "--no-open"])
    assert "192.168.1.5" not in result.output


def test_busy_port_is_clear_error(busy_port: int, opened: list[str]) -> None:
    result = runner.invoke(main.app, ["web", "--host", "127.0.0.1", "--port", str(busy_port)])
    assert result.exit_code == 1
    assert f"Порт {busy_port} не открыт" in result.output
    assert "Traceback" not in result.output
    assert opened == []
