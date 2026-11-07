"""Команда `coach web`: пульт, план дня в браузере. Живёт до Ctrl-C."""

import webbrowser
from typing import Annotated

import typer

from ai_coach.cli.journal import fail
from ai_coach.web.server import lan_address, make_server


def web(
    host: Annotated[str, typer.Option(help="Адрес; 0.0.0.0 - доступно и из домашней сети.")] = (
        "0.0.0.0"
    ),
    port: Annotated[int, typer.Option(help="Порт.")] = 8765,
    no_open: Annotated[bool, typer.Option("--no-open", help="Не открывать браузер.")] = False,
) -> None:
    """Пульт: план дня в браузере (читает базу, без пароля). Остановка - Ctrl-C."""
    try:
        server = make_server(host, port)
    except OSError as e:
        fail(f"Порт {port} не открыт: {e.strerror or e}.")
    typer.echo(f"Пульт: http://127.0.0.1:{port}/")
    lan = lan_address()
    if host == "0.0.0.0" and lan:
        typer.echo(f"С телефона в этой сети: http://{lan}:{port}/ (без пароля, видит любой в сети)")
    if not no_open:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        typer.echo("Пульт остановлен.")
    finally:
        server.server_close()
