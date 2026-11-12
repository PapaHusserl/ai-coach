"""Команда `coach decide`: очередь решений на будущее (слова, черновики тренировок, фазы)."""

from typing import Annotated, Any

import typer

from ai_coach.cli.journal import check_date, fail, now
from ai_coach.goals.service import accept_phase, reject_phase
from ai_coach.store.db import open_db
from ai_coach.store.decisions import (
    add_decision,
    close_decision,
    get_decision,
    list_decisions,
    open_decisions,
    set_result,
)

decide_app = typer.Typer(help="Решения на будущее: очередь пунктов", no_args_is_help=True)


def _line(row: dict[str, Any], with_status: bool) -> str:
    what = row["text"] if row["kind"] == "text" else f"{row['kind']} {row['ref_id']}: {row['text']}"
    status = f"  [{row['status']}]" if with_status else ""
    day = row["target_date"] or "-"
    return f"{row['id']}  {day}  {what}  (отложено {row['created_at']}){status}"


@decide_app.command("add")
def decide_add(
    text: Annotated[str, typer.Argument(help="Что решить, как есть")],
    target: Annotated[
        str | None, typer.Option("--for", help="День, которого касается решение, YYYY-MM-DD")
    ] = None,
) -> None:
    """Положить решение на будущее в очередь (open)."""
    if not text.strip():
        fail("Текст решения не должен быть пустым.")
    values = {"text": text, "created_at": now(), "target_date": None}
    if target is not None:
        values["target_date"] = check_date(target)
    conn = open_db()
    try:
        with conn:
            decision_id = add_decision(conn, values)
    finally:
        conn.close()
    typer.echo(f"Решение {decision_id} отложено.")


@decide_app.command("list")
def decide_list(
    all_items: Annotated[bool, typer.Option("--all", help="Вместе с решёнными.")] = False,
) -> None:
    """Очередь: id, целевой день, текст, когда отложено; без --all - только открытые."""
    conn = open_db()
    try:
        if all_items:
            rows = list_decisions(conn, "0000-01-01", "9999-12-31")
        else:
            rows = open_decisions(conn)
    finally:
        conn.close()
    if not rows:
        typer.echo("Отложенных решений нет.")
    for row in rows:
        typer.echo(_line(row, all_items))


@decide_app.command("done")
def decide_done(
    decision_id: Annotated[int, typer.Argument(help="id пункта")],
    no: Annotated[bool, typer.Option("--no", help="Решено «нет» (фаза отклоняется)")] = False,
    drop: Annotated[bool, typer.Option("--drop", help="Снять пункт")] = False,
) -> None:
    """Закрыть пункт: без флага - «да» (фаза принимается), --no - «нет», --drop - снять."""
    if no and drop:
        fail("--no и --drop вместе нельзя.")
    status = "no" if no else "dropped" if drop else "yes"
    conn = open_db()
    try:
        row = get_decision(conn, decision_id)
        if row is None:
            fail(f"Пункта {decision_id} нет.")
        if row["status"] != "open":
            fail(f"Пункт {decision_id}: уже решено ({row['status']}).")
        if row["kind"] == "workout":
            ref = row["ref_id"]
            fail(f"Это черновик тренировки: coach approve {ref} или coach cancel {ref}.")
        if row["kind"] == "phase" and drop:
            fail("Фазу можно только принять или отклонить (без флага или --no).")
        try:
            if row["kind"] == "phase":
                (reject_phase if no else accept_phase)(conn, row["ref_id"])
            close_decision(conn, decision_id, status, now())
            conn.commit()
        except (ValueError, LookupError) as e:
            conn.rollback()
            fail(str(e))
    finally:
        conn.close()
    typer.echo(f"Пункт {decision_id}: {status}.")


@decide_app.command("result")
def decide_result(
    decision_id: Annotated[int, typer.Argument(help="id пункта")],
    missed: Annotated[bool, typer.Option("--missed", help="Не исполнено")] = False,
) -> None:
    """Отметить исполнение решения словами («да»): без флага - исполнено, --missed - нет."""
    conn = open_db()
    try:
        row = get_decision(conn, decision_id)
        if row is None:
            fail(f"Пункта {decision_id} нет.")
        if row["kind"] != "text":
            fail("Исполнение отмечается только у решений словами.")
        with conn:
            saved = set_result(conn, decision_id, "missed" if missed else "kept", now())
        if not saved:
            fail(f"Пункт {decision_id}: нужен «да» без отмеченного исполнения.")
    finally:
        conn.close()
    typer.echo(f"Пункт {decision_id}: исполнение отмечено.")
