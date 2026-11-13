"""Команда `coach status`: что запланировано и отправлено."""

from typing import Annotated

import typer

from ai_coach.cli.journal import check_date, fail
from ai_coach.store.db import open_db
from ai_coach.store.plans import list_planned_workouts


def status(
    day: Annotated[str | None, typer.Option("--date", help="Один день, YYYY-MM-DD")] = None,
    date_from: Annotated[
        str | None, typer.Option("--from", help="С даты включительно, YYYY-MM-DD")
    ] = None,
    date_to: Annotated[
        str | None, typer.Option("--to", help="По дату включительно, YYYY-MM-DD")
    ] = None,
) -> None:
    """Что запланировано и отправлено (можно за день или период)."""
    if day is not None and (date_from is not None or date_to is not None):
        fail("--date нельзя вместе с --from/--to.")
    for value in (day, date_from, date_to):
        if value is not None:
            check_date(value)
    if day is not None:
        date_from = day
        date_to = day
    start = date_from or "0000-01-01"
    end = date_to or "9999-12-31"
    if start > end:
        fail("--from позже --to.")
    conn = open_db()
    try:
        rows = list_planned_workouts(conn, start, end)
    finally:
        conn.close()
    if not rows:
        typer.echo("Тренировок нет.")
    for row in rows:
        sent = f", отправлена {row['pushed_at']}" if row["pushed_at"] else ""
        typer.echo(
            f"{row['id']}  {row['date']}  {row['sport']}  {row['name']}  [{row['status']}{sent}]"
        )
