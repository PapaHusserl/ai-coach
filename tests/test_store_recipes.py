import sqlite3

import pytest

from ai_coach.store.recipes import (
    add_recipe,
    delete_recipe,
    edit_recipe,
    get_recipe,
    list_recipes,
    recipe_portion,
)

NOW = "2026-10-07 10:00:00"
LATER = "2026-10-07 18:00:00"
CHICKEN = {"product": "курица", "qty": 500.0, "unit": "g"}
RICE = {"product": "рис", "qty": 200.0, "unit": "g"}
EGGS = {"product": "яйца", "qty": 4.0, "unit": "pcs"}


def must(conn: sqlite3.Connection, key: int | str) -> dict:
    recipe = get_recipe(conn, key)
    assert recipe is not None
    return recipe


def values(name: str = "плов", **fields: object) -> dict:
    base = {
        "name": name,
        "kcal_100": 150.0,
        "protein_100": 8.0,
        "fat_100": 5.0,
        "carbs_100": 18.0,
        "yield_g": 1000.0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return {**base, **fields}


def edit(conn: sqlite3.Connection, rid: int, items: list | None = None, **fields: object) -> bool:
    return edit_recipe(conn, rid, fields, items, LATER)


def new_recipe(conn: sqlite3.Connection, name: str = "плов", items: list | None = None) -> int:
    return add_recipe(conn, values(name), [CHICKEN, RICE] if items is None else items)


# --- add / get ---


def test_add_returns_id_and_get_by_id_returns_fields(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    recipe = must(conn, rid)
    assert recipe is not None
    assert recipe["id"] == rid
    assert (recipe["name"], recipe["kcal_100"], recipe["protein_100"]) == ("плов", 150.0, 8.0)
    assert (recipe["fat_100"], recipe["carbs_100"], recipe["yield_g"]) == (5.0, 18.0, 1000.0)


def test_get_returns_items_in_order(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    items = must(conn, rid)["items"]
    assert [(i["product"], i["qty"], i["unit"]) for i in items] == [
        ("курица", 500.0, "g"),
        ("рис", 200.0, "g"),
    ]


def test_get_by_name(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    assert must(conn, "плов")["id"] == rid


def test_get_by_name_ignores_case_for_cyrillic(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn, "Плов")
    assert must(conn, "плов")["id"] == rid
    assert must(conn, "ПЛОВ")["id"] == rid


def test_get_unknown_returns_none(conn: sqlite3.Connection) -> None:
    assert get_recipe(conn, 99) is None
    assert get_recipe(conn, "нет такого") is None


def test_add_without_yield_and_items(conn: sqlite3.Connection) -> None:
    data = values("йогурт")
    del data["yield_g"]
    rid = add_recipe(conn, data, [])
    recipe = must(conn, rid)
    assert recipe["yield_g"] is None
    assert recipe["items"] == []


def test_add_sets_created_and_updated_at(conn: sqlite3.Connection) -> None:
    recipe = must(conn, new_recipe(conn))
    assert recipe["created_at"] == NOW
    assert recipe["updated_at"] == NOW
    assert recipe["deleted_at"] is None


def test_item_with_pcs_unit(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn, "омлет", [EGGS])
    item = must(conn, rid)["items"][0]
    assert (item["product"], item["qty"], item["unit"]) == ("яйца", 4.0, "pcs")


# --- unique name ---


def test_duplicate_name_is_refused(conn: sqlite3.Connection) -> None:
    new_recipe(conn)
    with pytest.raises(ValueError):
        new_recipe(conn)


def test_duplicate_name_ignores_case(conn: sqlite3.Connection) -> None:
    new_recipe(conn, "Плов")
    with pytest.raises(ValueError):
        new_recipe(conn, "плов")


def test_duplicate_does_not_add_second_recipe(conn: sqlite3.Connection) -> None:
    new_recipe(conn)
    with pytest.raises(ValueError):
        new_recipe(conn)
    assert len(list_recipes(conn)) == 1


def test_name_can_be_reused_after_delete(conn: sqlite3.Connection) -> None:
    first = new_recipe(conn)
    delete_recipe(conn, first, LATER)
    second = new_recipe(conn)
    assert second != first
    assert must(conn, "плов")["id"] == second


# --- list ---


def test_list_on_empty_database(conn: sqlite3.Connection) -> None:
    assert list_recipes(conn) == []


def test_list_returns_all_alive(conn: sqlite3.Connection) -> None:
    new_recipe(conn, "плов")
    new_recipe(conn, "борщ")
    assert sorted(r["name"] for r in list_recipes(conn)) == ["борщ", "плов"]


def test_list_has_no_deleted(conn: sqlite3.Connection) -> None:
    keep = new_recipe(conn, "плов")
    gone = new_recipe(conn, "борщ")
    delete_recipe(conn, gone, LATER)
    assert [r["id"] for r in list_recipes(conn)] == [keep]


# --- edit ---


def test_edit_changes_macros_and_returns_true(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    assert edit(conn, rid, kcal_100=170.0, carbs_100=20.0) is True
    recipe = must(conn, rid)
    assert (recipe["kcal_100"], recipe["carbs_100"]) == (170.0, 20.0)
    assert (recipe["protein_100"], recipe["fat_100"]) == (8.0, 5.0)


def test_edit_changes_yield(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    edit(conn, rid, yield_g=800.0)
    assert must(conn, rid)["yield_g"] == 800.0


def test_edit_renames(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    edit(conn, rid, name="плов с курицей")
    assert must(conn, "плов с курицей")["id"] == rid
    assert get_recipe(conn, "плов") is None


def test_edit_replaces_items_wholly(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    edit(conn, rid, items=[EGGS])
    items = must(conn, rid)["items"]
    assert [(i["product"], i["qty"], i["unit"]) for i in items] == [("яйца", 4.0, "pcs")]


def test_edit_without_items_keeps_items(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    edit(conn, rid, kcal_100=170.0)
    assert len(must(conn, rid)["items"]) == 2


def test_edit_sets_updated_at_only(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    edit(conn, rid, kcal_100=170.0)
    recipe = must(conn, rid)
    assert recipe["updated_at"] == LATER
    assert recipe["created_at"] == NOW


def test_edit_does_not_touch_other_recipes(conn: sqlite3.Connection) -> None:
    first = new_recipe(conn, "плов")
    second = new_recipe(conn, "борщ")
    edit(conn, second, kcal_100=60.0)
    assert must(conn, first)["kcal_100"] == 150.0
    assert len(must(conn, first)["items"]) == 2


def test_edit_unknown_returns_false(conn: sqlite3.Connection) -> None:
    assert edit(conn, 99, kcal_100=1.0) is False


def test_edit_deleted_returns_false_and_keeps_data(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    delete_recipe(conn, rid, LATER)
    assert edit(conn, rid, kcal_100=1.0) is False
    assert get_recipe(conn, rid) is None


def test_edit_to_existing_name_is_refused(conn: sqlite3.Connection) -> None:
    new_recipe(conn, "плов")
    other = new_recipe(conn, "борщ")
    with pytest.raises(ValueError):
        edit(conn, other, name="Плов")
    assert must(conn, other)["name"] == "борщ"


def test_edit_keeping_own_name_is_allowed(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn, "плов")
    assert edit(conn, rid, name="Плов") is True


# --- delete ---


def test_delete_returns_true_and_hides_recipe(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    assert delete_recipe(conn, rid, LATER) is True
    assert get_recipe(conn, rid) is None
    assert get_recipe(conn, "плов") is None
    assert list_recipes(conn) == []


def test_delete_marks_row_instead_of_removing(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    delete_recipe(conn, rid, LATER)
    row = conn.execute("SELECT deleted_at FROM recipe WHERE id = ?", (rid,)).fetchone()
    assert row[0] == LATER


def test_delete_twice_returns_false(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    delete_recipe(conn, rid, LATER)
    assert delete_recipe(conn, rid, "2026-10-08 10:00:00") is False
    row = conn.execute("SELECT deleted_at FROM recipe WHERE id = ?", (rid,)).fetchone()
    assert row[0] == LATER


def test_delete_unknown_returns_false(conn: sqlite3.Connection) -> None:
    assert delete_recipe(conn, 99, LATER) is False


def test_delete_does_not_touch_other_recipes(conn: sqlite3.Connection) -> None:
    keep = new_recipe(conn, "плов")
    gone = new_recipe(conn, "борщ")
    delete_recipe(conn, gone, LATER)
    assert get_recipe(conn, keep) is not None


# --- recipe_portion ---


def portion(conn: sqlite3.Connection, rid: int, grams: float) -> list[dict]:
    return recipe_portion(must(conn, rid), grams)


def test_portion_is_proportional_to_grams_and_yield(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    result = portion(conn, rid, 250)
    assert [(p["product"], p["unit"]) for p in result] == [("курица", "g"), ("рис", "g")]
    assert result[0]["qty"] == pytest.approx(125.0)
    assert result[1]["qty"] == pytest.approx(50.0)


def test_portion_of_whole_yield_is_whole_recipe(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    assert [p["qty"] for p in portion(conn, rid, 1000)] == pytest.approx([500.0, 200.0])


def test_portion_keeps_pcs_unit_and_fraction(conn: sqlite3.Connection) -> None:
    rid = add_recipe(conn, values("омлет", yield_g=400.0), [EGGS])
    result = portion(conn, rid, 100)
    assert result[0]["unit"] == "pcs"
    assert result[0]["qty"] == pytest.approx(1.0)


def test_portion_without_yield_is_empty(conn: sqlite3.Connection) -> None:
    data = values("плов")
    del data["yield_g"]
    rid = add_recipe(conn, data, [CHICKEN, RICE])
    assert portion(conn, rid, 250) == []


def test_portion_without_items_is_empty(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn, items=[])
    assert portion(conn, rid, 250) == []


def test_portion_does_not_change_recipe(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    portion(conn, rid, 250)
    assert [i["qty"] for i in must(conn, rid)["items"]] == [500.0, 200.0]
