import json
import sqlite3
from typing import Any

import pytest

from ai_coach.load import rebuild_plan_actual
from ai_coach.store.garmin_data import upsert_activity, upsert_strength_set
from ai_coach.store.plans import add_plan_actual, add_planned_workout, list_plan_actual

STRENGTH_SPEC = {
    "name": "Силовая",
    "exercises": [
        {
            "category": "BENCH_PRESS",
            "exercise": "BARBELL_BENCH_PRESS",
            "sets": 3,
            "reps": 8,
            "rest_seconds": 90,
            "weight_kg": 40,
        },
        {
            "category": "ROW",
            "exercise": "BARBELL_ROW",
            "sets": 3,
            "reps": 8,
            "rest_seconds": 90,
            "weight_kg": 30,
        },
    ],
}
# Шаги по build_strength: stepOrder 1 группа, 2 подход, 3 отдых (упражнение 1);
# 4 группа, 5 подход, 6 отдых (упражнение 2). wktStepIndex = stepOrder - 1,
# значит рабочие подходы упражнений — 1 и 4.
BENCH_STEP = 1
ROW_STEP = 4


def plan(
    conn: sqlite3.Connection,
    date: str,
    sport: str = "run",
    status: str = "pushed",
    spec: dict[str, Any] | None = None,
) -> int:
    values = {
        "date": date,
        "sport": sport,
        "name": f"{sport} {date}",
        "status": status,
        "workout_json": spec or {"name": sport, "steps": []},
    }
    return add_planned_workout(conn, values)


def activity(
    conn: sqlite3.Connection, activity_id: int, start: str, type_key: str = "running"
) -> int:
    upsert_activity(
        conn,
        {
            "activity_id": activity_id,
            "start_time_local": start,
            "type_key": type_key,
            "raw_json": {},
        },
    )
    return activity_id


def active_set(conn: sqlite3.Connection, activity_id: int, index: int, step: int) -> None:
    upsert_strength_set(
        conn,
        {
            "activity_id": activity_id,
            "set_index": index,
            "wkt_step_index": step,
            "set_type": "ACTIVE",
            "raw_json": {},
        },
    )


def rest_set(conn: sqlite3.Connection, activity_id: int, index: int, step: int) -> None:
    upsert_strength_set(
        conn,
        {
            "activity_id": activity_id,
            "set_index": index,
            "wkt_step_index": step,
            "set_type": "REST",
            "raw_json": {},
        },
    )


def rows(conn: sqlite3.Connection, start: str = "2026-03-01", end: str = "2026-03-31") -> list:
    return list_plan_actual(conn, start, end)


def test_done_when_same_date_and_type(conn: sqlite3.Connection) -> None:
    planned = plan(conn, "2026-03-10", "run")
    act = activity(conn, 1, "2026-03-10 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "done"
    assert row["date"] == "2026-03-10"
    assert row["planned_id"] == planned
    assert row["activity_id"] == act


@pytest.mark.parametrize(
    ("sport", "type_key"),
    [
        ("run", "running"),
        ("bike", "cycling"),
        ("swim", "lap_swimming"),
    ],
)
def test_done_for_each_endurance_sport(conn: sqlite3.Connection, sport: str, type_key: str) -> None:
    plan(conn, "2026-03-10", sport)
    activity(conn, 1, "2026-03-10 07:00:00", type_key)
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["kind"] for r in rows(conn)] == ["done"]


def test_skipped_when_no_activity(conn: sqlite3.Connection) -> None:
    planned = plan(conn, "2026-03-10", "run")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "skipped"
    assert row["planned_id"] == planned
    assert row["activity_id"] is None


def test_extra_when_no_plan(conn: sqlite3.Connection) -> None:
    act = activity(conn, 1, "2026-03-10 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "extra"
    assert row["date"] == "2026-03-10"
    assert row["planned_id"] is None
    assert row["activity_id"] == act


def test_different_when_other_sport_on_planned_day(conn: sqlite3.Connection) -> None:
    planned = plan(conn, "2026-03-10", "run")
    act = activity(conn, 1, "2026-03-10 07:00:00", "cycling")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "different"
    assert row["planned_id"] == planned
    assert row["activity_id"] == act
    assert row["details_json"] is None


def test_activity_on_other_day_does_not_match(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-10", "run")
    activity(conn, 1, "2026-03-11 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [(r["date"], r["kind"]) for r in rows(conn)] == [
        ("2026-03-10", "skipped"),
        ("2026-03-11", "extra"),
    ]


def test_one_activity_closes_only_one_planned(conn: sqlite3.Connection) -> None:
    first = plan(conn, "2026-03-10", "run")
    second = plan(conn, "2026-03-10", "run")
    activity(conn, 1, "2026-03-10 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    result = {r["planned_id"]: r["kind"] for r in rows(conn)}
    assert result == {first: "done", second: "skipped"}


def test_two_planned_two_activities_match_by_type(conn: sqlite3.Connection) -> None:
    run = plan(conn, "2026-03-10", "run")
    bike = plan(conn, "2026-03-10", "bike")
    bike_act = activity(conn, 1, "2026-03-10 07:00:00", "cycling")
    run_act = activity(conn, 2, "2026-03-10 18:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    result = {r["planned_id"]: (r["kind"], r["activity_id"]) for r in rows(conn)}
    assert result == {run: ("done", run_act), bike: ("done", bike_act)}


def test_same_type_beats_different_pairing(conn: sqlite3.Connection) -> None:
    run = plan(conn, "2026-03-10", "run")
    swim = plan(conn, "2026-03-10", "swim")
    run_act = activity(conn, 1, "2026-03-10 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    result = {r["planned_id"]: (r["kind"], r["activity_id"]) for r in rows(conn)}
    assert result == {run: ("done", run_act), swim: ("skipped", None)}


@pytest.mark.parametrize("status", ["draft", "approved", "cancelled"])
def test_unpushed_plan_is_ignored(conn: sqlite3.Connection, status: str) -> None:
    plan(conn, "2026-03-10", "run", status=status)
    activity(conn, 1, "2026-03-10 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["kind"] for r in rows(conn)] == ["extra"]


def test_period_bounds_are_inclusive_and_outside_ignored(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-02-28", "run")
    plan(conn, "2026-03-01", "run")
    plan(conn, "2026-03-31", "run")
    plan(conn, "2026-04-01", "run")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["date"] for r in rows(conn, "2026-01-01", "2026-12-31")] == [
        "2026-03-01",
        "2026-03-31",
    ]


def test_activity_late_evening_counts_for_its_local_date(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-31", "run")
    activity(conn, 1, "2026-03-31 23:50:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["kind"] for r in rows(conn)] == ["done"]


def test_rebuild_twice_gives_no_duplicates(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-10", "run")
    activity(conn, 1, "2026-03-10 07:00:00", "running")
    activity(conn, 2, "2026-03-11 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert sorted(r["kind"] for r in rows(conn)) == ["done", "extra"]


def test_rebuild_replaces_stale_rows_in_period_only(conn: sqlite3.Connection) -> None:
    planned = plan(conn, "2026-03-10", "run")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["kind"] for r in rows(conn)] == ["skipped"]
    activity(conn, 1, "2026-03-10 07:00:00", "running")
    old_planned = plan(conn, "2026-02-10", "run")
    add_plan_actual(conn, {"date": "2026-02-10", "kind": "skipped", "planned_id": old_planned})
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [march] = rows(conn)
    assert (march["kind"], march["planned_id"]) == ("done", planned)
    assert [r["planned_id"] for r in rows(conn, "2026-02-01", "2026-02-28")] == [old_planned]


def test_strength_done_when_all_exercises_have_active_sets(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-10", "strength", spec=STRENGTH_SPEC)
    act = activity(conn, 1, "2026-03-10 07:00:00", "strength_training")
    active_set(conn, act, 0, BENCH_STEP)
    rest_set(conn, act, 1, BENCH_STEP + 1)
    active_set(conn, act, 2, ROW_STEP)
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "done"
    assert row["activity_id"] == act


def test_strength_with_missed_exercise_is_different_with_details(
    conn: sqlite3.Connection,
) -> None:
    planned = plan(conn, "2026-03-10", "strength", spec=STRENGTH_SPEC)
    act = activity(conn, 1, "2026-03-10 07:00:00", "strength_training")
    active_set(conn, act, 0, BENCH_STEP)
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "different"
    assert row["planned_id"] == planned
    assert row["activity_id"] == act
    assert json.loads(row["details_json"])["missing_exercises"] == ["BARBELL_ROW"]


def test_strength_rest_sets_do_not_count_as_done(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-10", "strength", spec=STRENGTH_SPEC)
    act = activity(conn, 1, "2026-03-10 07:00:00", "strength_training")
    active_set(conn, act, 0, BENCH_STEP)
    rest_set(conn, act, 1, ROW_STEP)
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "different"
    assert json.loads(row["details_json"])["missing_exercises"] == ["BARBELL_ROW"]


def test_strength_without_planned_steps_is_different(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-10", "strength", spec=STRENGTH_SPEC)
    act = activity(conn, 1, "2026-03-10 07:00:00", "strength_training")
    active_set(conn, act, 0, 99)
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "different"
    missing = json.loads(row["details_json"])["missing_exercises"]
    assert missing == ["BARBELL_BENCH_PRESS", "BARBELL_ROW"]


def test_strength_planned_but_only_run_done_is_different(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-10", "strength", spec=STRENGTH_SPEC)
    activity(conn, 1, "2026-03-10 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["kind"] for r in rows(conn)] == ["different"]


def test_strength_skipped_when_no_activity(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-10", "strength", spec=STRENGTH_SPEC)
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["kind"] for r in rows(conn)] == ["skipped"]


def test_mobility_plan_is_skipped_and_does_not_take_activity(conn: sqlite3.Connection) -> None:
    plan(conn, "2026-03-10", "mobility")
    act = activity(conn, 1, "2026-03-10 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    [row] = rows(conn)
    assert row["kind"] == "extra"
    assert row["planned_id"] is None
    assert row["activity_id"] == act


def test_two_equal_plans_lower_id_gets_earlier_activity(conn: sqlite3.Connection) -> None:
    first = plan(conn, "2026-03-10", "run")
    second = plan(conn, "2026-03-10", "run")
    evening = activity(conn, 1, "2026-03-10 18:00:00", "running")
    morning = activity(conn, 2, "2026-03-10 07:00:00", "running")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    result = {r["planned_id"]: (r["kind"], r["activity_id"]) for r in rows(conn)}
    assert result == {first: ("done", morning), second: ("done", evening)}


def test_two_unpaired_plans_take_foreign_activities_in_order(conn: sqlite3.Connection) -> None:
    first = plan(conn, "2026-03-10", "run")
    second = plan(conn, "2026-03-10", "swim")
    evening = activity(conn, 1, "2026-03-10 18:00:00", "cycling")
    morning = activity(conn, 2, "2026-03-10 07:00:00", "strength_training")
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    result = {r["planned_id"]: (r["kind"], r["activity_id"]) for r in rows(conn)}
    assert result == {first: ("different", morning), second: ("different", evening)}


@pytest.mark.parametrize(
    ("sport", "type_key"),
    [
        ("run", "treadmill_running"),
        ("bike", "indoor_cycling"),
        ("bike", "road_biking"),
    ],
)
def test_done_for_non_first_type_key(conn: sqlite3.Connection, sport: str, type_key: str) -> None:
    plan(conn, "2026-03-10", sport)
    activity(conn, 1, "2026-03-10 07:00:00", type_key)
    rebuild_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["kind"] for r in rows(conn)] == ["done"]
