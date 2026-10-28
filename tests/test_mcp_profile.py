import sqlite3

from mcp_fakes import call, call_text

from ai_coach.goals import create_goal
from ai_coach.mcp_server.snapshot import SNAPSHOT_ROWS
from ai_coach.mcp_server.tools import MAX_CHARS
from ai_coach.profile.service import set_value
from ai_coach.store.goals import add_goal, add_phase
from ai_coach.store.journal import add_food, add_weight
from ai_coach.store.plans import add_planned_workout

DAY = "2026-10-07"
RAW = "SECRET_RAW_PAYLOAD"


def fill(conn: sqlite3.Connection) -> None:
    for key, value in [
        ("sex", "m"),
        ("birth_date", "1990-01-15"),
        ("height_cm", "180"),
        ("activity_level", "moderate"),
        ("weight_goal", "keep"),
    ]:
        set_value(conn, key, value, "manual", "2026-10-01T10:00:00")
    add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 80.0})
    conn.execute(
        "INSERT INTO profile_log (key, value, source, logged_at, raw_json) VALUES (?,?,?,?,?)",
        ("equipment", "гантели", "garmin", "2026-10-02T10:00:00", f'{{"secret": "{RAW}"}}'),
    )


def test_get_profile_has_values_with_source(conn: sqlite3.Connection) -> None:
    fill(conn)
    profile = call(conn, "get_profile", date=DAY)
    assert profile["values"]["sex"]["value"] == "m"
    assert profile["values"]["sex"]["source"] == "manual"
    assert profile["values"]["equipment"]["source"] == "garmin"


def test_get_profile_has_computed_fields(conn: sqlite3.Connection) -> None:
    fill(conn)
    profile = call(conn, "get_profile", date=DAY)
    assert profile["age"] == 36
    assert profile["weight_kg"] == 80.0


def test_get_profile_has_missing(conn: sqlite3.Connection) -> None:
    fill(conn)
    missing = call(conn, "get_profile", date=DAY)["missing"]
    assert "injuries" in missing
    assert "sex" not in missing


def test_get_profile_has_nutrition(conn: sqlite3.Connection) -> None:
    fill(conn)
    nutrition = call(conn, "get_profile", date=DAY)["nutrition"]
    for key in ["bmr", "tdee_rest", "tdee_today", "kcal_target", "protein_g", "fat_g", "carbs_g"]:
        assert key in nutrition
    assert nutrition["bmr"] > 1000


def test_get_profile_without_raw_json(conn: sqlite3.Connection) -> None:
    fill(conn)
    text = call_text(conn, "get_profile", date=DAY)
    assert "raw_json" not in text
    assert RAW not in text


def test_get_profile_on_empty_database(conn: sqlite3.Connection) -> None:
    profile = call(conn, "get_profile", date=DAY)
    assert profile["values"] == {}
    assert "sex" in profile["missing"]


def test_get_profile_for_date_before_changes(conn: sqlite3.Connection) -> None:
    set_value(conn, "height_cm", "180", "manual", "2026-10-01T10:00:00")
    set_value(conn, "height_cm", "181", "manual", "2026-10-05T10:00:00")
    values = call(conn, "get_profile", date="2026-10-03")["values"]
    assert float(values["height_cm"]["value"]) == 180


def test_get_profile_date_is_optional(conn: sqlite3.Connection) -> None:
    fill(conn)
    assert call(conn, "get_profile")["values"]["sex"]["value"] == "m"


def test_snapshot_has_current_profile_values(conn: sqlite3.Connection) -> None:
    fill(conn)
    profile = call(conn, "get_morning_snapshot", date=DAY)["profile"]
    assert profile["values"]["sex"] == "m"
    assert float(profile["values"]["height_cm"]) == 180


def fresh_manual_and_old_garmin_weight(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-24 10:49:04", "weight_kg": 78.7})
    set_value(conn, "weight", "80.599", "garmin", "2026-10-11 09:54:42")


def test_snapshot_weight_is_fresh_manual_not_garmin(conn: sqlite3.Connection) -> None:
    fresh_manual_and_old_garmin_weight(conn)
    profile = call(conn, "get_morning_snapshot", date="2026-10-28")["profile"]
    assert profile["values"]["weight"] == 78.7


def test_get_profile_values_weight_equals_weight_kg(conn: sqlite3.Connection) -> None:
    fresh_manual_and_old_garmin_weight(conn)
    profile = call(conn, "get_profile", date="2026-10-28")
    assert profile["weight_kg"] == 78.7
    assert profile["values"]["weight"]["value"] == profile["weight_kg"]
    assert profile["values"]["weight"]["source"] == "manual"


def test_snapshot_profile_has_missing_nutrition_and_goals(conn: sqlite3.Connection) -> None:
    fill(conn)
    create_goal(conn, "Полумарафон", now="2026-10-01T10:00:00")
    profile = call(conn, "get_morning_snapshot", date=DAY)["profile"]
    assert "injuries" in profile["missing"]
    assert profile["nutrition"]["kcal_target"] > 0
    assert "Полумарафон" in call_text(conn, "get_morning_snapshot", date=DAY)
    assert [g["title"] for g in profile["goals"]] == ["Полумарафон"]


def test_snapshot_profile_has_no_history_or_sources(conn: sqlite3.Connection) -> None:
    set_value(conn, "injuries", "старая травма", "manual", "2026-10-01T10:00:00")
    set_value(conn, "injuries", "новая травма", "manual", "2026-10-02T10:00:00")
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    profile_text = str(call(conn, "get_morning_snapshot", date=DAY)["profile"])
    assert "новая травма" in profile_text
    assert "старая травма" not in text
    assert "logged_at" not in profile_text
    assert "source" not in profile_text


def test_snapshot_profile_skips_empty_keys(conn: sqlite3.Connection) -> None:
    set_value(conn, "sex", "m", "manual", "2026-10-01T10:00:00")
    values = call(conn, "get_morning_snapshot", date=DAY)["profile"]["values"]
    assert list(values) == ["sex"]


def test_snapshot_profile_has_no_raw_json(conn: sqlite3.Connection) -> None:
    fill(conn)
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert RAW not in text


def test_snapshot_profile_is_not_cut_when_snapshot_is_shrunk(conn: sqlite3.Connection) -> None:
    fill(conn)
    big = "x" * 3000
    for number in range(SNAPSHOT_ROWS * 2):
        add_phase(conn, {"name": f"Фаза {number}", "description": big, "status": "proposed"})
        add_planned_workout(
            conn, {"date": DAY, "sport": "run", "name": f"Бег {number} {big}", "workout_json": {}}
        )
        add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": f"еда {number} {big}"})
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert len(text) <= MAX_CHARS
    profile = call(conn, "get_morning_snapshot", date=DAY)["profile"]
    assert profile["values"]["sex"] == "m"
    assert "injuries" in profile["missing"]
    assert profile["nutrition"]["kcal_target"] > 0


def test_snapshot_profile_goals_are_limited_by_priority(conn: sqlite3.Connection) -> None:
    for number in range(12):
        add_goal(conn, {"title": f"Цель {number}", "status": "active", "priority": number})
    profile = call(conn, "get_morning_snapshot", date=DAY)["profile"]
    assert len(profile["goals"]) == 10
    assert profile["goals"][0]["title"] == "Цель 11"
    assert profile["goals_truncated"] is True


def test_snapshot_profile_goals_not_truncated_when_few(conn: sqlite3.Connection) -> None:
    add_goal(conn, {"title": "Одна", "status": "active"})
    assert call(conn, "get_morning_snapshot", date=DAY)["profile"]["goals_truncated"] is False
