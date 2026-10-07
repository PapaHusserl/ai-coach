import sqlite3

import pytest

from ai_coach.goals import create_goal
from ai_coach.profile.service import current_profile, set_value
from ai_coach.store.goals import add_goal
from ai_coach.store.journal import add_weight

DAY = "2026-10-07"
REQUIRED = {
    "sex",
    "birth_date",
    "height_cm",
    "weight",
    "activity_level",
    "schedule",
    "equipment",
    "injuries",
    "weight_goal",
    "goals",
}


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT count(*) FROM profile_log").fetchone()[0]


def put(
    conn: sqlite3.Connection, key: str, value: str, source: str = "manual", at: str = ""
) -> None:
    set_value(conn, key, value, source, at or "2026-10-01T10:00:00")


def height(conn: sqlite3.Connection, day: str) -> float:
    return float(current_profile(conn, day)["values"]["height_cm"]["value"])


def test_set_value_writes_one_row(conn: sqlite3.Connection) -> None:
    put(conn, "sex", "m")
    row = conn.execute("SELECT key, value, source, logged_at FROM profile_log").fetchall()
    assert [tuple(r) for r in row] == [("sex", "m", "manual", "2026-10-01T10:00:00")]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("sex", "x"),
        ("height_cm", "abc"),
        ("birth_date", "вчера"),
        ("activity_level", "extreme"),
        ("weight_goal", "explode"),
        ("max_hr", "быстро"),
        ("nonsense", "1"),
        ("resting_hr", "50"),
    ],
)
def test_bad_value_or_key_is_rejected_and_writes_nothing(
    conn: sqlite3.Connection, key: str, value: str
) -> None:
    with pytest.raises(ValueError):
        put(conn, key, value)
    assert count(conn) == 0


def test_bad_source_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        put(conn, "sex", "m", source="web")
    assert count(conn) == 0


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("sex", "f"),
        ("birth_date", "1990-01-15"),
        ("height_cm", "180"),
        ("activity_level", "moderate"),
        ("max_hr", "190"),
        ("injuries", "нет"),
        ("schedule", "пн, ср, пт по утрам"),
        ("weight_goal", "lose"),
        ("target_weight_kg", "75"),
        ("kcal_target", "2400"),
    ],
)
def test_good_values_are_accepted(conn: sqlite3.Connection, key: str, value: str) -> None:
    put(conn, key, value)
    assert count(conn) == 1


def test_new_value_adds_a_row_and_becomes_current(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "180", at="2026-10-01T10:00:00")
    put(conn, "height_cm", "181", at="2026-10-05T10:00:00")
    assert count(conn) == 2
    assert height(conn, DAY) == 181


def test_state_on_a_date_between_changes(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "180", at="2026-10-01T10:00:00")
    put(conn, "height_cm", "181", at="2026-10-05T10:00:00")
    assert height(conn, "2026-10-03") == 180


def test_state_on_the_day_of_change_includes_that_day(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "180", at="2026-10-01T10:00:00")
    put(conn, "height_cm", "181", at="2026-10-05T10:00:00")
    assert height(conn, "2026-10-05") == 181


def test_state_before_first_record_has_no_value(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "180", at="2026-10-01T10:00:00")
    assert "height_cm" not in current_profile(conn, "2026-09-30")["values"]


def test_current_value_has_source_and_logged_at(conn: sqlite3.Connection) -> None:
    put(conn, "sex", "m")
    item = current_profile(conn, DAY)["values"]["sex"]
    assert item["value"] == "m"
    assert item["source"] == "manual"
    assert item["logged_at"] == "2026-10-01T10:00:00"


def test_manual_beats_garmin(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "178", "garmin", "2026-10-01T10:00:00")
    put(conn, "height_cm", "180", "manual", "2026-10-02T10:00:00")
    item = current_profile(conn, DAY)["values"]["height_cm"]
    assert (float(item["value"]), item["source"]) == (180, "manual")


def test_manual_beats_later_garmin(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "180", "manual", "2026-10-01T10:00:00")
    put(conn, "height_cm", "178", "garmin", "2026-10-02T10:00:00")
    item = current_profile(conn, DAY)["values"]["height_cm"]
    assert (float(item["value"]), item["source"]) == (180, "manual")


def test_only_garmin_is_used(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "178", "garmin")
    item = current_profile(conn, DAY)["values"]["height_cm"]
    assert (float(item["value"]), item["source"]) == (178, "garmin")


def test_same_garmin_value_is_not_written_twice(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "178", "garmin", "2026-10-01T10:00:00")
    put(conn, "height_cm", "178", "garmin", "2026-10-02T10:00:00")
    assert count(conn) == 1


def test_changed_garmin_value_is_written(conn: sqlite3.Connection) -> None:
    put(conn, "height_cm", "178", "garmin", "2026-10-01T10:00:00")
    put(conn, "height_cm", "179", "garmin", "2026-10-02T10:00:00")
    assert count(conn) == 2


def test_age_is_computed_from_birth_date(conn: sqlite3.Connection) -> None:
    put(conn, "birth_date", "1990-01-15")
    assert current_profile(conn, DAY)["age"] == 36


def test_age_before_birthday_is_one_less(conn: sqlite3.Connection) -> None:
    put(conn, "birth_date", "1990-12-31")
    assert current_profile(conn, DAY)["age"] == 35


def test_age_is_none_without_birth_date(conn: sqlite3.Connection) -> None:
    assert current_profile(conn, DAY)["age"] is None


def test_weight_log_beats_garmin_weight(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-06 07:00:00", "weight_kg": 82.0})
    put(conn, "weight", "81.7", "garmin")
    assert current_profile(conn, DAY)["weight_kg"] == 82.0


def test_latest_weight_log_is_used(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-05 07:00:00", "weight_kg": 83.0})
    add_weight(conn, {"measured_at": "2026-10-06 07:00:00", "weight_kg": 82.0})
    assert current_profile(conn, DAY)["weight_kg"] == 82.0


def test_garmin_weight_is_fallback(conn: sqlite3.Connection) -> None:
    put(conn, "weight", "81.7", "garmin")
    assert current_profile(conn, DAY)["weight_kg"] == 81.7


def test_weight_is_none_without_data(conn: sqlite3.Connection) -> None:
    assert current_profile(conn, DAY)["weight_kg"] is None


def test_missing_on_empty_database_has_all_required_and_no_goals_mark(
    conn: sqlite3.Connection,
) -> None:
    profile = current_profile(conn, DAY)
    assert set(profile["missing"]) == REQUIRED


def test_missing_shrinks_as_values_are_added(conn: sqlite3.Connection) -> None:
    put(conn, "sex", "m")
    missing = current_profile(conn, DAY)["missing"]
    assert "sex" not in missing
    assert "birth_date" in missing


def test_weight_in_log_removes_weight_from_missing(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-06 07:00:00", "weight_kg": 82.0})
    assert "weight" not in current_profile(conn, DAY)["missing"]


def test_active_goal_removes_no_goals_mark(conn: sqlite3.Connection) -> None:
    create_goal(conn, "Полумарафон", now="2026-10-01T10:00:00")
    assert "goals" not in current_profile(conn, DAY)["missing"]


def test_cancelled_goal_does_not_count(conn: sqlite3.Connection) -> None:
    add_goal(conn, {"title": "x", "status": "cancelled"})
    assert "goals" in current_profile(conn, DAY)["missing"]


def test_no_answer_to_injuries_is_a_value(conn: sqlite3.Connection) -> None:
    put(conn, "injuries", "нет")
    assert "injuries" not in current_profile(conn, DAY)["missing"]


def test_missing_is_empty_when_everything_is_filled(conn: sqlite3.Connection) -> None:
    for key, value in [
        ("sex", "m"),
        ("birth_date", "1990-01-15"),
        ("height_cm", "180"),
        ("activity_level", "moderate"),
        ("schedule", "пн ср пт"),
        ("equipment", "гантели"),
        ("injuries", "нет"),
        ("weight_goal", "keep"),
    ]:
        put(conn, key, value)
    add_weight(conn, {"measured_at": "2026-10-06 07:00:00", "weight_kg": 82.0})
    create_goal(conn, "Полумарафон", now="2026-10-01T10:00:00")
    profile = current_profile(conn, DAY)
    assert profile["missing"] == []
