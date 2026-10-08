"""Команды `coach supplement take|log|untake`: журнал приёма добавок (подключены в main.py)."""

from datetime import date
from typing import Annotated, Any

import typer

from ai_coach.cli.journal import check_date, fail, now
from ai_coach.cli.sport_nutrition import find, read_dose, remove
from ai_coach.store.db import open_db
from ai_coach.store.intake import delete_intake, list_intake, log_intake
from ai_coach.store.sport_nutrition import get_supplement


def describe_intake(row: dict[str, Any]) -> str:
    dose = f"{row['dose']:g} {row['unit']}" if row["dose"] is not None else "по норме"
    note = f", {row['note']}" if row["note"] else ""
    return f"{row['id']}  {row['date']} {row['taken_at'][11:16]}  {row['name']}  {dose}{note}"


def supplement_take(
    key: Annotated[str, typer.Argument(help="id или название добавки")],
    on: Annotated[
        str | None, typer.Option("--date", help="День приёма; по умолчанию сегодня")
    ] = None,
    dose: Annotated[
        str | None, typer.Option("--dose", help="Принятая доза; без неё - по норме")
    ] = None,
    note: Annotated[str | None, typer.Option("--note", help="Заметка")] = None,
) -> None:
    """Отметить приём добавки (можно несколько раз в день)."""
    day = check_date(on) if on is not None else date.today().isoformat()
    if day > date.today().isoformat():
        fail("--date в будущем.")
    taken_dose = read_dose(dose)
    supplement = find(get_supplement, key, "Добавки")
    values = {"item_id": supplement["id"], "date": day, "taken_at": now()}
    values |= {"dose": taken_dose, "note": note}
    conn = open_db()
    try:
        with conn:
            log_id = log_intake(conn, values)
    finally:
        conn.close()
    typer.echo(f"Приём {log_id} записан: {supplement['name']}, {day}.")


def supplement_log(
    on: Annotated[str | None, typer.Option("--date", help="День; по умолчанию сегодня")] = None,
    date_from: Annotated[str | None, typer.Option("--from", help="Начало периода")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="Конец периода")] = None,
) -> None:
    """Приёмы добавок за день или период."""
    if on is not None and (date_from is not None or date_to is not None):
        fail("--date и --from/--to вместе нельзя.")
    if (date_from is None) != (date_to is None):
        fail("--from и --to нужны вместе.")
    if date_from is not None and date_to is not None:
        first, last = check_date(date_from), check_date(date_to)
    else:
        first = last = check_date(on) if on is not None else date.today().isoformat()
    if last < first:
        fail("--to не может быть раньше --from.")
    conn = open_db()
    try:
        rows = list_intake(conn, first, last)
    finally:
        conn.close()
    if not rows:
        typer.echo("Приёмов нет.")
    for row in rows:
        typer.echo(describe_intake(row))


def supplement_untake(
    log_id: Annotated[int, typer.Argument(help="id приёма (coach supplement log)")],
) -> None:
    """Удалить отметку приёма (пометка, строка остаётся в базе)."""
    remove(delete_intake, log_id, "Приёма")
    typer.echo(f"Приём {log_id} удалён.")
