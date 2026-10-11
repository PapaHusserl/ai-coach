"""Команда `coach review`: отметка проведённого недельного обзора."""

from datetime import date, datetime
from typing import Annotated

import typer

from ai_coach.cli.journal import check_date, fail, now
from ai_coach.review import review_week
from ai_coach.store.db import open_db
from ai_coach.store.review import mark_review

review_app = typer.Typer(help="Недельный обзор", no_args_is_help=True)


@review_app.command("done")
def review_done(
    note: Annotated[str | None, typer.Argument(help="Заметка, как есть")] = None,
    week: Annotated[
        str | None,
        typer.Option(
            "--week",
            help="Понедельник недели, YYYY-MM-DD (по умолчанию: в Пн - прошедшая неделя, "
            "в остальные дни - текущая; до 04:00 - как у coach feel)",
        ),
    ] = None,
) -> None:
    """Отметить недельный обзор проведённым (повтор заменяет запись, заметка без новой остаётся)."""
    moment = now()
    if week is None:
        start = review_week(datetime.fromisoformat(moment))
    else:
        start = check_date(week)
        if date.fromisoformat(start).weekday() != 0:
            fail("--week: нужен понедельник.")
    conn = open_db()
    try:
        with conn:
            values = {"week_start": start, "done_at": moment}
            if note is not None:
                values["note"] = note
            mark_review(conn, values)
    finally:
        conn.close()
    typer.echo(f"Обзор недели с {start} отмечен.")
