"""Команды `coach`: login, sync, import."""

from getpass import getpass
from pathlib import Path
from typing import Annotated

import typer

from ai_coach.garmin import (
    TOKEN_NAME,
    GarminAuthError,
    GarminError,
    full_login,
    load_client,
    token_dir,
)
from ai_coach.store.db import open_db
from ai_coach.sync import FitImportError, import_fit
from ai_coach.sync import sync as run_sync

app = typer.Typer(help="Личный ИИ-тренер на данных Garmin", no_args_is_help=True)

ZIP_UNSUPPORTED = (
    "Разбор полного экспорта (zip) пока не поддерживается. Передай FIT активности (.fit)."
)


def fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


@app.command()
def login() -> None:
    """Полный логин Garmin (пароль через getpass). Запускать в обычном терминале."""
    try:
        if (token_dir() / TOKEN_NAME).exists():
            try:
                load_client()
            except GarminAuthError:
                typer.echo("Токены протухли, нужен полный логин.")
            else:
                typer.echo("Токены найдены и работают, пароль не нужен.")
                return
        email = getpass("Garmin email (ввод скрыт): ")
        password = getpass("Garmin пароль (ввод скрыт): ")
        full_login(email, password, lambda: getpass("Код MFA: "))
    except GarminError as e:
        fail(str(e))
    typer.echo(f"Логин прошёл, токены: {token_dir() / TOKEN_NAME}")


@app.command()
def sync(days: Annotated[int, typer.Option(help="За сколько последних дней")] = 7) -> None:
    """Загрузить метрики, активности и подходы силовой из Garmin в базу."""
    try:
        client = load_client()
    except GarminError as e:
        fail(str(e))
        return
    conn = open_db()
    try:
        typer.echo(run_sync(conn, client, days, pause=0.5))
    except GarminError as e:
        fail(str(e))
    finally:
        conn.close()


@app.command("import")
def import_(
    path: Annotated[Path, typer.Argument(help="FIT активности")],
    activity_id: Annotated[
        int | None, typer.Option("--id", help="id активности, если его нет в имени файла")
    ] = None,
) -> None:
    """Импортировать FIT активности (без сети)."""
    if path.suffix.lower() == ".zip":
        fail(ZIP_UNSUPPORTED)
    if not path.is_file():
        fail(f"Файл не найден: {path}")
    conn = open_db()
    try:
        typer.echo(import_fit(conn, path, activity_id))
    except FitImportError as e:
        fail(str(e))
    finally:
        conn.close()
