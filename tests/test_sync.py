import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from garmin_fakes import FakeGarmin, snapshot, sync_log
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectNotFoundError,
    GarminConnectTooManyRequestsError,
)

from ai_coach.garmin.client import GarminError
from ai_coach.store.garmin_data import (
    get_activity,
    get_daily_metrics,
    last_threshold,
    list_activities,
    list_daily_metrics,
    list_strength_sets,
)
from ai_coach.sync.garmin_sync import sync

TODAY = date(2026, 3, 10)
ACTIVITY_ID = 9000000001


def day(back: int = 0) -> str:
    return (TODAY - timedelta(days=back)).isoformat()


def run_sync(conn: sqlite3.Connection, client: FakeGarmin, days: int) -> str:
    return sync(conn, client, days, pause=0, today=TODAY)  # type: ignore[arg-type]


def test_sync_writes_daily_metrics_summary(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    row = get_daily_metrics(conn, day())
    assert row is not None
    assert row["sleep_seconds"] == 27000
    assert row["sleep_score"] == 80
    assert row["hrv_last_night"] == 48
    assert row["hrv_weekly_avg"] == 50
    assert row["hrv_status"] == "BALANCED"
    assert row["body_battery_charged"] == 60
    assert row["body_battery_drained"] == 55
    assert row["stress_avg"] == 30
    assert row["readiness_score"] == 70
    assert row["readiness_level"] == "MODERATE"


def test_sync_keeps_raw_json_of_metrics(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    row = get_daily_metrics(conn, day())
    assert row is not None
    assert isinstance(json.loads(row["raw_json"]), dict)
    assert "dailySleepDTO" in row["raw_json"]
    assert "hrvSummary" in row["raw_json"]


def test_sync_days_limits_period_including_today(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 3)
    rows = list_daily_metrics(conn, day(10), day())
    assert [r["date"] for r in rows] == [day(2), day(1), day()]


def test_sync_asks_garmin_only_for_requested_days(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin()
    run_sync(conn, fake, 2)
    asked = {day for method, day in fake.calls if method == "get_sleep_data"}
    assert asked == {day(1), day()}


def test_sync_writes_activity(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    row = get_activity(conn, ACTIVITY_ID)
    assert row is not None
    assert row["type_key"] == "strength_training"
    assert row["start_time_local"] == f"{day()} 11:57:32"
    assert row["start_time_gmt"] == f"{day()} 06:57:32"
    assert row["name"] == "Тренировка"
    assert row["duration_s"] == 2400.0
    assert row["distance_m"] == 0.0
    assert row["calories"] == 260.0
    assert row["avg_hr"] == 120.0
    assert row["max_hr"] == 155.0
    assert row["training_load"] == 25.5
    assert row["workout_id"] == 5000001
    assert json.loads(row["raw_json"])["activityId"] == ACTIVITY_ID


def test_sync_writes_strength_sets_with_wkt_step_index(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    sets = list_strength_sets(conn, ACTIVITY_ID)
    assert [s["set_index"] for s in sets] == [0, 1, 2, 3, 4]
    assert [s["wkt_step_index"] for s in sets] == [0, 1, 2, 3, 5]


def test_sync_strength_set_fields(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    second = list_strength_sets(conn, ACTIVITY_ID)[1]
    assert second["exercise_category"] == "BENCH_PRESS"
    assert second["exercise_name"] == "BARBELL_BENCH_PRESS"
    assert second["reps"] == 10
    assert second["duration_s"] == 45.0
    assert second["set_type"] == "ACTIVE"
    assert second["start_time"] == "2026-03-10T06:58:32.0"
    assert json.loads(second["raw_json"])["wktStepIndex"] == 1


def test_sync_strength_weight_is_stored_in_kg(conn: sqlite3.Connection) -> None:
    # Garmin отдаёт вес в граммах (40000 = 40 кг); решение «кг» — по спайку, подтвердить с кабаном
    run_sync(conn, FakeGarmin(), 1)
    sets = list_strength_sets(conn, ACTIVITY_ID)
    assert sets[1]["weight"] == 40.0


def test_sync_strength_set_without_reps_and_weight_is_null(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    warm_up = list_strength_sets(conn, ACTIVITY_ID)[0]
    assert warm_up["reps"] is None
    assert warm_up["weight"] is None


def test_sync_strength_set_with_zero_reps_keeps_zero(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    last = list_strength_sets(conn, ACTIVITY_ID)[4]
    assert last["reps"] == 0


def test_sync_does_not_fetch_sets_for_non_strength(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin(with_run=True)
    run_sync(conn, fake, 1)
    assert len(list_activities(conn, day(), day())) == 2
    assert ("get_activity_exercise_sets", 9000000002) not in fake.calls
    assert list_strength_sets(conn, 9000000002) == []


def test_repeated_sync_does_not_change_database(conn: sqlite3.Connection, tmp_path: Path) -> None:
    run_sync(conn, FakeGarmin(with_run=True), 3)
    conn.commit()
    first = snapshot(tmp_path / "coach.db")
    run_sync(conn, FakeGarmin(with_run=True), 3)
    conn.commit()
    assert snapshot(tmp_path / "coach.db") == first


def test_repeated_sync_does_not_duplicate_rows(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 2)
    run_sync(conn, FakeGarmin(), 2)
    assert len(list_daily_metrics(conn, day(10), day())) == 2
    assert len(list_activities(conn, day(10), day())) == 1
    assert len(list_strength_sets(conn, ACTIVITY_ID)) == 5


def test_sync_updates_changed_activity(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    fake = FakeGarmin()
    fake.activities[0]["activityName"] = "Переименована"
    run_sync(conn, fake, 1)
    row = get_activity(conn, ACTIVITY_ID)
    assert row is not None
    assert row["name"] == "Переименована"
    assert len(list_activities(conn, day(10), day())) == 1


def test_sync_updates_changed_set(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    fake = FakeGarmin()
    fake.sets["exerciseSets"][1]["repetitionCount"] = 12
    run_sync(conn, fake, 1)
    sets = list_strength_sets(conn, ACTIVITY_ID)
    assert len(sets) == 5
    assert sets[1]["reps"] == 12


def test_sync_survives_day_without_sleep(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin(empty={"get_sleep_data": {day(1)}})
    run_sync(conn, fake, 3)
    row = get_daily_metrics(conn, day(1))
    assert row is not None
    assert row["sleep_seconds"] is None
    assert row["sleep_score"] is None
    assert row["hrv_last_night"] == 48
    assert row["stress_avg"] == 30


def test_sync_survives_every_metric_empty_for_a_day(conn: sqlite3.Connection) -> None:
    names = ["get_sleep_data", "get_hrv_data", "get_stress_data"]
    names += ["get_body_battery", "get_training_readiness"]
    fake = FakeGarmin(empty={n: {day(1)} for n in names})
    run_sync(conn, fake, 3)
    assert get_daily_metrics(conn, day(2)) is not None
    assert get_daily_metrics(conn, day()) is not None
    empty_day = get_daily_metrics(conn, day(1))
    if empty_day is not None:
        assert empty_day["sleep_seconds"] is None
        assert empty_day["hrv_last_night"] is None
        assert empty_day["readiness_score"] is None


def test_sync_survives_garmin_404_for_a_metric(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin(missing={"get_training_readiness": {day()}})
    run_sync(conn, fake, 2)
    row = get_daily_metrics(conn, day())
    assert row is not None
    assert row["readiness_score"] is None
    assert row["sleep_score"] == 80
    other = get_daily_metrics(conn, day(1))
    assert other is not None
    assert other["readiness_score"] == 70


def test_sync_fills_gap_when_data_arrives_later(conn: sqlite3.Connection) -> None:
    gap = FakeGarmin(empty={"get_sleep_data": {day()}})
    run_sync(conn, gap, 1)
    run_sync(conn, FakeGarmin(), 1)
    row = get_daily_metrics(conn, day())
    assert row is not None
    assert row["sleep_score"] == 80


def test_sync_without_activities_is_ok(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin()
    fake.activities = []
    run_sync(conn, fake, 1)
    assert list_activities(conn, day(10), day()) == []
    assert get_daily_metrics(conn, day()) is not None


def test_sync_writes_ok_to_sync_log(conn: sqlite3.Connection, tmp_path: Path) -> None:
    run_sync(conn, FakeGarmin(), 1)
    conn.commit()
    rows = sync_log(tmp_path / "coach.db")
    assert len(rows) == 1
    assert rows[0]["kind"] == "sync"
    assert rows[0]["status"] == "ok"
    assert rows[0]["started_at"]
    assert rows[0]["finished_at"]


def test_each_sync_adds_a_sync_log_row(conn: sqlite3.Connection, tmp_path: Path) -> None:
    run_sync(conn, FakeGarmin(), 1)
    run_sync(conn, FakeGarmin(), 1)
    conn.commit()
    assert len(sync_log(tmp_path / "coach.db")) == 2


@pytest.mark.parametrize(
    ("garmin_error", "hint"),
    [
        (GarminConnectAuthenticationError("401"), "coach login"),
        (GarminConnectTooManyRequestsError("429"), "429"),
    ],
)
def test_sync_error_is_clear_and_database_stays_intact(
    conn: sqlite3.Connection, tmp_path: Path, garmin_error: Exception, hint: str
) -> None:
    run_sync(conn, FakeGarmin(), 3)
    conn.commit()
    before = snapshot(tmp_path / "coach.db")
    broken = FakeGarmin(fail={"get_hrv_data": garmin_error})
    with pytest.raises(GarminError) as raised:
        run_sync(conn, broken, 5)
    assert hint in str(raised.value)
    assert snapshot(tmp_path / "coach.db") == before


def test_sync_error_in_activities_leaves_metrics_unwritten(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    broken = FakeGarmin(fail={"get_activities_by_date": GarminConnectTooManyRequestsError("429")})
    with pytest.raises(GarminError):
        run_sync(conn, broken, 3)
    assert snapshot(tmp_path / "coach.db")["daily_metrics"] == []


def test_sync_error_in_sets_leaves_activity_unwritten(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    broken = FakeGarmin(
        fail={"get_activity_exercise_sets": GarminConnectAuthenticationError("401")}
    )
    with pytest.raises(GarminError):
        run_sync(conn, broken, 1)
    data = snapshot(tmp_path / "coach.db")
    assert data["activities"] == []
    assert data["strength_sets"] == []


def test_sync_error_is_written_to_sync_log(conn: sqlite3.Connection, tmp_path: Path) -> None:
    broken = FakeGarmin(fail={"get_sleep_data": GarminConnectTooManyRequestsError("429")})
    with pytest.raises(GarminError):
        run_sync(conn, broken, 1)
    rows = sync_log(tmp_path / "coach.db")
    assert len(rows) == 1
    assert rows[0]["kind"] == "sync"
    assert rows[0]["status"] == "error"
    assert rows[0]["finished_at"]
    assert rows[0]["message"]


@pytest.mark.parametrize("answer", ["404", "none"])
def test_sync_survives_missing_sets_of_strength_activity(
    conn: sqlite3.Connection, answer: str
) -> None:
    if answer == "404":
        fake = FakeGarmin(fail={"get_activity_exercise_sets": GarminConnectNotFoundError("404")})
    else:
        fake = FakeGarmin()
        fake.sets = None
    run_sync(conn, fake, 1)
    assert get_activity(conn, ACTIVITY_ID) is not None
    assert list_strength_sets(conn, ACTIVITY_ID) == []
    assert get_daily_metrics(conn, day()) is not None


def test_sync_network_error_is_clear_and_database_stays_intact(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    run_sync(conn, FakeGarmin(), 3)
    conn.commit()
    before = snapshot(tmp_path / "coach.db")
    broken = FakeGarmin(fail={"get_hrv_data": GarminConnectConnectionError("network down")})
    with pytest.raises(GarminError) as raised:
        run_sync(conn, broken, 5)
    assert str(raised.value)
    assert snapshot(tmp_path / "coach.db") == before


def test_sync_network_error_is_written_to_sync_log(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    broken = FakeGarmin(fail={"get_sleep_data": GarminConnectConnectionError("network down")})
    with pytest.raises(GarminError):
        run_sync(conn, broken, 1)
    rows = sync_log(tmp_path / "coach.db")
    assert [(r["kind"], r["status"]) for r in rows] == [("sync", "error")]
    assert rows[0]["message"]


def test_sync_writes_lthr_from_garmin(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(), 1)
    row = last_threshold(conn, "2099-01-01")
    assert row is not None
    assert (row["calendar_date"], row["lthr"]) == ("2026-03-09", 168)


def test_sync_without_lthr_data_still_syncs(conn: sqlite3.Connection) -> None:
    for error in (GarminConnectNotFoundError("404"), TypeError("None")):
        run_sync(conn, FakeGarmin(fail={"get_lactate_threshold": error}), 1)
    assert last_threshold(conn, "2099-01-01") is None
    assert get_daily_metrics(conn, day()) is not None


def test_sync_with_empty_lthr_answer_does_not_write_it(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin()
    fake.lactate = {"speed_and_heart_rate": {"heartRate": None}, "power": {}}
    run_sync(conn, fake, 1)
    assert last_threshold(conn, "2099-01-01") is None


def test_sync_cuts_time_from_lthr_date(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin()
    fake.lactate["speed_and_heart_rate"]["calendarDate"] = "2026-03-09T00:00:00.0"
    run_sync(conn, fake, 1)
    row = last_threshold(conn, "2026-03-09")
    assert row is not None
    assert row["calendar_date"] == "2026-03-09"
