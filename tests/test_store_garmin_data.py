import json
import sqlite3

import pytest

from ai_coach.store.garmin_data import (
    get_activity,
    get_daily_metrics,
    list_activities,
    list_daily_metrics,
    list_strength_sets,
    upsert_activity,
    upsert_daily_metrics,
    upsert_strength_set,
)


def activity(activity_id: int, start: str = "2026-03-10 07:00:00", **extra: object) -> dict:
    return {
        "activity_id": activity_id,
        "start_time_local": start,
        "type_key": "running",
        "raw_json": {"activityId": activity_id},
        **extra,
    }


def strength_set(activity_id: int, set_index: int, **extra: object) -> dict:
    return {
        "activity_id": activity_id,
        "set_index": set_index,
        "raw_json": {"i": set_index},
        **extra,
    }


def test_daily_metrics_roundtrip_keeps_raw_json(conn: sqlite3.Connection) -> None:
    raw = {"sleep": {"score": 81}, "hrv": None}
    upsert_daily_metrics(
        conn,
        {"date": "2026-03-10", "sleep_score": 81, "hrv_status": "BALANCED", "raw_json": raw},
    )
    row = get_daily_metrics(conn, "2026-03-10")
    assert row is not None
    assert row["sleep_score"] == 81
    assert row["hrv_status"] == "BALANCED"
    assert json.loads(row["raw_json"]) == raw


def test_daily_metrics_missing_day_is_none(conn: sqlite3.Connection) -> None:
    assert get_daily_metrics(conn, "2026-03-10") is None


def test_daily_metrics_gaps_are_null(conn: sqlite3.Connection) -> None:
    upsert_daily_metrics(conn, {"date": "2026-03-10", "sleep_score": 70, "raw_json": {}})
    row = get_daily_metrics(conn, "2026-03-10")
    assert row is not None
    assert row["hrv_last_night"] is None
    assert row["readiness_score"] is None


def test_daily_metrics_upsert_by_date_no_duplicates(conn: sqlite3.Connection) -> None:
    upsert_daily_metrics(conn, {"date": "2026-03-10", "sleep_score": 70, "raw_json": {"v": 1}})
    upsert_daily_metrics(conn, {"date": "2026-03-10", "sleep_score": 85, "raw_json": {"v": 2}})
    rows = list_daily_metrics(conn, "2026-03-10", "2026-03-10")
    assert len(rows) == 1
    assert rows[0]["sleep_score"] == 85
    assert json.loads(rows[0]["raw_json"]) == {"v": 2}


def test_daily_metrics_repeated_identical_upsert_is_idempotent(conn: sqlite3.Connection) -> None:
    values = {"date": "2026-03-10", "sleep_score": 70, "raw_json": {"v": 1}}
    upsert_daily_metrics(conn, values)
    before = list_daily_metrics(conn, "2026-03-01", "2026-03-31")
    upsert_daily_metrics(conn, values)
    assert list_daily_metrics(conn, "2026-03-01", "2026-03-31") == before


def test_list_daily_metrics_inclusive_range_sorted(conn: sqlite3.Connection) -> None:
    for day in ("2026-03-12", "2026-03-09", "2026-03-10", "2026-03-11", "2026-03-13"):
        upsert_daily_metrics(conn, {"date": day, "raw_json": {}})
    rows = list_daily_metrics(conn, "2026-03-10", "2026-03-12")
    assert [r["date"] for r in rows] == ["2026-03-10", "2026-03-11", "2026-03-12"]


def test_list_daily_metrics_empty_range(conn: sqlite3.Connection) -> None:
    assert list_daily_metrics(conn, "2026-03-10", "2026-03-12") == []


def test_activity_roundtrip_keeps_raw_json(conn: sqlite3.Connection) -> None:
    raw = {"activityId": 5, "activityType": {"typeKey": "running"}}
    upsert_activity(
        conn,
        activity(5, name="Утренний бег", distance_m=10000.5, workout_id=77) | {"raw_json": raw},
    )
    row = get_activity(conn, 5)
    assert row is not None
    assert row["name"] == "Утренний бег"
    assert row["type_key"] == "running"
    assert row["distance_m"] == 10000.5
    assert row["workout_id"] == 77
    assert json.loads(row["raw_json"]) == raw


def test_activity_missing_is_none(conn: sqlite3.Connection) -> None:
    assert get_activity(conn, 404) is None


def test_activity_upsert_by_id_no_duplicates(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(5, name="old", calories=100.0))
    upsert_activity(conn, activity(5, name="new", calories=250.0))
    rows = list_activities(conn, "2026-03-01", "2026-03-31")
    assert len(rows) == 1
    assert rows[0]["name"] == "new"
    assert rows[0]["calories"] == 250.0


def test_activity_upsert_different_ids_are_separate(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(5))
    upsert_activity(conn, activity(6))
    assert len(list_activities(conn, "2026-03-01", "2026-03-31")) == 2


def test_activity_upsert_keeps_strength_sets(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(5, name="a"))
    upsert_strength_set(conn, strength_set(5, 0, reps=10))
    upsert_activity(conn, activity(5, name="b"))
    assert len(list_strength_sets(conn, 5)) == 1


def test_list_activities_by_start_date_inclusive_sorted(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(1, "2026-03-09 23:59:59"))
    upsert_activity(conn, activity(2, "2026-03-11 18:00:00"))
    upsert_activity(conn, activity(3, "2026-03-10 00:00:00"))
    upsert_activity(conn, activity(4, "2026-03-11 06:30:00"))
    upsert_activity(conn, activity(5, "2026-03-12 00:00:00"))
    rows = list_activities(conn, "2026-03-10", "2026-03-11")
    assert [r["activity_id"] for r in rows] == [3, 4, 2]


def test_strength_set_roundtrip(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(5))
    upsert_strength_set(
        conn,
        strength_set(5, 0, wkt_step_index=2, exercise_name="BENCH_PRESS", reps=8, weight=62.5),
    )
    rows = list_strength_sets(conn, 5)
    assert len(rows) == 1
    assert rows[0]["wkt_step_index"] == 2
    assert rows[0]["exercise_name"] == "BENCH_PRESS"
    assert rows[0]["reps"] == 8
    assert rows[0]["weight"] == 62.5
    assert json.loads(rows[0]["raw_json"]) == {"i": 0}


def test_strength_set_upsert_by_activity_and_index(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(5))
    upsert_strength_set(conn, strength_set(5, 0, reps=8))
    upsert_strength_set(conn, strength_set(5, 0, reps=10))
    rows = list_strength_sets(conn, 5)
    assert len(rows) == 1
    assert rows[0]["reps"] == 10


def test_strength_sets_sorted_and_scoped_to_activity(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(5))
    upsert_activity(conn, activity(6))
    for index in (2, 0, 1):
        upsert_strength_set(conn, strength_set(5, index))
    upsert_strength_set(conn, strength_set(6, 0))
    assert [r["set_index"] for r in list_strength_sets(conn, 5)] == [0, 1, 2]
    assert len(list_strength_sets(conn, 6)) == 1
    assert list_strength_sets(conn, 7) == []


def test_strength_set_requires_existing_activity(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        upsert_strength_set(conn, strength_set(999, 0))


def test_strength_set_requires_raw_json(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(5))
    with pytest.raises(sqlite3.IntegrityError):
        upsert_strength_set(conn, {"activity_id": 5, "set_index": 0, "reps": 5})


def test_strength_set_raw_json_none_is_rejected(conn: sqlite3.Connection) -> None:
    upsert_activity(conn, activity(5))
    with pytest.raises(sqlite3.IntegrityError):
        upsert_strength_set(conn, strength_set(5, 0) | {"raw_json": None})


def test_get_and_list_return_raw_json_as_string(conn: sqlite3.Connection) -> None:
    upsert_daily_metrics(conn, {"date": "2026-03-10", "raw_json": {"a": 1}})
    upsert_activity(conn, activity(5))
    upsert_strength_set(conn, strength_set(5, 0))
    metrics = get_daily_metrics(conn, "2026-03-10")
    found = get_activity(conn, 5)
    assert metrics is not None
    assert found is not None
    assert isinstance(metrics["raw_json"], str)
    assert isinstance(found["raw_json"], str)
    for row in (
        list_daily_metrics(conn, "2026-03-10", "2026-03-10")[0],
        list_activities(conn, "2026-03-10", "2026-03-10")[0],
        list_strength_sets(conn, 5)[0],
    ):
        assert isinstance(row["raw_json"], str)
