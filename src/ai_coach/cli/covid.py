"""Команда `coach covid`: отметка COVID за день (положительный тест) и её снятие."""

from datetime import date, timedelta
from typing import Annotated

import typer

from ai_coach.cli.habits import DATE_HELP, habit_day
from ai_coach.cli.journal import fail, now
from ai_coach.store.db import open_db
from ai_coach.store.journal import list_covid_marks, mark_covid, unmark_covid

HINT_DAYS = 21


def covid(
    on: Annotated[str | None, typer.Option("--date", help=DATE_HELP)] = None,
    undo: Annotated[bool, typer.Option("--undo", help="Снять отметку за день")] = False,
) -> None:
    """Отметить COVID за день (положительный тест); повтор ничего не меняет."""
    conn = open_db()
    try:
        day = habit_day(on)
        if day > date.today().isoformat():
            fail("--date в будущем.")
        with conn:
            if not undo:
                mark_covid(conn, day, now())
                typer.echo(f"COVID отмечен за {day}.")
                return
            if unmark_covid(conn, day):
                typer.echo(f"Отметка COVID за {day} снята.")
                return
        today = habit_day(None)
        start = (date.fromisoformat(today) - timedelta(days=HINT_DAYS - 1)).isoformat()
        others = list_covid_marks(conn, start, today)
    finally:
        conn.close()
    hint = f" Есть за: {', '.join(others)}." if others else ""
    fail(f"Отметки COVID за {day} нет.{hint}")
