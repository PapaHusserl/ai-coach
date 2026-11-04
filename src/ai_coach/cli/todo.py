"""Команда `coach todo`: пункты ~/.claude/todo.json - чтение и запись."""

from datetime import date
from typing import Annotated

import typer

from ai_coach.cli.journal import fail
from ai_coach.workload import (
    TodoError,
    WorkloadConfigError,
    add_item,
    edit_item,
    load_config,
    move_item,
)
from ai_coach.workload.todo import active_items

todo_app = typer.Typer(help="Туду", no_args_is_help=True)


@todo_app.command("list")
def todo_list(
    all_items: Annotated[bool, typer.Option("--all", help="Вместе с закрытыми.")] = False,
) -> None:
    """Пункты туду: id, состояние, название (doing первыми); без --all - только открытые."""
    try:
        items = active_items(load_config().todo_path, include_closed=all_items)
    except (WorkloadConfigError, TodoError) as e:
        fail(str(e))
        return
    if not items:
        typer.echo("Туду пусто.")
    for item in items:
        typer.echo(f"{item['id']}  {item['state']}  {item['title']}")


@todo_app.command("add")
def todo_add(
    title: Annotated[str, typer.Argument(help="Название пункта.")],
    note: Annotated[str, typer.Option("--note", help="Заметка.")] = "",
) -> None:
    """Добавить пункт (состояние todo)."""
    try:
        item_id = add_item(load_config().todo_path, title, note, date.today())
    except (WorkloadConfigError, TodoError) as e:
        fail(str(e))
        return
    typer.echo(f"+ #{item_id} {title.strip()}")


def _move(item_id: int, state: str) -> None:
    try:
        move_item(load_config().todo_path, item_id, state, date.today())
    except (WorkloadConfigError, TodoError) as e:
        fail(str(e))
        return
    typer.echo(f"#{item_id} -> {state}")


@todo_app.command("start")
def todo_start(item_id: Annotated[int, typer.Argument(help="id пункта.")]) -> None:
    """Взять пункт в работу (doing)."""
    _move(item_id, "doing")


@todo_app.command("done")
def todo_done(item_id: Annotated[int, typer.Argument(help="id пункта.")]) -> None:
    """Закрыть пункт (done)."""
    _move(item_id, "done")


@todo_app.command("drop")
def todo_drop(item_id: Annotated[int, typer.Argument(help="id пункта.")]) -> None:
    """Отказаться от пункта (dropped)."""
    _move(item_id, "dropped")


@todo_app.command("reopen")
def todo_reopen(item_id: Annotated[int, typer.Argument(help="id пункта.")]) -> None:
    """Вернуть пункт в todo."""
    _move(item_id, "todo")


@todo_app.command("edit")
def todo_edit(
    item_id: Annotated[int, typer.Argument(help="id пункта.")],
    title: Annotated[str | None, typer.Option("--title", help="Новое название.")] = None,
    note: Annotated[str | None, typer.Option("--note", help="Новая заметка.")] = None,
) -> None:
    """Поменять название и/или заметку; состояние и дату не трогает."""
    if title is None and note is None:
        fail("Нужен --title или --note")
    try:
        edit_item(load_config().todo_path, item_id, title, note)
    except (WorkloadConfigError, TodoError) as e:
        fail(str(e))
        return
    typer.echo(f"#{item_id} изменён")
