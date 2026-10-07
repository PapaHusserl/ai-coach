"""Команды `coach protocol` и `coach supplement`: протоколы спортивного питания и добавки."""

from typing import Annotated, Any

import typer

from ai_coach.cli.journal import fail, now
from ai_coach.cli.recipes import num, read_name
from ai_coach.store.db import open_db
from ai_coach.store.sport_nutrition import (
    add_protocol,
    add_supplement,
    delete_protocol,
    delete_supplement,
    edit_protocol,
    edit_supplement,
    get_protocol,
    get_supplement,
    list_protocols,
    list_supplements,
)

protocol_app = typer.Typer(help="Протоколы спортивного питания", no_args_is_help=True)
supplement_app = typer.Typer(help="Добавки", no_args_is_help=True)
PHASES = ("before", "during", "after")
SPORTS = ("strength", "mobility", "run", "bike", "swim")
UNITS = ("g", "mg", "ml", "pcs")
SCHEDULES = ("daily", "training_day", "before", "after")
AMOUNTS = {
    "carbs_g": "--carbs",
    "protein_g": "--protein",
    "fluid_ml": "--fluid",
    "sodium_mg": "--sodium",
}
MINUTES = {"min_duration_min": "--min-duration", "offset_min": "--offset"}
PHASE_HELP = "before | during | after"
SPORT_HELP = "strength | mobility | run | bike | swim; без него - для любого вида"
SPORT_EDIT_HELP = "Вид спорта; сбросить нельзя - удалите и создайте заново"


def one_of(value: str | None, allowed: tuple[str, ...], option: str) -> str | None:
    if value is not None and value not in allowed:
        fail(f"{option} должен быть из {list(allowed)}, получено: {value!r}")
    return value


def minutes(text: str | None, option: str) -> int | None:
    """Целое число минут не меньше 0; None - не задано."""
    if text is None:
        return None
    try:
        value = int(text)
    except ValueError:
        fail(f"{option} должно быть целым числом минут, получено: {text!r}")
        return None
    if value < 0:
        fail(f"{option} не может быть меньше 0.")
    return value


def read_protocol(options: dict[str, str | None]) -> dict[str, Any]:
    """Опции протокола (поле -> текст) -> значения только заданных полей, с проверкой."""
    values: dict[str, Any] = {}
    for key, option in AMOUNTS.items():
        found = num(options[key], option)
        if found is not None:
            values[key] = found
    for key, option in MINUTES.items():
        found = minutes(options[key], option)
        if found is not None:
            values[key] = found
    return values


def check_not_empty(values: dict[str, Any]) -> None:
    if not any(values.get(key, 0) > 0 for key in AMOUNTS):
        fail("Протокол пустой: нужен хотя бы один из --carbs, --protein, --fluid, --sodium.")


def read_dose(text: str | None) -> float | None:
    dose = num(text, "--dose")
    if dose == 0:
        fail("--dose должна быть больше 0.")
    return dose


def describe_protocol(row: dict[str, Any]) -> str:
    unit = " в час" if row["phase"] == "during" else ""
    amounts = (
        f"У {row['carbs_g']:g} г, Б {row['protein_g']:g} г, "
        f"жидкость {row['fluid_ml']:g} мл, натрий {row['sodium_mg']:g} мг{unit}"
    )
    sport = row["sport"] or "любой вид"
    return (
        f"{row['id']}  {row['name']}  {row['phase']}, {sport}, от {row['min_duration_min']} мин, "
        f"смещение {row['offset_min']} мин: {amounts}"
    )


def describe_supplement(row: dict[str, Any]) -> str:
    when = f", {row['time_note']}" if row["time_note"] else ""
    return f"{row['id']}  {row['name']}  {row['dose']:g} {row['unit']}, {row['schedule']}{when}"


def show_note(row: dict[str, Any]) -> None:
    if row["note"]:
        typer.echo(f"Заметка: {row['note']}")


def find(getter: Any, key: str, what: str) -> dict[str, Any]:
    conn = open_db()
    try:
        found = getter(conn, int(key) if key.isdigit() else key)
    finally:
        conn.close()
    if found is None:
        fail(f"{what} {key!r} нет.")
    return found or {}


def save(adder: Any, values: dict[str, Any]) -> int:
    conn = open_db()
    try:
        with conn:
            return adder(conn, {**values, "created_at": now()})
    except ValueError as e:
        fail(str(e))
        return 0
    finally:
        conn.close()


def change(editor: Any, row_id: int, fields: dict[str, Any], what: str) -> None:
    conn = open_db()
    try:
        with conn:
            done = editor(conn, row_id, fields, now())
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    if not done:
        fail(f"{what} {row_id} нет или он удалён.")


def remove(deleter: Any, row_id: int, what: str) -> None:
    conn = open_db()
    try:
        with conn:
            done = deleter(conn, row_id, now())
    finally:
        conn.close()
    if not done:
        fail(f"{what} {row_id} нет или он уже удалён.")


@protocol_app.command("add")
def protocol_add(
    name: Annotated[str, typer.Argument(help="Название")],
    phase: Annotated[str, typer.Option("--phase", help=PHASE_HELP)],
    sport: Annotated[str | None, typer.Option("--sport", help=SPORT_HELP)] = None,
    min_duration: Annotated[
        str | None, typer.Option("--min-duration", help="Только для тренировок от N минут")
    ] = None,
    offset: Annotated[
        str | None, typer.Option("--offset", help="За сколько минут до / через сколько после")
    ] = None,
    carbs: Annotated[
        str | None, typer.Option("--carbs", help="Углеводы, г (в час для during)")
    ] = None,
    protein: Annotated[str | None, typer.Option("--protein", help="Белки, г")] = None,
    fluid: Annotated[str | None, typer.Option("--fluid", help="Жидкость, мл")] = None,
    sodium: Annotated[str | None, typer.Option("--sodium", help="Натрий, мг")] = None,
    note: Annotated[str | None, typer.Option("--note", help="Заметка")] = None,
) -> None:
    """Сохранить протокол питания до / во время / после тренировки."""
    name = read_name(name)
    one_of(phase, PHASES, "--phase")
    one_of(sport, SPORTS, "--sport")
    options = {
        "carbs_g": carbs,
        "protein_g": protein,
        "fluid_ml": fluid,
        "sodium_mg": sodium,
        "min_duration_min": min_duration,
        "offset_min": offset,
    }
    values = read_protocol(options)
    check_not_empty(values)
    values |= {"name": name, "phase": phase, "sport": sport, "note": note}
    typer.echo(f"Протокол {save(add_protocol, values)} сохранён.")


@protocol_app.command("list")
def protocol_list() -> None:
    """Все протоколы."""
    conn = open_db()
    try:
        rows = list_protocols(conn)
    finally:
        conn.close()
    if not rows:
        typer.echo("Протоколов нет.")
    for row in rows:
        typer.echo(describe_protocol(row))


@protocol_app.command("show")
def protocol_show(key: Annotated[str, typer.Argument(help="id или название")]) -> None:
    """Протокол с заметкой."""
    row = find(get_protocol, key, "Протокола")
    typer.echo(describe_protocol(row))
    show_note(row)


@protocol_app.command("edit")
def protocol_edit(
    protocol_id: Annotated[int, typer.Argument(help="id протокола (coach protocol list)")],
    name: Annotated[str | None, typer.Option("--name", help="Новое название")] = None,
    phase: Annotated[str | None, typer.Option("--phase", help=PHASE_HELP)] = None,
    sport: Annotated[str | None, typer.Option("--sport", help=SPORT_EDIT_HELP)] = None,
    min_duration: Annotated[
        str | None, typer.Option("--min-duration", help="Только для тренировок от N минут")
    ] = None,
    offset: Annotated[
        str | None, typer.Option("--offset", help="За сколько минут до / через сколько после")
    ] = None,
    carbs: Annotated[str | None, typer.Option("--carbs", help="Углеводы, г")] = None,
    protein: Annotated[str | None, typer.Option("--protein", help="Белки, г")] = None,
    fluid: Annotated[str | None, typer.Option("--fluid", help="Жидкость, мл")] = None,
    sodium: Annotated[str | None, typer.Option("--sodium", help="Натрий, мг")] = None,
    note: Annotated[str | None, typer.Option("--note", help="Заметка")] = None,
) -> None:
    """Поправить протокол (что передано)."""
    options = {
        "carbs_g": carbs,
        "protein_g": protein,
        "fluid_ml": fluid,
        "sodium_mg": sodium,
        "min_duration_min": min_duration,
        "offset_min": offset,
    }
    fields = read_protocol(options)
    fields |= {"phase": one_of(phase, PHASES, "--phase"), "sport": one_of(sport, SPORTS, "--sport")}
    fields |= {"note": note}
    if name is not None:
        fields["name"] = read_name(name)
    fields = {key: value for key, value in fields.items() if value is not None}
    if not fields:
        fail("Нечего менять: нужен хотя бы один параметр протокола.")
    old = find(get_protocol, str(protocol_id), "Протокола")
    check_not_empty({**old, **fields})
    change(edit_protocol, protocol_id, fields, "Протокола")
    typer.echo(f"Протокол {protocol_id} исправлен.")


@protocol_app.command("delete")
def protocol_delete(protocol_id: Annotated[int, typer.Argument(help="id протокола")]) -> None:
    """Удалить протокол (пометка, строка остаётся в базе)."""
    remove(delete_protocol, protocol_id, "Протокола")
    typer.echo(f"Протокол {protocol_id} удалён.")


@supplement_app.command("add")
def supplement_add(
    name: Annotated[str, typer.Argument(help="Название")],
    dose: Annotated[str, typer.Option("--dose", help="Доза за приём, больше 0")],
    unit: Annotated[str, typer.Option("--unit", help="g | mg | ml | pcs")],
    schedule: Annotated[
        str, typer.Option("--schedule", help="daily | training_day | before | after")
    ],
    time_note: Annotated[str | None, typer.Option("--time-note", help="Когда принимать")] = None,
    note: Annotated[str | None, typer.Option("--note", help="Заметка")] = None,
) -> None:
    """Сохранить добавку: доза за приём и график."""
    name = read_name(name)
    one_of(unit, UNITS, "--unit")
    one_of(schedule, SCHEDULES, "--schedule")
    values = {"name": name, "dose": read_dose(dose), "unit": unit, "schedule": schedule}
    values |= {"time_note": time_note, "note": note}
    typer.echo(f"Добавка {save(add_supplement, values)} сохранена.")


@supplement_app.command("list")
def supplement_list() -> None:
    """Все добавки."""
    conn = open_db()
    try:
        rows = list_supplements(conn)
    finally:
        conn.close()
    if not rows:
        typer.echo("Добавок нет.")
    for row in rows:
        typer.echo(describe_supplement(row))


@supplement_app.command("show")
def supplement_show(key: Annotated[str, typer.Argument(help="id или название")]) -> None:
    """Добавка с заметкой."""
    row = find(get_supplement, key, "Добавки")
    typer.echo(describe_supplement(row))
    show_note(row)


@supplement_app.command("edit")
def supplement_edit(
    supplement_id: Annotated[int, typer.Argument(help="id добавки (coach supplement list)")],
    name: Annotated[str | None, typer.Option("--name", help="Новое название")] = None,
    dose: Annotated[str | None, typer.Option("--dose", help="Доза за приём, больше 0")] = None,
    unit: Annotated[str | None, typer.Option("--unit", help="g | mg | ml | pcs")] = None,
    schedule: Annotated[
        str | None, typer.Option("--schedule", help="daily | training_day | before | after")
    ] = None,
    time_note: Annotated[str | None, typer.Option("--time-note", help="Когда принимать")] = None,
    note: Annotated[str | None, typer.Option("--note", help="Заметка")] = None,
) -> None:
    """Поправить добавку (что передано)."""
    fields: dict[str, Any] = {
        "dose": read_dose(dose),
        "unit": one_of(unit, UNITS, "--unit"),
        "schedule": one_of(schedule, SCHEDULES, "--schedule"),
        "time_note": time_note,
        "note": note,
        "name": read_name(name) if name is not None else None,
    }
    fields = {key: value for key, value in fields.items() if value is not None}
    if not fields:
        fail("Нечего менять: нужен хотя бы один параметр добавки.")
    change(edit_supplement, supplement_id, fields, "Добавки")
    typer.echo(f"Добавка {supplement_id} исправлена.")


@supplement_app.command("delete")
def supplement_delete(supplement_id: Annotated[int, typer.Argument(help="id добавки")]) -> None:
    """Удалить добавку (пометка, строка остаётся в базе)."""
    remove(delete_supplement, supplement_id, "Добавки")
    typer.echo(f"Добавка {supplement_id} удалена.")
