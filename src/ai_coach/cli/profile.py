"""Команды `coach profile|goal`: профиль спортсмена и цели."""

from datetime import date
from typing import Annotated, Any

import typer

from ai_coach.cli.journal import check_date, fail, now
from ai_coach.goals import create_goal, list_goals, update_goal
from ai_coach.profile import current_profile, set_value
from ai_coach.store.db import open_db

profile_app = typer.Typer(help="Профиль спортсмена", no_args_is_help=True)
goal_app = typer.Typer(help="Цели", no_args_is_help=True)


@profile_app.command("show")
def profile_show() -> None:
    """Текущий профиль: значения с источниками и что ещё не заполнено."""
    conn = open_db()
    try:
        profile = current_profile(conn, date.today().isoformat())
    finally:
        conn.close()
    for key, entry in profile["values"].items():
        typer.echo(f"{key}: {entry['value']} ({entry['source']})")
    if profile["missing"]:
        typer.echo(f"Не заполнено: {', '.join(profile['missing'])}")


@profile_app.command("set")
def profile_set(
    key: Annotated[str, typer.Argument(help="Ключ профиля")],
    value: Annotated[str, typer.Argument(help="Значение")],
) -> None:
    """Записать значение профиля (ручное главнее Garmin). Записи только добавляются."""
    conn = open_db()
    try:
        with conn:
            set_value(conn, key, value, "manual", now())
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(f"{key} записан.")


@goal_app.command("add")
def goal_add(
    title: Annotated[str, typer.Argument(help="Название цели")],
    kind: Annotated[str | None, typer.Option(help="Вид цели")] = None,
    target: Annotated[str | None, typer.Option(help="Чего достичь")] = None,
    target_date: Annotated[str | None, typer.Option("--date", help="Срок, YYYY-MM-DD")] = None,
    priority: Annotated[int, typer.Option(help="Приоритет")] = 0,
) -> None:
    """Добавить цель."""
    if target_date is not None:
        check_date(target_date)
    fields: dict[str, Any] = {
        "kind": kind,
        "target": target,
        "target_date": target_date,
        "priority": priority,
    }
    conn = open_db()
    try:
        with conn:
            goal_id = create_goal(conn, title.strip(), **fields)
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(f"Цель {goal_id} добавлена.")


@goal_app.command("list")
def goal_list() -> None:
    """Все цели."""
    conn = open_db()
    try:
        goals = list_goals(conn)
    finally:
        conn.close()
    if not goals:
        typer.echo("Целей нет.")
    for goal in goals:
        due = f", до {goal['target_date']}" if goal["target_date"] else ""
        typer.echo(f"{goal['id']}  {goal['title']}  [{goal['status']}{due}]")


def close_goal(goal_id: int, status: str) -> None:
    conn = open_db()
    try:
        with conn:
            update_goal(conn, goal_id, {"status": status})
    except LookupError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(f"Цель {goal_id}: {status}.")


@goal_app.command("done")
def goal_done(goal_id: Annotated[int, typer.Argument(help="id цели")]) -> None:
    """Цель достигнута."""
    close_goal(goal_id, "done")


@goal_app.command("cancel")
def goal_cancel(goal_id: Annotated[int, typer.Argument(help="id цели")]) -> None:
    """Цель отменена."""
    close_goal(goal_id, "cancelled")
