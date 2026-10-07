import sqlite3
from typing import Any

import pytest

from ai_coach.sport_nutrition import protocols_for, workout_duration_min
from ai_coach.store.plans import add_planned_workout, get_planned_workout
from ai_coach.store.sport_nutrition import add_protocol, add_supplement

NOW = "2026-10-07 10:00:00"
DAY = "2026-10-07"


def workout(
    conn: sqlite3.Connection, minutes: int | None, sport: str = "run", status: str = "approved"
) -> dict[str, Any]:
    spec: dict[str, Any] = {"name": "тренировка"}
    if minutes is not None:
        spec["estimated_duration_secs"] = minutes * 60
    wid = add_planned_workout(
        conn,
        {"date": DAY, "sport": sport, "name": "т", "workout_json": spec, "status": status},
    )
    found = get_planned_workout(conn, wid)
    assert found is not None
    return found


def protocol(conn: sqlite3.Connection, name: str, phase: str, **fields: object) -> int:
    base = {
        "name": name,
        "phase": phase,
        "sport": None,
        "min_duration_min": 0,
        "offset_min": 30,
        "carbs_g": 30.0,
        "protein_g": 0.0,
        "fluid_ml": 0.0,
        "sodium_mg": 0.0,
        "note": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return add_protocol(conn, {**base, **fields})


def supplement(conn: sqlite3.Connection, name: str, schedule: str = "daily") -> int:
    values = {
        "name": name,
        "dose": 5.0,
        "unit": "g",
        "schedule": schedule,
        "time_note": None,
        "note": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return add_supplement(conn, values)


def names(rows: list[dict[str, Any]]) -> list[str]:
    return [r["name"] for r in rows]


# --- workout_duration_min ---


def test_duration_is_taken_from_estimated_secs(conn: sqlite3.Connection) -> None:
    assert workout_duration_min(workout(conn, 90)) == 90


@pytest.mark.parametrize("minutes", [0, None])
def test_duration_unknown_is_zero_or_none(conn: sqlite3.Connection, minutes: int | None) -> None:
    assert not workout_duration_min(workout(conn, minutes))


# --- 74 / 75 / 120 ---


def test_74_minutes_is_water_only(conn: sqlite3.Connection) -> None:
    protocol(conn, "углеводы в час", "during")
    result = protocols_for(conn, workout(conn, 74))
    assert result["water_only"] is True
    assert result["during"] == []
    assert result["duration_unknown"] is False


def test_75_minutes_gets_during_protocol(conn: sqlite3.Connection) -> None:
    protocol(conn, "углеводы в час", "during")
    result = protocols_for(conn, workout(conn, 75))
    assert result["water_only"] is False
    assert names(result["during"]) == ["углеводы в час"]


def test_120_minutes_gets_during_protocol(conn: sqlite3.Connection) -> None:
    protocol(conn, "углеводы в час", "during")
    result = protocols_for(conn, workout(conn, 120))
    assert result["water_only"] is False
    assert names(result["during"]) == ["углеводы в час"]


def test_short_workout_still_gets_before_and_after(conn: sqlite3.Connection) -> None:
    protocol(conn, "до", "before")
    protocol(conn, "после", "after")
    result = protocols_for(conn, workout(conn, 30))
    assert names(result["before"]) == ["до"]
    assert names(result["after"]) == ["после"]


@pytest.mark.parametrize("minutes", [0, None])
def test_unknown_duration_is_flagged_and_not_water_only(
    conn: sqlite3.Connection, minutes: int | None
) -> None:
    result = protocols_for(conn, workout(conn, minutes))
    assert result["duration_unknown"] is True
    assert result["water_only"] is False


def test_known_duration_is_not_flagged_unknown(conn: sqlite3.Connection) -> None:
    assert protocols_for(conn, workout(conn, 60))["duration_unknown"] is False


def test_no_protocols_gives_empty_phases(conn: sqlite3.Connection) -> None:
    result = protocols_for(conn, workout(conn, 90))
    assert (result["before"], result["during"], result["after"]) == ([], [], [])
    assert result["supplements"] == []


# --- sport: specific beats general ---


def test_specific_sport_wins_over_general(conn: sqlite3.Connection) -> None:
    protocol(conn, "общий до", "before")
    protocol(conn, "бег до", "before", sport="run")
    assert names(protocols_for(conn, workout(conn, 60, "run"))["before"]) == ["бег до"]


def test_general_is_used_when_no_specific_for_sport(conn: sqlite3.Connection) -> None:
    protocol(conn, "общий до", "before")
    protocol(conn, "бег до", "before", sport="run")
    assert names(protocols_for(conn, workout(conn, 60, "bike"))["before"]) == ["общий до"]


def test_other_sport_protocol_is_not_used(conn: sqlite3.Connection) -> None:
    protocol(conn, "плавание после", "after", sport="swim")
    assert protocols_for(conn, workout(conn, 60, "run"))["after"] == []


def test_specific_wins_only_within_its_phase(conn: sqlite3.Connection) -> None:
    protocol(conn, "общий после", "after")
    protocol(conn, "бег до", "before", sport="run")
    result = protocols_for(conn, workout(conn, 60, "run"))
    assert names(result["before"]) == ["бег до"]
    assert names(result["after"]) == ["общий после"]


def test_deleted_protocol_is_not_used(conn: sqlite3.Connection) -> None:
    pid = protocol(conn, "до", "before")
    conn.execute("UPDATE nutrition_protocol SET deleted_at = ? WHERE id = ?", (NOW, pid))
    assert protocols_for(conn, workout(conn, 60))["before"] == []


def test_min_duration_filters_protocol(conn: sqlite3.Connection) -> None:
    protocol(conn, "для долгих", "after", min_duration_min=90)
    assert protocols_for(conn, workout(conn, 60))["after"] == []
    assert names(protocols_for(conn, workout(conn, 90))["after"]) == ["для долгих"]


# --- supplements ---


def test_supplements_for_training_day_include_all_schedules(conn: sqlite3.Connection) -> None:
    for schedule in ["daily", "training_day", "before", "after"]:
        supplement(conn, f"добавка {schedule}", schedule)
    result = protocols_for(conn, workout(conn, 60))
    assert sorted(names(result["supplements"])) == sorted(
        f"добавка {s}" for s in ["daily", "training_day", "before", "after"]
    )


def test_deleted_supplement_is_not_used(conn: sqlite3.Connection) -> None:
    sid = supplement(conn, "креатин")
    conn.execute("UPDATE supplement SET deleted_at = ? WHERE id = ?", (NOW, sid))
    assert protocols_for(conn, workout(conn, 60))["supplements"] == []


def test_protocols_for_writes_nothing(conn: sqlite3.Connection) -> None:
    protocol(conn, "до", "before")
    supplement(conn, "креатин")
    found = workout(conn, 60)
    before = conn.total_changes
    protocols_for(conn, found)
    assert conn.total_changes == before


def test_unknown_duration_gives_protocols_without_min_duration_filter(
    conn: sqlite3.Connection,
) -> None:
    protocol(conn, "для долгих", "after", min_duration_min=90)
    result = protocols_for(conn, workout(conn, None))
    assert names(result["after"]) == ["для долгих"]
