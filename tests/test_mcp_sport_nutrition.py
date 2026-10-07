import sqlite3

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, rows, tool_names

from ai_coach.store.plans import add_planned_workout
from ai_coach.store.sport_nutrition import (
    add_protocol,
    add_supplement,
    delete_protocol,
    delete_supplement,
)

DAY = "2026-10-07"
NOW = "2026-10-07 10:00:00"
SNAPSHOT_NUTRITION_ROWS = 10


def new_protocol(conn: sqlite3.Connection, name: str = "гель", phase: str = "before", **f) -> int:
    base = {
        "name": name,
        "phase": phase,
        "sport": None,
        "min_duration_min": 0,
        "offset_min": 30,
        "carbs_g": 30.0,
        "protein_g": 0.0,
        "fluid_ml": 200.0,
        "sodium_mg": 0.0,
        "note": "SECRET_NOTE",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return add_protocol(conn, {**base, **f})


def new_supplement(conn: sqlite3.Connection, name: str = "креатин", schedule: str = "daily") -> int:
    return add_supplement(
        conn,
        {
            "name": name,
            "dose": 5.0,
            "unit": "g",
            "schedule": schedule,
            "time_note": None,
            "note": None,
            "created_at": NOW,
            "updated_at": NOW,
        },
    )


def new_workout(
    conn: sqlite3.Connection, minutes: int | None = 90, sport: str = "run", status: str = "approved"
) -> int:
    spec: dict = {"name": "т"}
    if minutes is not None:
        spec["estimated_duration_secs"] = minutes * 60
    row = {"date": DAY, "sport": sport, "name": "т", "workout_json": spec, "status": status}
    return add_planned_workout(conn, row)


# --- get_sport_nutrition ---


def test_tools_exist(conn: sqlite3.Connection) -> None:
    names = tool_names(conn)
    assert "get_sport_nutrition" in names
    assert "get_sport_nutrition_for" in names


@pytest.mark.parametrize("kind", ["protocol", "supplement"])
def test_get_on_empty_database(conn: sqlite3.Connection, kind: str) -> None:
    assert call(conn, "get_sport_nutrition", kind=kind) == {"rows": [], "truncated": False}


def test_get_protocols_returns_rows_without_deleted(conn: sqlite3.Connection) -> None:
    new_protocol(conn, "гель")
    gone = new_protocol(conn, "напиток")
    delete_protocol(conn, gone, "2026-10-07 12:00:00")
    assert [r["name"] for r in rows(conn, "get_sport_nutrition", kind="protocol")] == ["гель"]


def test_get_protocols_row_has_fields(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    row = rows(conn, "get_sport_nutrition", kind="protocol")[0]
    assert (row["id"], row["phase"], row["carbs_g"], row["fluid_ml"]) == (
        pid,
        "before",
        30.0,
        200.0,
    )


def test_get_supplements_returns_rows_without_deleted(conn: sqlite3.Connection) -> None:
    new_supplement(conn, "креатин")
    gone = new_supplement(conn, "магний")
    delete_supplement(conn, gone, "2026-10-07 12:00:00")
    found = rows(conn, "get_sport_nutrition", kind="supplement")
    assert [(r["name"], r["dose"], r["unit"], r["schedule"]) for r in found] == [
        ("креатин", 5.0, "g", "daily")
    ]


def test_get_has_no_service_fields(conn: sqlite3.Connection) -> None:
    new_protocol(conn)
    text = call_text(conn, "get_sport_nutrition", kind="protocol")
    assert "deleted_at" not in text
    assert "created_at" not in text


@pytest.mark.parametrize("kind", ["protocol", "supplement"])
def test_get_is_capped(conn: sqlite3.Connection, kind: str) -> None:
    for number in range(100):
        if kind == "protocol":
            new_protocol(conn, f"протокол {number}")
        else:
            new_supplement(conn, f"добавка {number}")
    result = call(conn, "get_sport_nutrition", kind=kind)
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60


def test_get_bad_kind_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(Exception):  # noqa: B017 - схема MCP или ToolError
        call(conn, "get_sport_nutrition", kind="vitamin")


# --- get_sport_nutrition_for ---


def day(conn: sqlite3.Connection) -> dict:
    return call(conn, "get_sport_nutrition_for", date=DAY)


def test_for_bad_date_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        call(conn, "get_sport_nutrition_for", date="07.10.2026")


def test_for_day_without_workout_has_only_daily_supplements(conn: sqlite3.Connection) -> None:
    new_protocol(conn, "до", "before")
    new_supplement(conn, "креатин", "daily")
    new_supplement(conn, "кофеин", "before")
    new_supplement(conn, "магний", "training_day")
    result = day(conn)
    assert result["workouts"] == []
    assert [s["name"] for s in result["supplements"]] == ["креатин"]


def test_for_training_day_has_all_supplements(conn: sqlite3.Connection) -> None:
    new_workout(conn)
    new_supplement(conn, "креатин", "daily")
    new_supplement(conn, "магний", "training_day")
    assert sorted(s["name"] for s in day(conn)["supplements"]) == ["креатин", "магний"]


def test_for_workout_has_phases_and_duration_flags(conn: sqlite3.Connection) -> None:
    wid = new_workout(conn, 120)
    new_protocol(conn, "до", "before")
    new_protocol(conn, "во время", "during")
    new_protocol(conn, "после", "after")
    item = day(conn)["workouts"][0]
    assert (item["id"], item["sport"]) == (wid, "run")
    assert [p["name"] for p in item["before"]] == ["до"]
    assert [p["name"] for p in item["during"]] == ["во время"]
    assert [p["name"] for p in item["after"]] == ["после"]
    assert (item["water_only"], item["duration_unknown"]) == (False, False)


def test_for_short_workout_is_water_only(conn: sqlite3.Connection) -> None:
    new_workout(conn, 74)
    new_protocol(conn, "во время", "during")
    item = day(conn)["workouts"][0]
    assert item["water_only"] is True
    assert item["during"] == []


def test_for_unknown_duration_is_flagged(conn: sqlite3.Connection) -> None:
    new_workout(conn, None)
    assert day(conn)["workouts"][0]["duration_unknown"] is True


def test_for_specific_sport_wins(conn: sqlite3.Connection) -> None:
    new_workout(conn, 60, "run")
    new_protocol(conn, "общий до", "before")
    new_protocol(conn, "бег до", "before", sport="run")
    assert [p["name"] for p in day(conn)["workouts"][0]["before"]] == ["бег до"]


def test_for_cancelled_workout_is_skipped(conn: sqlite3.Connection) -> None:
    new_workout(conn, 90, status="cancelled")
    new_protocol(conn, "до", "before")
    new_supplement(conn, "магний", "training_day")
    result = day(conn)
    assert result["workouts"] == []
    assert result["supplements"] == []


def test_for_two_workouts_gives_two_items(conn: sqlite3.Connection) -> None:
    first = new_workout(conn, 90, "run")
    second = new_workout(conn, 40, "strength")
    new_protocol(conn, "во время", "during")
    items = day(conn)["workouts"]
    assert [i["id"] for i in items] == [first, second]
    assert items[0]["water_only"] is False
    assert items[1]["water_only"] is True


def test_for_other_date_workout_is_not_included(conn: sqlite3.Connection) -> None:
    add_planned_workout(
        conn,
        {"date": "2026-10-08", "sport": "run", "name": "т", "workout_json": {}, "status": "draft"},
    )
    assert day(conn)["workouts"] == []


# --- snapshot ---


def snapshot(conn: sqlite3.Connection) -> dict:
    return call(conn, "get_morning_snapshot", date=DAY)


def test_snapshot_without_data_has_no_sport_nutrition(conn: sqlite3.Connection) -> None:
    assert "sport_nutrition_today" not in snapshot(conn)


def test_snapshot_without_workout_and_supplements_has_no_sport_nutrition(
    conn: sqlite3.Connection,
) -> None:
    new_protocol(conn, "до", "before")
    assert "sport_nutrition_today" not in snapshot(conn)


def test_snapshot_is_compact_without_notes(conn: sqlite3.Connection) -> None:
    new_workout(conn, 90)
    new_protocol(conn, "до", "before")
    part = snapshot(conn)["sport_nutrition_today"]
    text = str(part)
    assert "до" in text
    assert "before" in text
    assert "SECRET_NOTE" not in text
    assert "note" not in text


def test_snapshot_supplements_are_one_string(conn: sqlite3.Connection) -> None:
    new_workout(conn, 90)
    new_supplement(conn, "креатин")
    new_supplement(conn, "магний", "training_day")
    line = snapshot(conn)["sport_nutrition_today"]["supplements"]
    assert isinstance(line, str)
    assert "креатин" in line
    assert "магний" in line


def test_snapshot_has_at_most_10_rows(conn: sqlite3.Connection) -> None:
    new_workout(conn, 90)
    for number in range(SNAPSHOT_NUTRITION_ROWS + 10):
        new_protocol(conn, f"протокол {number}", "before")
    part = snapshot(conn)["sport_nutrition_today"]
    assert len(part["rows"]) <= SNAPSHOT_NUTRITION_ROWS
    assert part["truncated"] is True


def test_snapshot_skips_cancelled_workout(conn: sqlite3.Connection) -> None:
    new_workout(conn, 90, status="cancelled")
    new_protocol(conn, "до", "before")
    assert "sport_nutrition_today" not in snapshot(conn)


def test_snapshot_workout_flags_have_name(conn: sqlite3.Connection) -> None:
    new_workout(conn, 90)
    new_protocol(conn, "до", "before")
    assert snapshot(conn)["sport_nutrition_today"]["workouts"][0]["name"] == "т"
