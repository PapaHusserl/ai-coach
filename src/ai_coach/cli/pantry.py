"""Команды `coach pantry`, `coach shop`, `coach meal`: продукты дома, список покупок, рацион."""

from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from ai_coach.pantry import missing, normalize, record, shopping_list, stock
from ai_coach.store.db import db_path, open_db
from ai_coach.store.pantry import mark_meal_plan

pantry_app = typer.Typer(help="Продукты дома", no_args_is_help=True)
meal_app = typer.Typer(help="Рацион на день", no_args_is_help=True)
DONE_MARK = "Оприходовано"


def fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def pantry_write(op: str, item: str, qty: float, unit: str) -> None:
    conn = open_db()
    try:
        with conn:
            warning = record(conn, op, item, qty, unit, now())
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(f"{item}: {op} {qty:g} {unit} записано.")
    if warning:
        typer.echo(warning)


@pantry_app.command("add")
def pantry_add(
    item: Annotated[str, typer.Argument(help="Продукт")],
    qty: Annotated[float, typer.Argument(help="Сколько")],
    unit: Annotated[str, typer.Argument(help="g, ml или pcs")],
) -> None:
    """Купил или принёс: добавить к остатку."""
    pantry_write("add", item, qty, unit)


@pantry_app.command("use")
def pantry_use(
    item: Annotated[str, typer.Argument(help="Продукт")],
    qty: Annotated[float, typer.Argument(help="Сколько")],
    unit: Annotated[str, typer.Argument(help="g, ml или pcs")],
) -> None:
    """Съел или израсходовал: вычесть из остатка."""
    pantry_write("use", item, qty, unit)


@pantry_app.command("set")
def pantry_set(
    item: Annotated[str, typer.Argument(help="Продукт")],
    qty: Annotated[float, typer.Argument(help="Сколько осталось")],
    unit: Annotated[str, typer.Argument(help="g, ml или pcs")],
) -> None:
    """Задать остаток как есть (сверка с реальностью)."""
    pantry_write("set", item, qty, unit)


@pantry_app.command("remove")
def pantry_remove(item: Annotated[str, typer.Argument(help="Продукт")]) -> None:
    """Продукта больше нет (остаток 0)."""
    conn = open_db()
    try:
        entries = [row for row in stock(conn) if row["item"] == normalize(item)]
    finally:
        conn.close()
    if not entries:
        fail(f"Продукта {item!r} нет дома.")
        return
    pantry_write("set", item, 0, entries[0]["unit"])


@pantry_app.command("list")
def pantry_list() -> None:
    """Что есть дома."""
    conn = open_db()
    try:
        rows = stock(conn)
    finally:
        conn.close()
    if not rows:
        typer.echo("Дома ничего нет.")
    for row in rows:
        typer.echo(f"{row['item']}  {row['qty']:g} {row['unit']}  (обновлено {row['updated_at']})")


def parse_item(line: str) -> dict[str, Any]:
    """«продукт qty unit» -> {item, qty, unit}."""
    parts = line.strip().rsplit(None, 2)
    if len(parts) != 3:
        raise ValueError(f"Ожидается «продукт количество единица», получено: {line!r}")
    try:
        qty = float(parts[1].replace(",", "."))
    except ValueError:
        raise ValueError(f"Количество должно быть числом, получено: {parts[1]!r}") from None
    return {"item": parts[0], "qty": qty, "unit": parts[2]}


def shop_done(path: str) -> None:
    """Оприходовать список покупок: каждая строка «- продукт qty unit» — add."""
    file = Path(path)
    if not file.is_file():
        fail(f"Файла {path} нет.")
        return
    rows = file.read_text(encoding="utf-8").splitlines()
    marks = [i for i, x in enumerate(rows) if x.startswith(DONE_MARK)]
    fresh = rows[marks[-1] + 1 :] if marks else rows
    lines = [x[2:] for x in fresh if x.startswith("- ")]
    if marks and not lines:
        fail(f"Список уже оприходован ({rows[marks[-1]]}). Ничего не изменено.")
        return
    conn = open_db()
    try:
        with conn:
            for line in lines:
                found = parse_item(line)
                record(conn, "add", found["item"], found["qty"], found["unit"], now())
    except ValueError as e:
        fail(f"{e} Ничего не оприходовано.")
        return
    finally:
        conn.close()
    with file.open("a", encoding="utf-8") as out:
        out.write(f"\n{DONE_MARK} {now()}\n")
    typer.echo(f"Оприходовано строк: {len(lines)}.")


def shop(
    items: Annotated[
        list[str] | None,
        typer.Argument(help="«продукт количество единица» ...; или done <файл>"),
    ] = None,
    from_file: Annotated[Path | None, typer.Option("--from-file", help="Строки из файла")] = None,
) -> None:
    """Список покупок: чего не хватает дома -> data/shopping/YYYY-MM-DD.md. Наружу ничего не
    уходит, база не меняется. `coach shop done <файл>` - оприходовать купленное."""
    if items and items[0] == "done":
        if len(items) != 2:
            fail("Нужно: coach shop done <файл>")
        shop_done(items[1])
        return
    lines = list(items or [])
    if from_file is not None:
        if not from_file.is_file():
            fail(f"Файла {from_file} нет.")
        lines += from_file.read_text(encoding="utf-8").splitlines()
    lines = [line for line in lines if line.strip()]
    if not lines:
        fail("Список пустой.")
    conn = open_db()
    try:
        need = [parse_item(line) for line in lines]
        text = shopping_list(conn, need)
        nothing = not missing(conn, need)
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(text)
    if nothing:
        return
    today = date.today().isoformat()
    path = db_path().parent / "data" / "shopping" / f"{today}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("a", encoding="utf-8") as out:
            out.write(f"\n{text}\n")
    else:
        path.write_text(f"# Список покупок {today}\n\n{text}\n", encoding="utf-8")
    typer.echo(f"Файл: {path}")


@meal_app.command("done")
def meal_done(
    day: Annotated[
        str | None, typer.Option("--date", help="Дата, YYYY-MM-DD (по умолчанию сегодня)")
    ] = None,
) -> None:
    """Отметить: рацион на день предложен (повторно - без ошибки)."""
    moment = now()
    if day is not None:
        try:
            date.fromisoformat(day)
        except ValueError:
            fail(f"Дата должна быть YYYY-MM-DD, получено: {day!r}")
    day = day or moment[:10]
    conn = open_db()
    try:
        with conn:
            mark_meal_plan(conn, day, moment)
    finally:
        conn.close()
    typer.echo(f"Рацион на {day} отмечен.")
