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
    assert result["missing"] == ["Barbell back squat"]
    assert result["duration_s"] == 2400


def test_missing_exercises_use_spec_title_or_readable_code(conn: sqlite3.Connection) -> None:
    wid = workout(conn, "strength", STRENGTH_SPEC)
    codes = ["BARBELL_BENCH_PRESS", "BARBELL_BACK_SQUAT", "UNKNOWN_LIFT"]
    details = json.dumps({"missing_exercises": codes})
    actual(conn, wid, "different", activity_id=activity(conn), details_json=details)
    result = fact(conn, wid, D)
    assert result is not None
    assert result["missing"] == ["Жим лёжа", "Barbell back squat", "UNKNOWN_LIFT"]


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


# Партия 5: неделя и нагрузка. Имена week/load — через модуль, чтобы файл собирался до кода.
WEDNESDAY = "2026-11-11"
WEEK_DAYS = [f"2026-11-{n:02d}" for n in range(9, 16)]  # Пн 9 - Вс 15


def planned_on(
    conn: sqlite3.Connection, day: str, status: str = "pushed", name: str = "Бег"
) -> int:
    spec = {**RUN_SPEC, "name": name}
    values = {"date": day, "sport": "run", "name": name, "status": status, "workout_json": spec}
    workout_id = add_planned_workout(conn, values)
    conn.commit()
    return workout_id


def week_of(conn: sqlite3.Connection, day: str = WEDNESDAY) -> dict[str, Any]:
    from ai_coach.web import training

    return training.week(conn, day)


def test_week_has_seven_days_monday_to_sunday(conn: sqlite3.Connection) -> None:
    days = week_of(conn)["days"]
    assert [d["date"] for d in days] == WEEK_DAYS


@pytest.mark.parametrize("day", ["2026-11-09", "2026-11-15"])
def test_week_edges_give_the_same_week(conn: sqlite3.Connection, day: str) -> None:
    assert [d["date"] for d in week_of(conn, day)["days"]] == WEEK_DAYS


def test_week_empty_days_have_no_planned_and_no_fact(conn: sqlite3.Connection) -> None:
    for entry in week_of(conn)["days"]:
        assert entry["planned"] == []
        assert entry["fact"] == []


def test_week_planned_has_id_name_sport_status(conn: sqlite3.Connection) -> None:
    wid = planned_on(conn, "2026-11-10", "approved", "Лёгкий бег")
    entry = week_of(conn)["days"][1]
    assert entry["planned"] == [
        {"id": wid, "name": "Лёгкий бег", "sport": "run", "status": "approved"}
    ]


def test_week_keeps_statuses_of_several_workouts_of_one_day(conn: sqlite3.Connection) -> None:
    planned_on(conn, "2026-11-12", "draft", "А")
    planned_on(conn, "2026-11-12", "pushed", "Б")
    planned = week_of(conn)["days"][3]["planned"]
    assert [(p["name"], p["status"]) for p in planned] == [("А", "draft"), ("Б", "pushed")]


def test_week_ignores_workouts_outside_the_week(conn: sqlite3.Connection) -> None:
    planned_on(conn, "2026-11-08")
    planned_on(conn, "2026-11-16")
    assert all(d["planned"] == [] for d in week_of(conn)["days"])


def test_week_fact_done_has_kind_and_activity_id(conn: sqlite3.Connection) -> None:
    wid = planned_on(conn, "2026-11-10")
    number = activity(conn, 7, start_time_local="2026-11-10 09:00:00")
    actual(conn, wid, date="2026-11-10", activity_id=number)
    facts = week_of(conn)["days"][1]["fact"]
    assert [(f["kind"], f["activity_id"]) for f in facts] == [("done", 7)]
    assert facts[0]["planned_id"] == wid


def test_week_fact_skipped_has_no_activity(conn: sqlite3.Connection) -> None:
    wid = planned_on(conn, "2026-11-10")
    actual(conn, wid, "skipped", date="2026-11-10")
    facts = week_of(conn)["days"][1]["fact"]
    assert [(f["kind"], f["activity_id"]) for f in facts] == [("skipped", None)]


def test_week_activity_without_plan_is_extra_with_its_name(conn: sqlite3.Connection) -> None:
    activity(conn, 9, start_time_local="2026-11-13 18:00:00", name="Прогулка")
    facts = week_of(conn)["days"][4]["fact"]
    assert facts == [{"kind": "extra", "name": "Прогулка", "activity_id": 9, "planned_id": None}]


def test_week_extra_row_from_plan_actual_takes_activity_name(conn: sqlite3.Connection) -> None:
    activity(conn, 9, start_time_local="2026-11-13 18:00:00", name="Прогулка")
    actual(conn, None, "extra", date="2026-11-13", activity_id=9)  # type: ignore[arg-type]
    facts = week_of(conn)["days"][4]["fact"]
    assert facts == [{"kind": "extra", "name": "Прогулка", "activity_id": 9, "planned_id": None}]


def test_week_activity_matched_to_plan_is_not_duplicated_as_extra(conn: sqlite3.Connection) -> None:
    wid = planned_on(conn, "2026-11-10")
    number = activity(conn, 7, start_time_local="2026-11-10 09:00:00")
    actual(conn, wid, date="2026-11-10", activity_id=number)
    facts = week_of(conn)["days"][1]["fact"]
    assert [f["kind"] for f in facts] == ["done"]


def test_week_activity_outside_the_week_is_ignored(conn: sqlite3.Connection) -> None:
    activity(conn, 1, start_time_local="2026-11-08 23:00:00")
    activity(conn, 2, start_time_local="2026-11-16 00:30:00")
    assert all(d["fact"] == [] for d in week_of(conn)["days"])


def load_of(conn: sqlite3.Connection, day: str = WEDNESDAY) -> dict[str, Any]:
    from ai_coach.web import training

    return training.load(conn, day)


def heart_data(conn: sqlite3.Connection, rest_day: str = "2026-11-05") -> None:
    from ai_coach.store.garmin_data import upsert_daily_metrics, upsert_threshold

    upsert_daily_metrics(conn, {"date": rest_day, "raw_json": {"sleep": {"restingHeartRate": 50}}})
    threshold = {
        "sport": "run",
        "source": "garmin_lt",
        "calendar_date": "2026-11-01",
        "lthr": 170,
        "raw_json": {},
    }
    upsert_threshold(conn, threshold)
    conn.commit()


def test_load_without_rest_hr_is_error_text_and_no_rows(conn: sqlite3.Connection) -> None:
    result = load_of(conn)
    assert result["rows"] is None
    assert "пульса покоя" in result["error"]


def test_load_has_fourteen_days_ending_on_the_day(conn: sqlite3.Connection) -> None:
    heart_data(conn)
    result = load_of(conn)
    assert result["error"] is None
    dates = [r["date"] for r in result["rows"]]
    assert dates[0] == "2026-10-29"
    assert dates[-1] == WEDNESDAY
    assert len(dates) == 14


def test_load_rows_have_tss_ctl_atl(conn: sqlite3.Connection) -> None:
    heart_data(conn)
    row = load_of(conn)["rows"][-1]
    assert {"date", "tss", "ctl", "atl"} <= set(row)
