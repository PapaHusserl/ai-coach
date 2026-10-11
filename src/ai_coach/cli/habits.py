"""Команда `coach habit`: привычки (да/нет за день и необязательное число)."""

from datetime import datetime
from typing import Annotated, Any

import typer

from ai_coach.cli.journal import check_date, fail, now
from ai_coach.cli.recipes import num, read_name
from ai_coach.cli.sport_nutrition import change, clear_field, find, remove, save
from ai_coach.store.db import open_db
from ai_coach.store.habits import (
    add_habit,
    delete_habit,
    edit_habit,
    get_habit,
    habits_on,
    mark_habit,
    unmark_habit,
)
from ai_coach.store.journal import wellbeing_day

habit_app = typer.Typer(help="Привычки", no_args_is_help=True)
DATE_HELP = "День, YYYY-MM-DD (по умолчанию как у coach feel: до 04:00 - вчера)"


def describe_habit(row: dict[str, Any]) -> str:
    unit = f", число в {row['unit']}" if row["unit"] else ""
    return f"{row['id']}  {row['name']}{unit}"


def habit_day(day: str | None) -> str:
    """День отметки: --date или день самочувствия (до 04:00 - вчера)."""
    if day is not None:
        return check_date(day)
    return wellbeing_day(datetime.fromisoformat(now()))


def mark(key: str, day: str | None, done: int | None, amount: float | None) -> None:
    """done: 1 - сделано, 0 - не сделано, None - снять отметку."""
    habit = find(get_habit, key, "Привычки")
    if amount is not None and not habit["unit"]:
        fail(f"У привычки {habit['name']} нет единицы: сначала задай --unit (coach habit edit).")
    when = habit_day(day)
    removed = False
    conn = open_db()
    try:
        with conn:
            if done is None:
                removed = unmark_habit(conn, habit["id"], when)
            else:
                mark_habit(conn, habit["id"], when, done, amount, now())
    finally:
        conn.close()
    if done is None and not removed:
        fail(f"Отметки привычки {habit['name']} за {when} нет.")
    what = {1: "отмечена", 0: "отмечена как не сделанная", None: "снята"}[done]
    typer.echo(f"Привычка {habit['name']} {what} за {when}.")


@habit_app.command("add")
def habit_add(
    name: Annotated[str, typer.Argument(help="Название")],
    unit: Annotated[
        str | None, typer.Option("--unit", help="Единица числа (мл, шагов); без - только да/нет")
    ] = None,
) -> None:
    """Завести привычку."""
    values = {"name": read_name(name), "unit": unit}
    typer.echo(f"Привычка {save(add_habit, values)} сохранена.")


@habit_app.command("list")
def habit_list(
    on: Annotated[str | None, typer.Option("--date", help=DATE_HELP)] = None,
) -> None:
    """Живые привычки с отметкой за день."""
    day = habit_day(on)
    conn = open_db()
    try:
        rows = habits_on(conn, day)
    finally:
        conn.close()
    if not rows:
        typer.echo("Привычек нет.")
    for row in rows:
        if row["done"] is None:
            state = "не отмечена"
        else:
            amount = ""
            if row["amount"] is not None:
                amount = f", {row['amount']:g} {row['unit'] or ''}".rstrip()
            state = ("сделано" if row["done"] else "нет") + amount
        typer.echo(f"{describe_habit(row)}  [{day}: {state}]")


# ignore_unknown_options: число вроде -1 доходит до проверки num, а не до разбора опций
@habit_app.command("done", context_settings={"ignore_unknown_options": True})
def habit_done(
    key: Annotated[str, typer.Argument(help="id или название")],
    amount: Annotated[str | None, typer.Argument(help="Число за день, необязательно")] = None,
    on: Annotated[str | None, typer.Option("--date", help=DATE_HELP)] = None,
    no: Annotated[bool, typer.Option("--no", help="Не сделано (done=0), без числа")] = False,
) -> None:
    """Отметить привычку за день: сделана, с --no - не сделана (повтор заменяет отметку)."""
    if no and amount is not None:
        fail("--no и число вместе нельзя.")
    mark(key, on, 0 if no else 1, num(amount, "Число"))


@habit_app.command("undo")
def habit_undo(
    key: Annotated[str, typer.Argument(help="id или название")],
    on: Annotated[str | None, typer.Option("--date", help=DATE_HELP)] = None,
) -> None:
    """Снять отметку за день (запись удаляется)."""
    mark(key, on, None, None)


@habit_app.command("edit")
def habit_edit(
    key: Annotated[str, typer.Argument(help="id или название (coach habit list)")],
    name: Annotated[str | None, typer.Option("--name", help="Новое название")] = None,
    unit: Annotated[str | None, typer.Option("--unit", help="Единица числа")] = None,
    clear_unit: Annotated[bool, typer.Option("--clear-unit", help="Убрать единицу")] = False,
) -> None:
    """Поправить название и/или единицу (что передано)."""
    fields: dict[str, Any] = {"name": read_name(name) if name is not None else None, "unit": unit}
    fields = {field: value for field, value in fields.items() if value is not None}
    clear_field(fields, "unit", unit, clear_unit, "--unit и --clear-unit")
    if not fields:
        fail("Нечего менять: нужен --name, --unit или --clear-unit.")
    habit_id = find(get_habit, key, "Привычки")["id"]
    change(edit_habit, habit_id, fields, "Привычки")
    typer.echo(f"Привычка {habit_id} исправлена.")


@habit_app.command("delete")
def habit_delete(key: Annotated[str, typer.Argument(help="id или название")]) -> None:
    """Удалить привычку (пометка, отметки остаются в базе)."""
    habit_id = find(get_habit, key, "Привычки")["id"]
    remove(delete_habit, habit_id, "Привычки")
    typer.echo(f"Привычка {habit_id} удалена.")
