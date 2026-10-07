"""Команды `coach`: sync, import, approve, push, status, weight, food, feel, profile, goal."""

from datetime import date, datetime
from getpass import getpass
from pathlib import Path
from typing import Annotated, Any

import typer

from ai_coach.garmin import (
    TOKEN_NAME,
    GarminAuthError,
    GarminError,
    full_login,
    load_client,
    token_dir,
)
from ai_coach.goals import create_goal, list_goals, update_goal
from ai_coach.plan import (
    PlanError,
    approve,
    garmin_json,
    has_old,
    pushable,
    remove_old,
    send,
)
from ai_coach.profile import current_profile, set_value
from ai_coach.store.db import open_db
from ai_coach.store.journal import add_food, add_weight, add_wellbeing
from ai_coach.store.plans import list_planned_workouts
from ai_coach.sync import FitImportError, import_export, import_fit, summary
from ai_coach.sync import sync as run_sync
from ai_coach.workouts import describe_workout

app = typer.Typer(help="Личный ИИ-тренер на данных Garmin", no_args_is_help=True)
profile_app = typer.Typer(help="Профиль спортсмена", no_args_is_help=True)
goal_app = typer.Typer(help="Цели", no_args_is_help=True)
app.add_typer(profile_app, name="profile")
app.add_typer(goal_app, name="goal")

ZIP_WITH_ID = "--id не нужен для zip-экспорта: id активностей берутся из архива."
MIN_WEIGHT_KG = 20
MAX_WEIGHT_KG = 300
MIN_SCORE = 1
MAX_SCORE = 5


def fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


@app.command()
def login() -> None:
    """Полный логин Garmin (пароль через getpass). Запускать в обычном терминале."""
    try:
        if (token_dir() / TOKEN_NAME).exists():
            try:
                load_client()
            except GarminAuthError:
                typer.echo("Токены протухли, нужен полный логин.")
            else:
                typer.echo("Токены найдены и работают, пароль не нужен.")
                return
        email = getpass("Garmin email (ввод скрыт): ")
        password = getpass("Garmin пароль (ввод скрыт): ")
        full_login(email, password, lambda: getpass("Код MFA: "))
    except GarminError as e:
        fail(str(e))
    typer.echo(f"Логин прошёл, токены: {token_dir() / TOKEN_NAME}")


@app.command()
def sync(days: Annotated[int, typer.Option(help="За сколько последних дней")] = 7) -> None:
    """Загрузить метрики, активности и подходы силовой из Garmin в базу."""
    try:
        client = load_client()
    except GarminError as e:
        fail(str(e))
        return
    conn = open_db()
    try:
        typer.echo(run_sync(conn, client, days, pause=0.5))
    except GarminError as e:
        fail(str(e))
    finally:
        conn.close()


@app.command("import")
def import_(
    path: Annotated[Path, typer.Argument(help="FIT активности или zip-экспорт Garmin")],
    activity_id: Annotated[
        int | None, typer.Option("--id", help="id активности, если его нет в имени файла")
    ] = None,
) -> None:
    """Импортировать FIT активности или zip-экспорт Garmin (без сети)."""
    is_zip = path.suffix.lower() == ".zip"
    if is_zip and activity_id is not None:
        fail(ZIP_WITH_ID)
    if not path.is_file():
        fail(f"Файл не найден: {path}")
    conn = open_db()
    try:
        if is_zip:
            typer.echo(summary(import_export(conn, path)))
        else:
            typer.echo(import_fit(conn, path, activity_id))
    except FitImportError as e:
        fail(str(e))
    finally:
        conn.close()


@app.command("approve")
def approve_(workout_id: Annotated[int, typer.Argument(help="id тренировки")]) -> None:
    """Утвердить черновик тренировки (draft -> approved)."""
    conn = open_db()
    try:
        approve(conn, workout_id)
        conn.commit()
        typer.echo(f"Тренировка {workout_id} утверждена.")
    except PlanError as e:
        fail(str(e))
    finally:
        conn.close()


@app.command()
def push(workout_id: Annotated[int, typer.Argument(help="id тренировки")]) -> None:
    """Отправить утверждённую тренировку в Garmin и запланировать на дату (спросит y/N).
    Повторный push заменяет только свою прежнюю копию — после отдельного y/N."""
    conn = open_db()
    try:
        row = pushable(conn, workout_id)
        typer.echo(f"Дата: {row['date']}")
        typer.echo(describe_workout(garmin_json(row)))
        if not typer.confirm("Отправить в Garmin?", default=False):
            typer.echo("Ничего не отправлено.")
            return
        client = load_client()
        if has_old(row):
            typer.echo(
                "В Garmin уже есть эта тренировка, после отправки новой её снимут с календаря "
                "и удалят: "
                f"workoutId={row['garmin_workout_id']}, scheduleId={row['garmin_schedule_id']}"
            )
            if not typer.confirm("Отправить новую и удалить старую?", default=False):
                typer.echo("Ничего не отправлено и не удалено.")
                return
        send(conn, client, row)
        conn.commit()
        if has_old(row):
            remove_old(client, row["garmin_workout_id"], row["garmin_schedule_id"])
        typer.echo("Отправлено. Синхронизируй часы.")
    except (PlanError, GarminError) as e:
        fail(str(e))
    finally:
        conn.close()


@app.command()
def status() -> None:
    """Что запланировано и отправлено."""
    conn = open_db()
    try:
        rows = list_planned_workouts(conn, "0000-01-01", "9999-12-31")
    finally:
        conn.close()
    if not rows:
        typer.echo("Тренировок нет.")
    for row in rows:
        sent = f", отправлена {row['pushed_at']}" if row["pushed_at"] else ""
        typer.echo(
            f"{row['id']}  {row['date']}  {row['sport']}  {row['name']}  [{row['status']}{sent}]"
        )


@app.command()
def weight(text: Annotated[str, typer.Argument(help="Вес, кг (можно 81,7)")]) -> None:
    """Записать вес (время — сейчас, местное)."""
    try:
        kg = float(text.replace(",", "."))
    except ValueError:
        fail(f"Вес должен быть числом, получено: {text!r}")
        return
    if not MIN_WEIGHT_KG <= kg <= MAX_WEIGHT_KG:
        fail(f"Вес должен быть от {MIN_WEIGHT_KG} до {MAX_WEIGHT_KG} кг.")
    conn = open_db()
    try:
        with conn:
            add_weight(conn, {"measured_at": now(), "weight_kg": kg})
    finally:
        conn.close()
    typer.echo(f"Вес {kg} кг записан.")


@app.command()
def food(text: Annotated[str, typer.Argument(help="Что съедено, как есть")]) -> None:
    """Записать еду текстом (время — сейчас). КБЖУ посчитает /coach-food."""
    if not text.strip():
        fail("Текст пустой.")
    conn = open_db()
    try:
        with conn:
            add_food(conn, {"logged_at": now(), "text": text.strip()})
    finally:
        conn.close()
    typer.echo("Еда записана. КБЖУ посчитает /coach-food.")


@app.command()
def feel(
    score: Annotated[int, typer.Argument(help="Самочувствие от 1 до 5")],
    text: Annotated[str | None, typer.Argument(help="Пояснение, как есть")] = None,
) -> None:
    """Записать самочувствие (время — сейчас). Записи только добавляются."""
    if not MIN_SCORE <= score <= MAX_SCORE:
        fail(f"Оценка должна быть от {MIN_SCORE} до {MAX_SCORE}.")
    moment = now()
    values = {"date": moment[:10], "logged_at": moment, "score": score, "text": text}
    conn = open_db()
    try:
        with conn:
            add_wellbeing(conn, values)
    finally:
        conn.close()
    typer.echo(f"Самочувствие {score} записано.")


@profile_app.command("show")
def profile_show() -> None:
    """Текущий профиль: значения с источниками и что ещё не заполнено."""
    conn = open_db()
    try:
        profile = current_profile(conn, date.today().isoformat())
    finally:
        conn.close()
    for key, entry in profile["values"].items():
        typer.echo(f"{key}: {entry['value']} ({entry['source']})")
    if profile["missing"]:
        typer.echo(f"Не заполнено: {', '.join(profile['missing'])}")


@profile_app.command("set")
def profile_set(
    key: Annotated[str, typer.Argument(help="Ключ профиля")],
    value: Annotated[str, typer.Argument(help="Значение")],
) -> None:
    """Записать значение профиля (ручное главнее Garmin). Записи только добавляются."""
    conn = open_db()
    try:
        with conn:
            set_value(conn, key, value, "manual", now())
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(f"{key} записан.")


@goal_app.command("add")
def goal_add(
    title: Annotated[str, typer.Argument(help="Название цели")],
    kind: Annotated[str | None, typer.Option(help="Вид цели")] = None,
    target: Annotated[str | None, typer.Option(help="Чего достичь")] = None,
    target_date: Annotated[str | None, typer.Option("--date", help="Срок, YYYY-MM-DD")] = None,
    priority: Annotated[int, typer.Option(help="Приоритет")] = 0,
) -> None:
    """Добавить цель."""
    if target_date is not None:
        try:
            date.fromisoformat(target_date)
        except ValueError:
            fail(f"Дата должна быть YYYY-MM-DD, получено: {target_date!r}")
            return
    fields: dict[str, Any] = {
        "kind": kind,
        "target": target,
        "target_date": target_date,
        "priority": priority,
    }
    conn = open_db()
    try:
        with conn:
            goal_id = create_goal(conn, title.strip(), **fields)
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(f"Цель {goal_id} добавлена.")


@goal_app.command("list")
def goal_list() -> None:
    """Все цели."""
    conn = open_db()
    try:
        goals = list_goals(conn)
    finally:
        conn.close()
    if not goals:
        typer.echo("Целей нет.")
    for goal in goals:
        due = f", до {goal['target_date']}" if goal["target_date"] else ""
        typer.echo(f"{goal['id']}  {goal['title']}  [{goal['status']}{due}]")


def close_goal(goal_id: int, status: str) -> None:
    conn = open_db()
    try:
        with conn:
            update_goal(conn, goal_id, {"status": status})
    except LookupError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(f"Цель {goal_id}: {status}.")


@goal_app.command("done")
def goal_done(goal_id: Annotated[int, typer.Argument(help="id цели")]) -> None:
    """Цель достигнута."""
    close_goal(goal_id, "done")


@goal_app.command("cancel")
def goal_cancel(goal_id: Annotated[int, typer.Argument(help="id цели")]) -> None:
    """Цель отменена."""
    close_goal(goal_id, "cancelled")
