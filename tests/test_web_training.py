import json
import sqlite3
from typing import Any

import pytest

from ai_coach.store.garmin_data import upsert_activity
from ai_coach.store.plans import add_plan_actual, add_planned_workout, get_planned_workout
from ai_coach.web.training import fact, plan_steps
from ai_coach.workouts.phone import player_payload

D = "2026-11-07"
RUN_SPEC = {
    "name": "Лёгкий бег",
    "estimated_duration_secs": 2400,
    "steps": [
        {"type": "warmup", "seconds": 300, "title": "Разминка"},
        {"type": "interval", "seconds": 1800, "pace_sec_per_km": [420, 380]},
        {"type": "cooldown", "seconds": 300},
    ],
}
STRENGTH_SPEC = {
    "name": "Силовая",
    "estimated_duration_secs": 3000,
    "exercises": [
        {
            "category": "BENCH_PRESS",
            "exercise": "BARBELL_BENCH_PRESS",
            "sets": 3,
            "reps": 8,
            "rest_seconds": 90,
            "weight_kg": 40,
            "title": "Жим лёжа",
        },
        {
            "category": "SQUAT",
            "exercise": "BARBELL_BACK_SQUAT",
            "sets": 3,
            "reps": 5,
            "rest_seconds": 120,
            "weight_kg": 60,
        },
    ],
}
MOBILITY_SPEC = {
    "name": "Растяжка",
    "estimated_duration_secs": 600,
    "steps": [
        {"exercise": "HIP_STRETCH", "seconds": 60, "description": "Левая сторона"},
        {
            "exercise": "HIP_STRETCH",
            "seconds": 60,
            "description": "Правая сторона",
            "title": "Бедро",
        },
    ],
}
SPECS = [("run", RUN_SPEC), ("strength", STRENGTH_SPEC), ("mobility", MOBILITY_SPEC)]
ZONES = {f"hrTimeInZone_{n}": s for n, s in zip(range(1, 6), (360, 1080, 600, 120, 0), strict=True)}


def workout(conn: sqlite3.Connection, sport: str = "run", spec: dict[str, Any] = RUN_SPEC) -> int:
    values = {"date": D, "sport": sport, "name": spec["name"], "workout_json": spec}
    workout_id = add_planned_workout(conn, values)
    conn.commit()
    return workout_id


def activity(conn: sqlite3.Connection, number: int = 1, **fields: Any) -> int:
    values: dict[str, Any] = {
        "activity_id": number,
        "start_time_local": f"{D} 09:00:00",
        "type_key": "running",
        "name": "Бег",
        "duration_s": 2400.0,
        "distance_m": 6000.0,
        "calories": 300.0,
        "avg_hr": 140.0,
        "max_hr": 160.0,
        "training_load": 55.0,
        "raw_json": ZONES,
    }
    upsert_activity(conn, values | fields)
    conn.commit()
    return number


def actual(conn: sqlite3.Connection, planned: int, kind: str = "done", **fields: Any) -> None:
    values = {"date": D, "kind": kind, "planned_id": planned, "activity_id": None} | fields
    add_plan_actual(conn, values)
    conn.commit()


def done_fact(
    conn: sqlite3.Connection, spec: dict[str, Any] = RUN_SPEC, **act: Any
) -> dict[str, Any]:
    wid = workout(conn, "run", spec)
    actual(conn, wid, activity_id=activity(conn, **act))
    result = fact(conn, wid, D)
    assert result is not None
    return result


def row_of(result: dict[str, Any], label: str) -> dict[str, Any] | None:
    return next((r for r in result["rows"] if r["label"].startswith(label)), None)


@pytest.mark.parametrize(("sport", "spec"), SPECS)
def test_plan_steps_are_player_blocks(conn: sqlite3.Connection, sport: str, spec: dict) -> None:
    row = get_planned_workout(conn, workout(conn, sport, spec))
    assert row is not None
    assert plan_steps(row) == player_payload(sport, spec, D)["b"]


def test_plan_steps_of_run_keep_pace_and_titles(conn: sqlite3.Connection) -> None:
    row = get_planned_workout(conn, workout(conn))
    assert row is not None
    steps = plan_steps(row)
    assert steps[0]["s"][0]["t"] == "Разминка"
    assert steps[0]["s"][1]["pace"] == [420, 380]


def test_fact_without_plan_actual_is_none(conn: sqlite3.Connection) -> None:
    assert fact(conn, workout(conn), D) is None


def test_fact_ignores_other_workout_and_other_day(conn: sqlite3.Connection) -> None:
    mine = workout(conn)
    other = workout(conn)
    actual(conn, other, activity_id=activity(conn))
    actual(conn, mine, activity_id=activity(conn, 2), date="2026-11-06")
    assert fact(conn, mine, D) is None


def test_done_fact_numbers_from_activity(conn: sqlite3.Connection) -> None:
    result = done_fact(conn)
    assert result["kind"] == "done"
    assert (result["duration_s"], result["distance_m"], result["calories"]) == (2400, 6000, 300)
    assert (result["avg_hr"], result["max_hr"], result["training_load"]) == (140, 160, 55)
    assert result["source"].startswith("Garmin, синхронизация")


def test_pace_is_seconds_per_km(conn: sqlite3.Connection) -> None:
    assert done_fact(conn)["pace_s_km"] == pytest.approx(400)


@pytest.mark.parametrize("distance", [0, None])
def test_pace_is_none_without_distance(conn: sqlite3.Connection, distance: float | None) -> None:
    assert done_fact(conn, distance_m=distance)["pace_s_km"] is None


def test_zones_are_shares_of_total(conn: sqlite3.Connection) -> None:
    zones = done_fact(conn)["zones"]
    assert zones == pytest.approx([360 / 2160, 1080 / 2160, 600 / 2160, 120 / 2160, 0.0])
    assert sum(zones) == pytest.approx(1)


def test_zones_are_none_when_all_zero(conn: sqlite3.Connection) -> None:
    raw = {f"hrTimeInZone_{n}": 0 for n in range(1, 6)}
    assert done_fact(conn, raw_json=raw)["zones"] is None


def test_zones_are_none_when_activity_has_none(conn: sqlite3.Connection) -> None:
    assert done_fact(conn, raw_json={})["zones"] is None


def test_different_strength_has_missing_exercises(conn: sqlite3.Connection) -> None:
    wid = workout(conn, "strength", STRENGTH_SPEC)
    details = json.dumps({"missing_exercises": ["BARBELL_BACK_SQUAT"]})
    actual(conn, wid, "different", activity_id=activity(conn), details_json=details)
    result = fact(conn, wid, D)
    assert result is not None
    assert result["kind"] == "different"
    assert result["missing"] == ["BARBELL_BACK_SQUAT"]
    assert result["duration_s"] == 2400


def test_skipped_has_kind_and_no_numbers(conn: sqlite3.Connection) -> None:
    wid = workout(conn)
    actual(conn, wid, "skipped")
    result = fact(conn, wid, D)
    assert result is not None
    assert result["kind"] == "skipped"
    for key in ("duration_s", "distance_m", "pace_s_km", "avg_hr", "max_hr", "zones"):
        assert result.get(key) is None, key
    assert not result.get("rows")


def test_duration_row_ok_from_ninety_percent_of_plan(conn: sqlite3.Connection) -> None:
    row = row_of(done_fact(conn, duration_s=2160.0), "Длительность")
    assert row is not None
    assert row["mark"] == "ok"


def test_duration_row_warns_below_ninety_percent(conn: sqlite3.Connection) -> None:
    row = row_of(done_fact(conn, duration_s=2159.0), "Длительность")
    assert row is not None
    assert row["mark"] == "warn"


def test_duration_row_ok_when_longer_than_plan(conn: sqlite3.Connection) -> None:
    row = row_of(done_fact(conn, duration_s=3600.0), "Длительность")
    assert row is not None
    assert row["mark"] == "ok"


def test_pace_row_only_when_plan_has_pace_target(conn: sqlite3.Connection) -> None:
    assert row_of(done_fact(conn), "Темп") is not None
    no_pace = {**RUN_SPEC, "steps": [{"type": "interval", "seconds": 2400}]}
    assert row_of(done_fact(conn, no_pace, number=2), "Темп") is None


def test_distance_row_only_when_plan_has_meters(conn: sqlite3.Connection) -> None:
    assert row_of(done_fact(conn), "Дистанция") is None
    meters = {**RUN_SPEC, "steps": [{"type": "interval", "meters": 6000}]}
    assert row_of(done_fact(conn, meters, number=2), "Дистанция") is not None


@pytest.mark.parametrize(
    ("seconds", "mark"),
    [
        (400, "ok"),
        (420, "ok"),
        (380, "ok"),
        (421, "warn"),
        (379, "warn"),
        (600, "warn"),
        (300, "warn"),
    ],
)
def test_pace_mark_is_ok_inside_target_range(
    conn: sqlite3.Connection, seconds: int, mark: str
) -> None:
    # дистанция 1 км: темп = длительность в секундах; цель RUN_SPEC - 380..420 с/км
    row = row_of(done_fact(conn, duration_s=float(seconds), distance_m=1000.0), "Темп")
    assert row is not None
    assert row["mark"] == mark


METERS_SPEC = {"name": "Бег", "steps": [{"type": "interval", "meters": 6000}]}


@pytest.mark.parametrize(
    ("meters", "mark"), [(6000, "ok"), (5400, "ok"), (5399, "warn"), (3000, "warn")]
)
def test_distance_mark_ok_from_ninety_percent(
    conn: sqlite3.Connection, meters: float, mark: str
) -> None:
    row = row_of(done_fact(conn, METERS_SPEC, distance_m=float(meters)), "Дистанция")
    assert row is not None
    assert row["mark"] == mark


def test_plan_vs_fact_row_texts(conn: sqlite3.Connection) -> None:
    spec = {
        **RUN_SPEC,
        "steps": [{"type": "interval", "meters": 6000, "pace_sec_per_km": [420, 380]}],
    }
    rows = done_fact(conn, spec)["rows"]
    assert [(r["label"], r["plan"], r["fact"], r["mark"]) for r in rows] == [
        ("Длительность", "40 мин", "40 мин", "ok"),
        ("Дистанция", "6.0 км", "6.0 км", "ok"),
        ("Темп", "7:00 /км - 6:20 /км", "6:40 /км", "ok"),
    ]


def test_null_duration_gives_no_pace_and_no_duration_rows(conn: sqlite3.Connection) -> None:
    result = done_fact(conn, duration_s=None)
    assert result["duration_s"] is None
    assert result["pace_s_km"] is None
    assert row_of(result, "Длительность") is None
    assert row_of(result, "Темп") is None


def test_no_average_heart_rate_row(conn: sqlite3.Connection) -> None:
    result = done_fact(conn)
    assert result["avg_hr"] == 140
    assert row_of(result, "Пульс") is None
