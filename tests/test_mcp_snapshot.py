import json
import sqlite3

from mcp_fakes import call, call_text

from ai_coach.mcp_server.tools import MAX_CHARS, SNAPSHOT_CHARS, SNAPSHOT_ROWS
from ai_coach.store.garmin_data import upsert_activity, upsert_daily_metrics, upsert_threshold
from ai_coach.store.goals import add_goal, add_phase
from ai_coach.store.journal import add_food, add_sync_log, add_weight
from ai_coach.store.plans import add_plan_actual, add_planned_workout

RAW = "SECRET_RAW_PAYLOAD"
DAY = "2026-10-07"


def fill(conn: sqlite3.Connection) -> None:
    upsert_daily_metrics(
        conn,
        {
            "date": DAY,
            "sleep_score": 77,
            "hrv_last_night": 63,
            "readiness_level": "PRIME",
            "raw_json": {"secret": RAW, "sleep": {"restingHeartRate": 50}},
        },
    )
    upsert_threshold(
        conn,
        {
            "sport": "run",
            "source": "garmin_lt",
            "calendar_date": "2026-09-30",
            "lthr": 170,
            "raw_json": {},
        },
    )
    upsert_activity(
        conn,
        {
            "activity_id": 1,
            "start_time_local": "2026-10-06 07:00:00",
            "type_key": "running",
            "name": "Вчерашний бег",
            "duration_s": 3600,
            "avg_hr": 170,
            "raw_json": {"secret": RAW},
        },
    )
    add_planned_workout(
        conn,
        {"date": DAY, "sport": "swim", "name": "Плавание 1500", "workout_json": {"steps": []}},
    )
    add_goal(conn, {"title": "Олимпийский триатлон", "status": "active"})
    add_goal(conn, {"title": "Закрытая цель", "status": "cancelled"})
    add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 81.7})
    add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": "овсянка с бананом"})
    add_sync_log(conn, {"started_at": f"{DAY} 06:00:00", "kind": "sync", "status": "ok"})


def test_snapshot_contains_all_parts_for_morning(conn: sqlite3.Connection) -> None:
    fill(conn)
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    for expected in [
        "PRIME",
        "Вчерашний бег",
        "Плавание 1500",
        "Олимпийский триатлон",
        "81.7",
        "овсянка с бананом",
        f"{DAY} 06:00:00",
    ]:
        assert expected in text


def test_snapshot_has_all_sections(conn: sqlite3.Connection) -> None:
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert set(snapshot) == {
        "date",
        "metrics",
        "activities",
        "load",
        "load_error",
        "goals",
        "phases_now",
        "phases_proposed",
        "plan",
        "plan_actual",
        "weights",
        "food_today",
        "last_sync",
        "wellbeing",
        "deviations",
        "profile",
    }


def test_snapshot_shows_only_active_goals(conn: sqlite3.Connection) -> None:
    fill(conn)
    assert "Закрытая цель" not in call_text(conn, "get_morning_snapshot", date=DAY)


def test_snapshot_has_load_for_the_day(conn: sqlite3.Connection) -> None:
    fill(conn)
    load = call(conn, "get_morning_snapshot", date=DAY)["load"]["rows"]
    assert load[-1]["date"] == DAY
    assert load[0]["date"] == "2026-10-01"


def test_snapshot_without_lthr_keeps_other_parts(conn: sqlite3.Connection) -> None:
    fill(conn)
    conn.execute("DELETE FROM thresholds")
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert "load_error" not in snapshot
    assert snapshot["warnings"] == [
        "нет порога для run",
        "нет порога для bike",
        "нет порога для swim",
    ]
    assert snapshot["thresholds"] == {}
    assert snapshot["metrics"]["rows"][0]["hrv_last_night"] == 63


def test_snapshot_with_heart_rate_data_has_no_load_error(conn: sqlite3.Connection) -> None:
    fill(conn)
    assert "load_error" not in call(conn, "get_morning_snapshot", date=DAY)


def test_snapshot_has_no_raw_json(conn: sqlite3.Connection) -> None:
    fill(conn)
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert "raw_json" not in text
    assert RAW not in text


def test_snapshot_sections_are_limited(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_ROWS + 5):
        add_goal(conn, {"title": f"Цель {number} " + "x" * 400, "status": "active"})
    snapshot = call(conn, "get_morning_snapshot", date="2099-01-01")
    goals = snapshot["goals"]
    assert goals["truncated"] is True
    assert 0 < len(goals["rows"]) < SNAPSHOT_ROWS + 5
    assert len(json.dumps(goals["rows"], ensure_ascii=False)) <= SNAPSHOT_CHARS


def test_snapshot_fits_total_limit(conn: sqlite3.Connection) -> None:
    big = "я" * 300
    for number in range(SNAPSHOT_ROWS * 2):
        add_goal(conn, {"title": f"Цель {number} {big}", "status": "active"})
        add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": f"еда {number} {big}"})
        add_phase(conn, {"name": f"Фаза {number}", "description": big, "status": "proposed"})
        add_planned_workout(
            conn,
            {"date": DAY, "sport": "run", "name": f"Бег {number} {big}", "workout_json": {}},
        )
        upsert_activity(
            conn,
            {
                "activity_id": number,
                "start_time_local": f"{DAY} 07:00:00",
                "type_key": "running",
                "name": f"Бег {number} {big}",
                "raw_json": {},
            },
        )
        add_plan_actual(
            conn,
            {"date": DAY, "activity_id": number, "kind": "extra", "details_json": {"x": big}},
        )
    assert len(call_text(conn, "get_morning_snapshot", date=DAY)) <= MAX_CHARS


def test_snapshot_without_data_does_not_fail(conn: sqlite3.Connection) -> None:
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert snapshot["date"] == DAY
    assert snapshot["metrics"] == {"rows": [], "truncated": False}
    assert snapshot["last_sync"] is None


def test_snapshot_has_thresholds_with_source(conn: sqlite3.Connection) -> None:
    fill(conn)
    thresholds = call(conn, "get_morning_snapshot", date=DAY)["thresholds"]
    assert thresholds["run"]["source"] == "garmin_lt"
    assert thresholds["bike"] == {"lthr": 163, "source": "derived", "date": "2026-09-30"}
