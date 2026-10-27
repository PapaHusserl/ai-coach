import sqlite3

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, rows

from ai_coach.profile.service import current_profile, set_value
from ai_coach.store.journal import add_food, add_weight, delete_food, delete_weight

DAY = "2026-10-07"
DELETED = "2026-10-07 12:00:00"
MACROS = {"kcal": 520.0, "protein_g": 31.5, "fat_g": 14.0, "carbs_g": 62.0}


def fill_profile(conn: sqlite3.Connection) -> None:
    for key, value in [
        ("sex", "m"),
        ("birth_date", "1990-01-15"),
        ("height_cm", "180"),
        ("activity_level", "moderate"),
        ("weight_goal", "keep"),
    ]:
        set_value(conn, key, value, "manual", "2026-10-01T10:00:00")


def test_get_weights_hides_deleted(conn: sqlite3.Connection) -> None:
    keep = add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 81.0})
    gone = add_weight(conn, {"measured_at": f"{DAY} 08:00:00", "weight_kg": 99.0})
    delete_weight(conn, gone, DELETED)
    found = rows(conn, "get_weights", start=DAY, end=DAY)
    assert [r["id"] for r in found] == [keep]


def test_get_food_hides_deleted(conn: sqlite3.Connection) -> None:
    keep = add_food(conn, {"logged_at": f"{DAY} 08:00:00", "text": "каша"})
    gone = add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": "суп"})
    delete_food(conn, gone, DELETED)
    found = rows(conn, "get_food", start=DAY, end=DAY)
    assert [r["id"] for r in found] == [keep]


def test_get_food_pending_hides_deleted(conn: sqlite3.Connection) -> None:
    gone = add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": "суп"})
    delete_food(conn, gone, DELETED)
    assert rows(conn, "get_food_pending") == []


def test_get_weights_still_gives_id(conn: sqlite3.Connection) -> None:
    wid = add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 81.0})
    assert rows(conn, "get_weights", start=DAY, end=DAY)[0]["id"] == wid


def test_snapshot_hides_deleted_weight_and_food(conn: sqlite3.Connection) -> None:
    w = add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 99.0})
    f = add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": "торт"})
    delete_weight(conn, w, DELETED)
    delete_food(conn, f, DELETED)
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert snapshot["weights"]["rows"] == []
    assert snapshot["food_today"]["rows"] == []


def test_deleted_food_leaves_nutrition_remaining(conn: sqlite3.Connection) -> None:
    fill_profile(conn)
    add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 80.0})
    eaten = add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": "овсянка", **MACROS})
    pending = add_food(conn, {"logged_at": f"{DAY} 12:00:00", "text": "суп"})
    delete_food(conn, eaten, DELETED)
    profile = call(conn, "get_morning_snapshot", date=DAY)["profile"]
    left = profile["nutrition_remaining"]
    assert left["kcal"] == profile["nutrition"]["kcal_target"]
    assert left["pending_count"] == 1
    delete_food(conn, pending, DELETED)
    left = call(conn, "get_morning_snapshot", date=DAY)["profile"]["nutrition_remaining"]
    assert left["pending_count"] == 0


def test_deleted_food_leaves_get_profile_remaining(conn: sqlite3.Connection) -> None:
    fill_profile(conn)
    add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 80.0})
    eaten = add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": "овсянка", **MACROS})
    delete_food(conn, eaten, DELETED)
    profile = call(conn, "get_profile", date=DAY)
    assert profile["nutrition_remaining"]["kcal"] == profile["nutrition"]["kcal_target"]


def test_deleted_weight_leaves_profile(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-05 07:00:00", "weight_kg": 83.0})
    latest = add_weight(conn, {"measured_at": "2026-10-06 07:00:00", "weight_kg": 70.0})
    assert current_profile(conn, DAY)["weight_kg"] == 70.0
    delete_weight(conn, latest, DELETED)
    assert current_profile(conn, DAY)["weight_kg"] == 83.0


def test_deleting_the_only_weight_leaves_profile_without_weight(conn: sqlite3.Connection) -> None:
    only = add_weight(conn, {"measured_at": "2026-10-06 07:00:00", "weight_kg": 70.0})
    delete_weight(conn, only, DELETED)
    assert current_profile(conn, DAY)["weight_kg"] is None


def test_save_nutrition_to_deleted_entry_is_rejected(conn: sqlite3.Connection) -> None:
    fid = add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": "суп"})
    delete_food(conn, fid, DELETED)
    with pytest.raises(ToolError, match="удалена"):
        call(conn, "save_food_nutrition", food_id=fid, groups=[], **MACROS)
    assert conn.execute("SELECT kcal FROM food_log").fetchone()[0] is None
