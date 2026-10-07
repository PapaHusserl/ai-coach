"""Команды `coach weight|food|edit|delete|log`: записи веса и еды, правка, удаление, просмотр."""

from datetime import date, datetime
from typing import Annotated

import typer

from ai_coach.store.db import open_db
from ai_coach.store.journal import (
    add_food,
    add_weight,
    delete_food,
    delete_weight,
    edit_food,
    edit_weight,
    list_food,
    list_weights,
)

edit_app = typer.Typer(help="Правка записей веса и еды", no_args_is_help=True)
delete_app = typer.Typer(help="Удаление записей веса и еды", no_args_is_help=True)
log_app = typer.Typer(help="Записи веса и еды за день (id для правки)", no_args_is_help=True)
MIN_WEIGHT_KG = 20
MAX_WEIGHT_KG = 300


def fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def check_date(value: str) -> str:
    """Дата строго YYYY-MM-DD, иначе ошибка."""
    try:
        ok = date.fromisoformat(value).isoformat() == value
    except ValueError:
        ok = False
    if not ok:
        fail(f"Дата должна быть YYYY-MM-DD, получено: {value!r}")
    return value


def parse_at(text: str | None) -> str | None:
    """--at: YYYY-MM-DD или "YYYY-MM-DD HH:MM"; None - не задан. Только дата -> 12:00,
    для сегодня до полудня - текущее время. Будущее - ошибка."""
    if text is None:
        return None
    value = text.strip()
    try:
        if len(value) == len("YYYY-MM-DD"):
            day = date.fromisoformat(check_date(value))
            moment = min(datetime(day.year, day.month, day.day, 12), datetime.now())
            in_future = day > date.today()
        else:
            moment = datetime.strptime(value, "%Y-%m-%d %H:%M")
            check_date(value[:10])
            in_future = moment > datetime.now()
    except ValueError:
        fail(f'--at должен быть YYYY-MM-DD или "YYYY-MM-DD HH:MM", получено: {text!r}')
        return None
    if in_future:
        fail("--at в будущем.")
    return moment.isoformat(sep=" ", timespec="seconds")


def parse_kg(text: str) -> float:
    try:
        kg = float(text.replace(",", "."))
    except ValueError:
        fail(f"Вес должен быть числом, получено: {text!r}")
        return 0
    if not MIN_WEIGHT_KG <= kg <= MAX_WEIGHT_KG:
        fail(f"Вес должен быть от {MIN_WEIGHT_KG} до {MAX_WEIGHT_KG} кг.")
    return kg


def weight(
    text: Annotated[str, typer.Argument(help="Вес, кг (можно 81,7)")],
    at: Annotated[
        str | None, typer.Option("--at", help='Когда: YYYY-MM-DD или "YYYY-MM-DD HH:MM"')
    ] = None,
) -> None:
    """Записать вес (время — сейчас, местное, или --at)."""
    kg = parse_kg(text)
    measured_at = parse_at(at) or now()
    conn = open_db()
    try:
        with conn:
            add_weight(conn, {"measured_at": measured_at, "weight_kg": kg})
    finally:
        conn.close()
    typer.echo(f"Вес {kg} кг записан.")


def food(
    text: Annotated[str, typer.Argument(help="Что съедено, как есть")],
    at: Annotated[
        str | None, typer.Option("--at", help='Когда: YYYY-MM-DD или "YYYY-MM-DD HH:MM"')
    ] = None,
) -> None:
    """Записать еду текстом (время — сейчас или --at). КБЖУ посчитает /coach-food."""
    if not text.strip():
        fail("Текст пустой.")
    logged_at = parse_at(at) or now()
    conn = open_db()
    try:
        with conn:
            add_food(conn, {"logged_at": logged_at, "text": text.strip()})
    finally:
        conn.close()
    typer.echo("Еда записана. КБЖУ посчитает /coach-food.")


@edit_app.command("weight")
def edit_weight_(
    weight_id: Annotated[int, typer.Argument(help="id записи (coach log weight)")],
    text: Annotated[str | None, typer.Argument(help="Новый вес, кг")] = None,
    at: Annotated[
        str | None, typer.Option("--at", help='Новое время: YYYY-MM-DD или "YYYY-MM-DD HH:MM"')
    ] = None,
) -> None:
    """Поправить вес и/или время записи."""
    if text is None and at is None:
        fail("Нужен новый вес или --at.")
    kg = parse_kg(text) if text is not None else None
    measured_at = parse_at(at)
    conn = open_db()
    try:
        with conn:
            done = edit_weight(conn, weight_id, kg, measured_at)
    finally:
        conn.close()
    if not done:
        fail(f"Записи веса {weight_id} нет или она удалена.")
    typer.echo(f"Запись веса {weight_id} исправлена.")


@edit_app.command("food")
def edit_food_(
    food_id: Annotated[int, typer.Argument(help="id записи (coach log food)")],
    text: Annotated[str | None, typer.Argument(help="Новый текст (КБЖУ сбросится)")] = None,
    at: Annotated[
        str | None, typer.Option("--at", help='Новое время: YYYY-MM-DD или "YYYY-MM-DD HH:MM"')
    ] = None,
) -> None:
    """Поправить текст и/или время еды. Новый текст сбрасывает КБЖУ (посчитает /coach-food)."""
    if text is None and at is None:
        fail("Нужен новый текст или --at.")
    if text is not None and not text.strip():
        fail("Текст пустой.")
    logged_at = parse_at(at)
    conn = open_db()
    try:
        with conn:
            done = edit_food(conn, food_id, text.strip() if text is not None else None, logged_at)
    finally:
        conn.close()
    if not done:
        fail(f"Записи еды {food_id} нет или она удалена.")
    typer.echo(f"Запись еды {food_id} исправлена.")


@delete_app.command("weight")
def delete_weight_(weight_id: Annotated[int, typer.Argument(help="id записи")]) -> None:
    """Удалить запись веса (пометка, строка остаётся в базе)."""
    conn = open_db()
    try:
        with conn:
            done = delete_weight(conn, weight_id, now())
    finally:
        conn.close()
    if not done:
        fail(f"Записи веса {weight_id} нет или она уже удалена.")
    typer.echo(f"Запись веса {weight_id} удалена.")


@delete_app.command("food")
def delete_food_(food_id: Annotated[int, typer.Argument(help="id записи")]) -> None:
    """Удалить запись еды (пометка, строка остаётся в базе)."""
    conn = open_db()
    try:
        with conn:
            done = delete_food(conn, food_id, now())
    finally:
        conn.close()
    if not done:
        fail(f"Записи еды {food_id} нет или она уже удалена.")
    typer.echo(f"Запись еды {food_id} удалена.")


def log_day(day: str | None) -> str:
    if day is None:
        return date.today().isoformat()
    return check_date(day)


@log_app.command("weight")
def log_weight(
    day: Annotated[
        str | None, typer.Option("--date", help="День, YYYY-MM-DD (по умолчанию сегодня)")
    ] = None,
) -> None:
    """Записи веса за день: id, время, кг."""
    day = log_day(day)
    conn = open_db()
    try:
        rows = list_weights(conn, day, day)
    finally:
        conn.close()
    if not rows:
        typer.echo("Записей нет.")
    for row in rows:
        typer.echo(f"{row['id']}  {row['measured_at']}  {row['weight_kg']} кг")


@log_app.command("food")
def log_food(
    day: Annotated[
        str | None, typer.Option("--date", help="День, YYYY-MM-DD (по умолчанию сегодня)")
    ] = None,
) -> None:
    """Записи еды за день: id, время, текст, КБЖУ (если посчитано)."""
    day = log_day(day)
    conn = open_db()
    try:
        rows = list_food(conn, day, day)
    finally:
        conn.close()
    if not rows:
        typer.echo("Записей нет.")
    for row in rows:
        if row["kcal"] is None:
            nutrition = "КБЖУ не посчитано"
        else:
            nutrition = (
                f"{row['kcal']:g} ккал, Б {row['protein_g']:g} / Ж {row['fat_g']:g} "
                f"/ У {row['carbs_g']:g}"
            )
        typer.echo(f"{row['id']}  {row['logged_at']}  {row['text']}  [{nutrition}]")
