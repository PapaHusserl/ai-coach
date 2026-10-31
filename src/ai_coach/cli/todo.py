"""Команда `coach todo`: активные пункты ~/.claude/todo.json (только чтение)."""

import typer

from ai_coach.cli.journal import fail
from ai_coach.workload import TodoError, WorkloadConfigError, load_config
from ai_coach.workload.todo import active_items

todo_app = typer.Typer(help="Туду (только чтение)", no_args_is_help=True)


@todo_app.command("list")
def todo_list() -> None:
    """Активные пункты туду: id, состояние, название (doing первыми)."""
    try:
        items = active_items(load_config().todo_path)
    except (WorkloadConfigError, TodoError) as e:
        fail(str(e))
        return
    if not items:
        typer.echo("Туду пусто.")
    for item in items:
        typer.echo(f"{item['id']}  {item['state']}  {item['title']}")
