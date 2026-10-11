"""Команда `coach event`: события тренера в календаре (список, запись, снятие, отмена черновика)."""

import sqlite3
from datetime import date, timedelta
from typing import Annotated, Any

import typer

from ai_coach.agenda import AgendaError, agenda_rows, cancel_event, remove_event, write_event
from ai_coach.agenda.calendar_write import CalendarWriter
from ai_coach.agenda.service import AHEAD_DAYS, PAST_DAYS
from ai_coach.cli.journal import check_date, fail
from ai_coach.store.db import open_db
from ai_coach.workload import CalendarError, WorkloadConfigError, load_config

event_app = typer.Typer(help="События тренера в календаре", no_args_is_help=True)
IDS_HELP = "id событий"


def describe_event(row: dict[str, Any]) -> str:
    repeat = f"  повтор: {row['repeat']}" if row["repeat"] else ""
    return (
        f"{row['id']}  {row['status']}  {row['start_at']} - {row['end_at'][11:16]}  "
        f"{row['kind']}  {row['title']}{repeat}"
    )


def coach_calendar() -> str:
    """Название календаря коуча из конфига; нет - ошибка (до обращения к календарю)."""
    try:
        name = load_config().coach_calendar
    except WorkloadConfigError as e:
        fail(str(e))
        return ""
    if name is None:
        fail("Календарь коуча не задан: добавь [coach] calendar в workload.toml.")
        return ""
    return name


def each(ids: list[int], action: Any) -> None:
    """Применяет action(conn, id) к каждому id; коммит после каждого. Ошибка одного - в stderr,
    остальные продолжаются, в конце код 1."""
    conn = open_db()
    failed = False
    try:
        for event_id in ids:
            try:
                action(conn, event_id)
                conn.commit()
            except (AgendaError, CalendarError) as e:
                conn.rollback()
                typer.echo(f"Событие {event_id}: {e}", err=True)
                failed = True
    finally:
        conn.close()
    if failed:
        raise typer.Exit(1)


@event_app.command("list")
def event_list(
    date_from: Annotated[str | None, typer.Option("--from", help="С даты YYYY-MM-DD")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="По дату YYYY-MM-DD")] = None,
) -> None:
    """Черновики и записанные события (по умолчанию от 30 дней назад до 14 вперёд)."""
    today = date.today()
    first = check_date(date_from) if date_from else (today - timedelta(days=PAST_DAYS)).isoformat()
    last = check_date(date_to) if date_to else (today + timedelta(days=AHEAD_DAYS)).isoformat()
    conn = open_db()
    try:
        rows = agenda_rows(conn, first, last)
    finally:
        conn.close()
    if not rows:
        typer.echo("Событий нет.")
    for row in rows:
        typer.echo(describe_event(row))


@event_app.command("write")
def event_write(ids: Annotated[list[int], typer.Argument(help=IDS_HELP)]) -> None:
    """Записать черновики в календарь коуча (draft -> written)."""
    writer = CalendarWriter(coach_calendar())

    def action(conn: sqlite3.Connection, event_id: int) -> None:
        write_event(conn, event_id, writer)
        typer.echo(f"Событие {event_id} записано в календарь.")

    each(ids, action)


@event_app.command("remove")
def event_remove(ids: Annotated[list[int], typer.Argument(help=IDS_HELP)]) -> None:
    """Снять записанные события из календаря коуча (written -> removed)."""
    writer = CalendarWriter(coach_calendar())

    def action(conn: sqlite3.Connection, event_id: int) -> None:
        remove_event(conn, event_id, writer)
        typer.echo(f"Событие {event_id} снято из календаря.")

    each(ids, action)


@event_app.command("cancel")
def event_cancel(ids: Annotated[list[int], typer.Argument(help=IDS_HELP)]) -> None:
    """Отменить черновики (draft -> cancelled); в календарь не ходит."""

    def action(conn: sqlite3.Connection, event_id: int) -> None:
        cancel_event(conn, event_id)
        typer.echo(f"Черновик {event_id} отменён.")

    each(ids, action)
