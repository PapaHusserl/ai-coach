import sqlite3

from mcp_fakes import call, call_text, rows, tool_names

from ai_coach.store.recipes import add_recipe, delete_recipe

DAY = "2026-10-07"
NOW = "2026-10-07 10:00:00"
SNAPSHOT_RECIPE_ROWS = 30


def new_recipe(conn: sqlite3.Connection, name: str = "плов", items: list | None = None) -> int:
    data = {
        "name": name,
        "kcal_100": 150.0,
        "protein_100": 8.0,
        "fat_100": 5.0,
        "carbs_100": 18.0,
        "yield_g": 1000.0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    default = [{"product": "курица", "qty": 500.0, "unit": "g"}]
    return add_recipe(conn, data, default if items is None else items)


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_recipes" in tool_names(conn)


def test_get_recipes_on_empty_database(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_recipes") == {"rows": [], "truncated": False}


def test_get_recipes_row_has_macros_yield_and_items(conn: sqlite3.Connection) -> None:
    rid = new_recipe(conn)
    row = rows(conn, "get_recipes")[0]
    assert (row["id"], row["name"]) == (rid, "плов")
    assert (row["kcal_100"], row["protein_100"], row["fat_100"], row["carbs_100"]) == (
        150.0,
        8.0,
        5.0,
        18.0,
    )
    assert row["yield_g"] == 1000.0
    assert row["items"] == [{"product": "курица", "qty": 500.0, "unit": "g"}]


def test_get_recipes_has_no_deleted(conn: sqlite3.Connection) -> None:
    new_recipe(conn, "плов")
    gone = new_recipe(conn, "борщ")
    delete_recipe(conn, gone, "2026-10-07 12:00:00")
    assert [r["name"] for r in rows(conn, "get_recipes")] == ["плов"]


def test_get_recipes_is_capped(conn: sqlite3.Connection) -> None:
    for number in range(100):
        new_recipe(conn, f"блюдо {number}")
    result = call(conn, "get_recipes")
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60


def test_get_recipes_has_no_service_fields(conn: sqlite3.Connection) -> None:
    new_recipe(conn)
    text = call_text(conn, "get_recipes")
    assert "deleted_at" not in text
    assert "created_at" not in text


def test_snapshot_has_recipes_with_only_name_and_macros(conn: sqlite3.Connection) -> None:
    new_recipe(conn)
    recipes = call(conn, "get_morning_snapshot", date=DAY)["recipes"]
    assert recipes["rows"] == [
        {"name": "плов", "kcal_100": 150.0, "protein_100": 8.0, "fat_100": 5.0, "carbs_100": 18.0}
    ]


def test_snapshot_recipes_empty_without_data(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_morning_snapshot", date=DAY)["recipes"]["rows"] == []


def test_snapshot_recipes_have_at_most_30_rows(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_RECIPE_ROWS + 20):
        new_recipe(conn, f"блюдо {number}")
    recipes = call(conn, "get_morning_snapshot", date=DAY)["recipes"]
    assert len(recipes["rows"]) <= SNAPSHOT_RECIPE_ROWS
    assert recipes["truncated"] is True


def test_snapshot_recipes_have_no_deleted(conn: sqlite3.Connection) -> None:
    gone = new_recipe(conn, "борщ")
    delete_recipe(conn, gone, "2026-10-07 12:00:00")
    assert call(conn, "get_morning_snapshot", date=DAY)["recipes"]["rows"] == []
