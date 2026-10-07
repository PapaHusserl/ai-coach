"""Справочник рецептов: recipe и recipe_ingredient."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert, update


def with_items(conn: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
    sql = "SELECT product, qty, unit FROM recipe_ingredient WHERE recipe_id = ? ORDER BY id"
    return {**row, "items": fetch_all(conn, sql, (row["id"],))}


def name_taken(conn: sqlite3.Connection, name: str, except_id: int | None = None) -> bool:
    """Есть ли живой рецепт с таким именем (без учёта регистра)."""
    rows = fetch_all(conn, "SELECT id, name FROM recipe WHERE deleted_at IS NULL", ())
    return any(r["name"].casefold() == name.casefold() and r["id"] != except_id for r in rows)


def add_recipe(
    conn: sqlite3.Connection, values: dict[str, Any], items: list[dict[str, Any]]
) -> int:
    """values: name, kcal_100, protein_100, fat_100, carbs_100, created_at; не обязательно
    yield_g, updated_at (по умолчанию = created_at). items: product, qty, unit. Имя занято
    живым рецептом - ValueError."""
    if name_taken(conn, values["name"]):
        raise ValueError(f"Рецепт {values['name']!r} уже есть.")
    recipe_id = insert(conn, "recipe", {"updated_at": values["created_at"], **values})
    for item in items:
        insert(conn, "recipe_ingredient", {**item, "recipe_id": recipe_id})
    return recipe_id


def list_recipes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Живые рецепты по имени, каждый с составом items."""
    rows = fetch_all(conn, "SELECT * FROM recipe WHERE deleted_at IS NULL ORDER BY name, id", ())
    return [with_items(conn, row) for row in rows]


def get_recipe(conn: sqlite3.Connection, key: int | str) -> dict[str, Any] | None:
    """Живой рецепт с составом по id или по имени (без учёта регистра); нет или удалён - None."""
    if isinstance(key, int):
        sql = "SELECT * FROM recipe WHERE id = ? AND deleted_at IS NULL"
        row = fetch_one(conn, sql, (key,))
    else:
        found = [r for r in list_recipes(conn) if r["name"].casefold() == key.strip().casefold()]
        return found[0] if found else None
    return with_items(conn, row) if row else None


def edit_recipe(
    conn: sqlite3.Connection,
    recipe_id: int,
    values: dict[str, Any],
    items: list[dict[str, Any]] | None,
    updated_at: str,
) -> bool:
    """Правка полей name, kcal_100, protein_100, fat_100, carbs_100, yield_g (что в values) и
    состава целиком (items не None, заменяет прежний). True - исправлено; False - рецепта нет
    или он удалён. Имя занято другим живым рецептом - ValueError."""
    if get_recipe(conn, recipe_id) is None:
        return False
    if "name" in values and name_taken(conn, values["name"], recipe_id):
        raise ValueError(f"Рецепт {values['name']!r} уже есть.")
    update(conn, "recipe", recipe_id, {**values, "updated_at": updated_at})
    if items is not None:
        conn.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (recipe_id,))
        for item in items:
            insert(conn, "recipe_ingredient", {**item, "recipe_id": recipe_id})
    return True


def delete_recipe(conn: sqlite3.Connection, recipe_id: int, deleted_at: str) -> bool:
    """Пометка удаления. True - удалён; False - рецепта нет или уже удалён."""
    sql = "UPDATE recipe SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL"
    return conn.execute(sql, (deleted_at, recipe_id)).rowcount > 0


def recipe_portion(recipe: dict[str, Any], grams: float) -> list[dict[str, Any]]:
    """Списания из кладовой на grams готового: product, qty, unit = состав * grams / yield_g.
    Нет yield_g или состава - пустой список (списание не предлагается)."""
    if not recipe["yield_g"] or not recipe["items"]:
        return []
    share = grams / recipe["yield_g"]
    return [
        {"product": i["product"], "qty": i["qty"] * share, "unit": i["unit"]}
        for i in recipe["items"]
    ]
