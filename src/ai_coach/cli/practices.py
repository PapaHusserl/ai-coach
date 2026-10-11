"""Команда `coach practice`: справочник практик восстановления (дыхание, пауза, прогулка, сон)."""

from typing import Annotated, Any

import typer

from ai_coach.cli.journal import fail
from ai_coach.cli.recipes import read_name
from ai_coach.cli.sport_nutrition import find, minutes, one_of, save
from ai_coach.store.db import open_db
from ai_coach.store.practices import add_practice, get_practice, list_practices

practice_app = typer.Typer(help="Практики восстановления", no_args_is_help=True)
KINDS = ("breathing", "pause", "walk", "sleep")
KIND_HELP = "breathing | pause | walk | sleep"


def describe_practice(row: dict[str, Any]) -> str:
    length = f", {row['minutes']} мин" if row["minutes"] else ""
    when = f"; когда: {row['trigger']}" if row["trigger"] else ""
    return f"{row['id']}  {row['name']}  {row['kind']}{length}{when}"


@practice_app.command("add")
def practice_add(
    name: Annotated[str, typer.Argument(help="Название")],
    kind: Annotated[str, typer.Option("--kind", help=KIND_HELP)],
    minutes_text: Annotated[
        str | None, typer.Option("--minutes", help="Длительность, мин, больше 0")
    ] = None,
    steps: Annotated[str | None, typer.Option("--steps", help="Шаги текстом")] = None,
    trigger: Annotated[
        str | None, typer.Option("--trigger", help="Когда применять (признак, сигнал)")
    ] = None,
) -> None:
    """Сохранить практику: вид, длительность, когда применять и шаги."""
    name = read_name(name)
    one_of(kind, KINDS, "--kind")
    length = minutes(minutes_text, "--minutes")
    if length == 0:
        fail("--minutes должно быть больше 0.")
    values = {
        "name": name,
        "kind": kind,
        "minutes": length,
        "trigger": trigger.strip() if trigger else None,
    }
    values |= {"steps": steps.strip() if steps else None}
    typer.echo(f"Практика {save(add_practice, values)} сохранена.")


@practice_app.command("list")
def practice_list() -> None:
    """Все практики."""
    conn = open_db()
    try:
        rows = list_practices(conn)
    finally:
        conn.close()
    if not rows:
        typer.echo("Практик нет.")
    for row in rows:
        typer.echo(describe_practice(row))


@practice_app.command("show")
def practice_show(key: Annotated[str, typer.Argument(help="id или название")]) -> None:
    """Практика с шагами."""
    row = find(get_practice, key, "Практики")
    typer.echo(describe_practice(row))
    if row["steps"]:
        typer.echo(f"Шаги: {row['steps']}")
