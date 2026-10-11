"""Команды `coach`: sync (Garmin и нагрузка), import, approve, push, link, status, weight, food,
feel, profile, goal, pantry, shop, meal, recipe, practice, habit, protocol, supplement,
med, event, log, edit, delete."""

from datetime import date, datetime
from getpass import getpass
from pathlib import Path
from typing import Annotated, Any

import typer

from ai_coach.cli.agenda import event_app
from ai_coach.cli.habits import habit_app
from ai_coach.cli.journal import check_date, delete_app, edit_app, food, log_app, weight
from ai_coach.cli.meds import med_app
from ai_coach.cli.pantry import meal_app, pantry_app, shop
from ai_coach.cli.practices import practice_app
from ai_coach.cli.recipes import recipe_app
from ai_coach.cli.review import review_app
from ai_coach.cli.sport_nutrition import protocol_app, supplement_app
from ai_coach.cli.supplement_log import supplement_log, supplement_take, supplement_untake
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
from ai_coach.store.journal import add_wellbeing, wellbeing_day
from ai_coach.store.plans import get_planned_workout, list_planned_workouts
from ai_coach.store.workload import upsert_counter
from ai_coach.sync import FitImportError, import_export, import_fit, summary
from ai_coach.sync import sync as run_sync
from ai_coach.sync import sync_workload as run_workload
from ai_coach.workouts import describe_workout, workout_link_url

app = typer.Typer(help="Личный ИИ-тренер на данных Garmin", no_args_is_help=True)
profile_app = typer.Typer(help="Профиль спортсмена", no_args_is_help=True)
goal_app = typer.Typer(help="Цели", no_args_is_help=True)
app.add_typer(profile_app, name="profile")
app.add_typer(goal_app, name="goal")
app.add_typer(edit_app, name="edit")
app.add_typer(delete_app, name="delete")
app.add_typer(log_app, name="log")
app.command()(weight)
app.command()(food)
app.add_typer(pantry_app, name="pantry")
app.add_typer(meal_app, name="meal")
app.add_typer(recipe_app, name="recipe")
app.add_typer(practice_app, name="practice")
app.add_typer(habit_app, name="habit")
app.add_typer(review_app, name="review")
app.add_typer(event_app, name="event")
app.add_typer(protocol_app, name="protocol")
app.add_typer(supplement_app, name="supplement")
supplement_app.command("take")(supplement_take)
supplement_app.command("log")(supplement_log)
supplement_app.command("untake")(supplement_untake)
app.add_typer(med_app, name="med")
app.command()(shop)

ZIP_WITH_ID = "--id не нужен для zip-экспорта: id активностей берутся из архива."
MIN_SCORE = 1
MAX_SCORE = 5
MAX_HOURS = 24


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
    """Загрузить метрики, активности и подходы силовой из Garmin и нагрузку (календарь, туду,
    груминг) в базу. Ошибка Garmin нагрузку не прерывает, код выхода остаётся 1."""
    conn = open_db()
    failed = False
    try:
        try:
            client = load_client()
            typer.echo(run_sync(conn, client, days, pause=0.5))
        except GarminError as e:
            typer.echo(str(e), err=True)
            failed = True
        typer.echo(run_workload(conn, days))
    finally:
        conn.close()
    if failed:
        raise typer.Exit(1)


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
def link(
    workout_id: Annotated[int, typer.Argument(help="id тренировки")],
    time: Annotated[str | None, typer.Option("--time", help="Время, HH:MM")] = None,
) -> None:
    """Ссылка на страницу-плеер с тренировкой (для телефона без часов)."""
    conn = open_db()
    try:
        row = get_planned_workout(conn, workout_id)
        typer.echo(workout_link_url(row, workout_id, time)["url"])
    except ValueError as e:
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


def parse_hours(kind: str, text: str) -> float:
    """Часы дня из текста (запятая как точка), от 0 до MAX_HOURS; иначе ошибка и выход."""
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        value = -1
    if not 0 <= value <= MAX_HOURS:
        fail(f"Часы ({kind}) должны быть числом от 0 до {MAX_HOURS}.")
    return value


@app.command()
def feel(
    score: Annotated[int, typer.Argument(help="Самочувствие от 1 до 5")],
    text: Annotated[str | None, typer.Argument(help="Пояснение, как есть")] = None,
    mood: Annotated[int | None, typer.Option(help="Настроение от 1 до 5")] = None,
    stress: Annotated[int | None, typer.Option(help="Стресс от 1 до 5")] = None,
    work: Annotated[str | None, typer.Option(help="Часы работы за день")] = None,
    hobby: Annotated[str | None, typer.Option(help="Часы хобби за день")] = None,
    rest: Annotated[str | None, typer.Option(help="Часы отдыха за день")] = None,
) -> None:
    """Записать самочувствие (время — сейчас), вечером ещё настроение, стресс и часы за день.
    Записи самочувствия только добавляются; часы за день перезаписываются.
    До 04:00 запись и часы идут на вчера."""
    for name, value in (("Оценка", score), ("Настроение", mood), ("Стресс", stress)):
        if value is not None and not MIN_SCORE <= value <= MAX_SCORE:
            fail(f"{name}: от {MIN_SCORE} до {MAX_SCORE}.")
    hours = {"work_hours": work, "hobby_hours": hobby, "rest_hours": rest}
    given = {kind: parse_hours(kind, value) for kind, value in hours.items() if value is not None}
    moment = now()
    day = wellbeing_day(datetime.fromisoformat(moment))
    values = {
        "date": day,
        "logged_at": moment,
        "score": score,
        "text": text,
        "mood": mood,
        "stress": stress,
    }
    conn = open_db()
    try:
        with conn:
            add_wellbeing(conn, values)
            for kind, value in given.items():
                counter = {"date": day, "kind": kind, "value": value}
                upsert_counter(conn, {**counter, "source": "manual", "synced_at": moment})
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
        check_date(target_date)
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
