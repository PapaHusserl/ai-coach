"""Команды `coach recipe`: справочник рецептов (КБЖУ на 100 г готового)."""

from typing import Annotated, Any

import typer

from ai_coach.cli.journal import fail, now
from ai_coach.cli.pantry import parse_item
from ai_coach.pantry import normalize
from ai_coach.store.db import open_db
from ai_coach.store.recipes import (
    add_recipe,
    delete_recipe,
    edit_recipe,
    get_recipe,
    list_recipes,
    recipe_portion,
)

recipe_app = typer.Typer(help="Справочник рецептов", no_args_is_help=True)
ITEM_HELP = "«продукт количество g|ml|pcs», можно несколько; при правке - состав целиком"
MAX_KCAL_100 = 900
UNITS = ("g", "ml", "pcs")


def num(text: str | None, name: str) -> float | None:
    """Число (можно с запятой) не меньше 0; None - не задано."""
    if text is None:
        return None
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        fail(f"{name} должно быть числом, получено: {text!r}")
        return None
    if value < 0:
        fail(f"{name} не может быть меньше 0.")
    return value


def read_values(options: dict[str, str | None]) -> dict[str, Any]:
    """Опции (поле рецепта -> текст) -> числа (только заданные), с проверкой."""
    values: dict[str, Any] = {}
    for key, text in options.items():
        found = num(text, "--" + key.removesuffix("_100").removesuffix("_g"))
        if found is not None:
            values[key] = found
    if values.get("kcal_100", 0) > MAX_KCAL_100:
        fail(f"Ккал на 100 г не больше {MAX_KCAL_100}.")
    if values.get("yield_g", 1) == 0:
        fail("--yield должен быть больше 0.")
    return values


def read_name(name: str) -> str:
    """Название: не пустое и не из одних цифр (это был бы id для show)."""
    if not name.strip():
        fail("Название пустое.")
    if name.strip().isdigit():
        fail("Название не может состоять из одних цифр.")
    return name.strip()


def read_items(lines: list[str] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in lines or []:
        try:
            found = parse_item(line)
        except ValueError as e:
            fail(str(e))
            return []
        if found["qty"] <= 0:
            fail(f"Количество должно быть больше 0: {line!r}")
        if found["unit"] not in UNITS:
            fail(f"Единица должна быть из {list(UNITS)}: {line!r}")
        result.append(
            {"product": normalize(found["item"]), "qty": found["qty"], "unit": found["unit"]}
        )
    return result


def find(key: str) -> dict[str, Any]:
    conn = open_db()
    try:
        found = get_recipe(conn, int(key) if key.isdigit() else key)
    finally:
        conn.close()
    if found is None:
        fail(f"Рецепта {key!r} нет.")
    return found or {}


def describe(recipe: dict[str, Any]) -> str:
    size = f", выход {recipe['yield_g']:g} г" if recipe["yield_g"] else ""
    return (
        f"{recipe['id']}  {recipe['name']}  на 100 г: {recipe['kcal_100']:g} ккал, "
        f"Б {recipe['protein_100']:g} / Ж {recipe['fat_100']:g} / У {recipe['carbs_100']:g}{size}"
    )


@recipe_app.command("add")
def recipe_add(
    name: Annotated[str, typer.Argument(help="Название")],
    kcal: Annotated[str, typer.Option("--kcal", help="Ккал на 100 г")],
    protein: Annotated[str, typer.Option("--protein", help="Белки на 100 г")],
    fat: Annotated[str, typer.Option("--fat", help="Жиры на 100 г")],
    carbs: Annotated[str, typer.Option("--carbs", help="Углеводы на 100 г")],
    yield_g: Annotated[str | None, typer.Option("--yield", help="Вес готового, г")] = None,
    item: Annotated[list[str] | None, typer.Option("--item", help=ITEM_HELP)] = None,
) -> None:
    """Сохранить рецепт: КБЖУ на 100 г готового, вес готового и состав."""
    name = read_name(name)
    options = {
        "kcal_100": kcal,
        "protein_100": protein,
        "fat_100": fat,
        "carbs_100": carbs,
        "yield_g": yield_g,
    }
    values = read_values(options)
    items = read_items(item)
    conn = open_db()
    try:
        with conn:
            values |= {"name": name, "created_at": now()}
            recipe_id = add_recipe(conn, values, items)
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    typer.echo(f"Рецепт {recipe_id} сохранён.")


@recipe_app.command("list")
def recipe_list() -> None:
    """Все рецепты."""
    conn = open_db()
    try:
        rows = list_recipes(conn)
    finally:
        conn.close()
    if not rows:
        typer.echo("Рецептов нет.")
    for row in rows:
        typer.echo(describe(row))


@recipe_app.command("show")
def recipe_show(
    key: Annotated[str, typer.Argument(help="id или название")],
    grams: Annotated[
        str | None, typer.Option("--grams", help="Съедено, г: показать списания из кладовой")
    ] = None,
) -> None:
    """Рецепт с составом; с --grams - что списать из кладовой на съеденное."""
    eaten = num(grams, "--grams")
    if eaten == 0:
        fail("--grams должен быть больше 0.")
    recipe = find(key)
    typer.echo(describe(recipe))
    for item in recipe["items"]:
        typer.echo(f"- {item['product']} {item['qty']:g} {item['unit']}")
    if eaten is None:
        return
    portion = recipe_portion(recipe, eaten)
    if not portion:
        typer.echo("Списание не предлагается: нет веса готового или состава.")
    for row in portion:
        typer.echo(f"списать: {row['product']} {row['qty']:.1f} {row['unit']}")


@recipe_app.command("edit")
def recipe_edit(
    recipe_id: Annotated[int, typer.Argument(help="id рецепта (coach recipe list)")],
    name: Annotated[str | None, typer.Option("--name", help="Новое название")] = None,
    kcal: Annotated[str | None, typer.Option("--kcal", help="Ккал на 100 г")] = None,
    protein: Annotated[str | None, typer.Option("--protein", help="Белки на 100 г")] = None,
    fat: Annotated[str | None, typer.Option("--fat", help="Жиры на 100 г")] = None,
    carbs: Annotated[str | None, typer.Option("--carbs", help="Углеводы на 100 г")] = None,
    yield_g: Annotated[str | None, typer.Option("--yield", help="Вес готового, г")] = None,
    item: Annotated[list[str] | None, typer.Option("--item", help=ITEM_HELP)] = None,
) -> None:
    """Поправить название, КБЖУ, вес готового и/или состав целиком (yield не сбрасывается)."""
    options = {
        "kcal_100": kcal,
        "protein_100": protein,
        "fat_100": fat,
        "carbs_100": carbs,
        "yield_g": yield_g,
    }
    fields = read_values(options)
    if name is not None:
        fields["name"] = read_name(name)
    items = read_items(item) if item else None
    if not fields and items is None:
        fail("Нечего менять: нужен --name, --kcal, --protein, --fat, --carbs, --yield или --item.")
    conn = open_db()
    try:
        with conn:
            done = edit_recipe(conn, recipe_id, fields, items, now())
    except ValueError as e:
        fail(str(e))
        return
    finally:
        conn.close()
    if not done:
        fail(f"Рецепта {recipe_id} нет или он удалён.")
    typer.echo(f"Рецепт {recipe_id} исправлен.")


@recipe_app.command("delete")
def recipe_delete(recipe_id: Annotated[int, typer.Argument(help="id рецепта")]) -> None:
    """Удалить рецепт (пометка, строка остаётся в базе)."""
    conn = open_db()
    try:
        with conn:
            done = delete_recipe(conn, recipe_id, now())
    finally:
        conn.close()
    if not done:
        fail(f"Рецепта {recipe_id} нет или он уже удалён.")
    typer.echo(f"Рецепт {recipe_id} удалён.")
