import sqlite3

from mcp_fakes import call, call_text, rows

from ai_coach.mcp_server.tools import MAX_CHARS
from ai_coach.pantry.service import record
from ai_coach.profile.service import set_value
from ai_coach.store.goals import add_goal
from ai_coach.store.journal import add_food, add_weight

DAY = "2026-10-07"
SNAPSHOT_PANTRY_ROWS = 30


def fill_profile(conn: sqlite3.Connection) -> None:
    for key, value in [
        ("sex", "m"),
        ("birth_date", "1990-01-15"),
        ("height_cm", "180"),
        ("activity_level", "moderate"),
        ("weight_goal", "keep"),
    ]:
        set_value(conn, key, value, "manual", "2026-10-01T10:00:00")
    add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 80.0})


def test_get_pantry_on_empty_database(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_pantry") == {"rows": [], "truncated": False}


def test_get_pantry_row_has_item_qty_unit_and_updated_at(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", "2026-10-05T10:00:00")
    record(conn, "use", "курица", 200, "g", "2026-10-06T10:00:00")
    row = rows(conn, "get_pantry")[0]
    assert (row["item"], row["qty"], row["unit"]) == ("курица", 300, "g")
    assert row["updated_at"] == "2026-10-06T10:00:00"


def test_get_pantry_shows_only_positive_qty(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", "2026-10-05T10:00:00")
    record(conn, "add", "рис", 100, "g", "2026-10-05T10:00:00")
    record(conn, "use", "рис", 100, "g", "2026-10-06T10:00:00")
    assert [r["item"] for r in rows(conn, "get_pantry")] == ["курица"]


def test_get_pantry_is_capped(conn: sqlite3.Connection) -> None:
    for number in range(100):
        record(conn, "add", f"продукт {number}", 1, "g", "2026-10-05T10:00:00")
    result = call(conn, "get_pantry")
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60


def test_get_pantry_has_no_log_internals(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", "2026-10-05T10:00:00")
    text = call_text(conn, "get_pantry")
    assert "logged_at" not in text
    assert '"op"' not in text


def test_snapshot_has_pantry_with_only_item_qty_unit(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", "2026-10-05T10:00:00")
    pantry = call(conn, "get_morning_snapshot", date=DAY)["pantry"]
    assert pantry["rows"] == [{"item": "курица", "qty": 500, "unit": "g"}]


def test_snapshot_pantry_is_empty_without_data(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_morning_snapshot", date=DAY)["pantry"]["rows"] == []


def test_snapshot_pantry_has_at_most_30_rows(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_PANTRY_ROWS + 20):
        record(conn, "add", f"продукт {number}", 1, "g", "2026-10-05T10:00:00")
    pantry = call(conn, "get_morning_snapshot", date=DAY)["pantry"]
    assert len(pantry["rows"]) <= SNAPSHOT_PANTRY_ROWS
    assert pantry["truncated"] is True


def test_snapshot_has_nutrition_remaining_in_profile(conn: sqlite3.Connection) -> None:
    fill_profile(conn)
    add_food(
        conn,
        {
            "logged_at": f"{DAY} 09:00:00",
            "text": "овсянка",
            "kcal": 500,
            "protein_g": 20,
            "fat_g": 10,
            "carbs_g": 80,
        },
    )
    add_food(conn, {"logged_at": f"{DAY} 12:00:00", "text": "суп"})
    profile = call(conn, "get_morning_snapshot", date=DAY)["profile"]
    left = profile["nutrition_remaining"]
    assert left["kcal"] == profile["nutrition"]["kcal_target"] - 500
    assert left["protein_g"] == profile["nutrition"]["protein_g"] - 20
    assert left["pending_count"] == 1


def test_get_profile_has_nutrition_remaining(conn: sqlite3.Connection) -> None:
    fill_profile(conn)
    profile = call(conn, "get_profile", date=DAY)
    assert profile["nutrition_remaining"]["kcal"] == profile["nutrition"]["kcal_target"]


def test_nutrition_remaining_counts_only_that_day(conn: sqlite3.Connection) -> None:
    fill_profile(conn)
    add_food(
        conn,
        {
            "logged_at": "2026-10-06 20:00:00",
            "text": "ужин",
            "kcal": 900,
            "protein_g": 50,
            "fat_g": 30,
            "carbs_g": 90,
        },
    )
    profile = call(conn, "get_profile", date=DAY)
    assert profile["nutrition_remaining"]["kcal"] == profile["nutrition"]["kcal_target"]


def test_nutrition_remaining_is_empty_without_nutrition(conn: sqlite3.Connection) -> None:
    profile = call(conn, "get_morning_snapshot", date=DAY)["profile"]
    assert not profile.get("nutrition_remaining")


def test_snapshot_keeps_profile_and_pantry_when_squeezed(conn: sqlite3.Connection) -> None:
    fill_profile(conn)
    big = "я" * 300
    for number in range(100):
        add_goal(conn, {"title": f"Цель {number} {big}", "status": "active"})
        record(conn, "add", f"продукт {number}", 1, "g", "2026-10-05T10:00:00")
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert len(call_text(conn, "get_morning_snapshot", date=DAY)) <= MAX_CHARS
    assert snapshot["profile"]["values"]["sex"] == "m"
    assert snapshot["profile"]["nutrition_remaining"]["kcal"] > 0
    assert snapshot["pantry"]["rows"]
