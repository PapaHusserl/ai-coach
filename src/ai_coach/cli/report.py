"""Команда `coach report`: очередь отчётов тренера о проблемах системы для технического агента."""

import re
from typing import Annotated, Any

import typer

from ai_coach.cli.journal import fail, now
from ai_coach.store.db import open_db
from ai_coach.store.reports import (
    add_report,
    close_report,
    get_report,
    list_reports,
    open_reports,
)

report_app = typer.Typer(help="Отчёты тренера о проблемах системы", no_args_is_help=True)

MAX_LENGTH = 600
_DIGIT = re.compile(r"(?<![A-Za-z_0-9])\d")


def personal_number(text: str) -> bool:
    """Есть цифра, не приклеенная к латинской букве или `_` (значения, даты, координаты)."""
    return _DIGIT.search(text) is not None


def _line(row: dict[str, Any], with_status: bool) -> str:
    line = f"{row['id']}  {row['created_at']}  {row['text']}"
    if not with_status:
        return line
    if row["status"] == "done":
        return f"{line}  [done BACKLOG {row['backlog']}]"
    return f"{line}  [{row['status']}]"


@report_app.command("add")
def report_add(
    text: Annotated[str, typer.Argument(help="Случай без значений и дат")],
) -> None:
    """Записать отчёт о проблеме системы для технического агента (open)."""
    if not text.strip():
        fail("Текст отчёта не должен быть пустым.")
    if personal_number(text):
        fail("В отчёте не должно быть чисел: опиши случай без значений.")
    if len(text) > MAX_LENGTH:
        fail(f"Отчёт длиннее {MAX_LENGTH} символов: сократи до сути.")
    conn = open_db()
    try:
        with conn:
            report_id = add_report(conn, {"text": text, "created_at": now()})
    finally:
        conn.close()
    typer.echo(f"Отчёт {report_id} записан.")


@report_app.command("list")
def report_list(
    all_items: Annotated[bool, typer.Option("--all", help="Вместе с закрытыми.")] = False,
) -> None:
    """Очередь: id, когда записан, текст; без --all - только открытые."""
    conn = open_db()
    try:
        rows = list_reports(conn) if all_items else open_reports(conn)
    finally:
        conn.close()
    if not rows:
        typer.echo("Открытых отчётов нет.")
    for row in rows:
        typer.echo(_line(row, all_items))


@report_app.command("done")
def report_done(
    report_id: Annotated[int, typer.Argument(help="id отчёта")],
    backlog: Annotated[int | None, typer.Option("--backlog", help="Номер пункта BACKLOG")] = None,
    drop: Annotated[bool, typer.Option("--drop", help="Снять отчёт")] = False,
) -> None:
    """Закрыть отчёт: --backlog N - переписан в пункт беклога, --drop - снят."""
    if backlog is not None and drop:
        fail("--backlog и --drop вместе нельзя.")
    if backlog is None and not drop:
        fail("Нужен --backlog <номер пункта> или --drop.")
    conn = open_db()
    try:
        row = get_report(conn, report_id)
        if row is None:
            fail(f"Отчёта {report_id} нет.")
        if row["status"] != "open":
            fail(f"Отчёт {report_id}: уже закрыт ({row['status']}).")
        with conn:
            close_report(conn, report_id, "dropped" if drop else "done", now(), backlog)
    finally:
        conn.close()
    if drop:
        typer.echo(f"Отчёт {report_id}: снят.")
    else:
        typer.echo(f"Отчёт {report_id}: в беклоге, пункт {backlog}.")
