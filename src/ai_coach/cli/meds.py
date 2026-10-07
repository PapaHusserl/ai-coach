"""Команда `coach med`: курсы витаминов, минералов, электролитов и безрецептурных средств."""

from datetime import date
from typing import Annotated, Any

import typer

from ai_coach.cli.journal import check_date, fail
from ai_coach.cli.recipes import read_name
from ai_coach.cli.sport_nutrition import (
    SCHEDULES,
    change,
    clear_field,
    find,
    one_of,
    read_dose,
    remove,
    save,
    show_note,
)
from ai_coach.store.db import open_db
from ai_coach.store.meds import add_med, delete_med, edit_med, get_med, list_meds, meds_on

med_app = typer.Typer(help="Курсы витаминов и безрецептурных средств", no_args_is_help=True)
KINDS = ("vitamin", "mineral", "electrolyte", "otc")
UNITS = ("mg", "mcg", "iu", "g", "ml", "pcs")
KIND_HELP = "vitamin | mineral | electrolyte | otc"
UNIT_HELP = "mg | mcg | iu | g | ml | pcs"
SCHEDULE_HELP = "daily | training_day | before | after"


def describe_med(row: dict[str, Any]) -> str:
    when = f", {row['time_note']}" if row["time_note"] else ""
    end = row["end_date"] or "бессрочно"
    return (
        f"{row['id']}  {row['name']}  {row['kind']}, {row['dose']:g} {row['unit']}, "
        f"{row['schedule']}{when}; {row['start_date']} - {end}"
    )


def check_period(start: str, end: str | None) -> None:
    if end is not None and end < start:
        fail("--end не может быть раньше --start.")


@med_app.command("add")
def med_add(
    name: Annotated[str, typer.Argument(help="Название")],
    kind: Annotated[str, typer.Option("--kind", help=KIND_HELP)],
    dose: Annotated[str, typer.Option("--dose", help="Доза за приём, больше 0")],
    unit: Annotated[str, typer.Option("--unit", help=UNIT_HELP)],
    schedule: Annotated[str, typer.Option("--schedule", help=SCHEDULE_HELP)],
    start: Annotated[
        str | None, typer.Option("--start", help="Начало, YYYY-MM-DD, обязательно")
    ] = None,
    end: Annotated[
        str | None, typer.Option("--end", help="Конец, YYYY-MM-DD; без него - бессрочно")
    ] = None,
    time_note: Annotated[str | None, typer.Option("--time-note", help="Когда принимать")] = None,
    note: Annotated[str | None, typer.Option("--note", help="Заметка")] = None,
) -> None:
    """Сохранить курс: что, доза за приём, график, с какого по какое число."""
    name = read_name(name)
    one_of(kind, KINDS, "--kind")
    one_of(unit, UNITS, "--unit")
    one_of(schedule, SCHEDULES, "--schedule")
    if start is None:
        fail("--start обязателен: укажи дату начала курса, YYYY-MM-DD.")
        return
    first = check_date(start)
    last = check_date(end) if end is not None else None
    check_period(first, last)
    values = {"name": name, "kind": kind, "dose": read_dose(dose), "unit": unit}
    values |= {"schedule": schedule, "start_date": first, "end_date": last}
    values |= {"time_note": time_note, "note": note}
    typer.echo(f"Курс {save(add_med, values)} сохранён.")


@med_app.command("list")
def med_list(
    on: Annotated[
        str | None, typer.Option("--date", help="Курсы на дату; по умолчанию сегодня")
    ] = None,
    all_courses: Annotated[
        bool, typer.Option("--all", help="Все курсы, в т.ч. закончившиеся")
    ] = False,
) -> None:
    """Курсы на дату или все."""
    if all_courses and on is not None:
        fail("--date и --all вместе нельзя.")
    day = check_date(on) if on is not None else date.today().isoformat()
    conn = open_db()
    try:
        rows = list_meds(conn) if all_courses else meds_on(conn, day)
    finally:
        conn.close()
    if not rows:
        typer.echo("Курсов нет.")
    for row in rows:
        typer.echo(describe_med(row))


@med_app.command("show")
def med_show(key: Annotated[str, typer.Argument(help="id или название")]) -> None:
    """Курс с заметкой."""
    row = find(get_med, key, "Курса")
    typer.echo(describe_med(row))
    show_note(row)


@med_app.command("edit")
def med_edit(
    med_id: Annotated[int, typer.Argument(help="id курса (coach med list --all)")],
    name: Annotated[str | None, typer.Option("--name", help="Новое название")] = None,
    kind: Annotated[str | None, typer.Option("--kind", help=KIND_HELP)] = None,
    dose: Annotated[str | None, typer.Option("--dose", help="Доза за приём, больше 0")] = None,
    unit: Annotated[str | None, typer.Option("--unit", help=UNIT_HELP)] = None,
    schedule: Annotated[str | None, typer.Option("--schedule", help=SCHEDULE_HELP)] = None,
    start: Annotated[str | None, typer.Option("--start", help="Начало, YYYY-MM-DD")] = None,
    end: Annotated[str | None, typer.Option("--end", help="Конец, YYYY-MM-DD")] = None,
    time_note: Annotated[str | None, typer.Option("--time-note", help="Когда принимать")] = None,
    note: Annotated[str | None, typer.Option("--note", help="Заметка")] = None,
    no_end: Annotated[bool, typer.Option("--no-end", help="Сделать курс бессрочным")] = False,
    clear_time_note: Annotated[
        bool, typer.Option("--clear-time-note", help="Убрать пометку о времени")
    ] = False,
    clear_note: Annotated[bool, typer.Option("--clear-note", help="Убрать заметку")] = False,
) -> None:
    """Поправить курс (что передано)."""
    fields: dict[str, Any] = {
        "kind": one_of(kind, KINDS, "--kind"),
        "dose": read_dose(dose),
        "unit": one_of(unit, UNITS, "--unit"),
        "schedule": one_of(schedule, SCHEDULES, "--schedule"),
        "start_date": check_date(start) if start is not None else None,
        "end_date": check_date(end) if end is not None else None,
        "time_note": time_note,
        "note": note,
        "name": read_name(name) if name is not None else None,
    }
    fields = {key: value for key, value in fields.items() if value is not None}
    clear_field(fields, "end_date", end, no_end, "--end и --no-end")
    clear_field(fields, "time_note", time_note, clear_time_note, "--time-note и --clear-time-note")
    clear_field(fields, "note", note, clear_note, "--note и --clear-note")
    if not fields:
        fail("Нечего менять: нужен хотя бы один параметр курса.")
    old = find(get_med, str(med_id), "Курса")
    merged = {**old, **fields}
    check_period(merged["start_date"], merged["end_date"])
    change(edit_med, med_id, fields, "Курса")
    typer.echo(f"Курс {med_id} исправлен.")


@med_app.command("delete")
def med_delete(med_id: Annotated[int, typer.Argument(help="id курса")]) -> None:
    """Удалить курс (пометка, строка остаётся в базе)."""
    remove(delete_med, med_id, "Курса")
    typer.echo(f"Курс {med_id} удалён.")
