import json
import sqlite3
from datetime import date, timedelta

from mcp_fakes import call, call_text

from ai_coach.mcp_server.tools import MAX_CHARS, SNAPSHOT_CHARS, SNAPSHOT_ROWS
from ai_coach.store.garmin_data import upsert_activity, upsert_daily_metrics, upsert_threshold
from ai_coach.store.goals import add_goal, add_phase
from ai_coach.store.journal import add_food, add_sync_log, add_weight
from ai_coach.store.meds import add_med, delete_med
from ai_coach.store.plans import add_plan_actual, add_planned_workout
from ai_coach.store.sport_nutrition import (
    add_protocol,
    add_supplement,
    delete_protocol,
    delete_supplement,
)

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
        "pantry",
        "pantry_expiring",
        "meal_plan_today",
        "recipes",
        "catalog",
        "first_run_today",
        "workload",
        "workload_ahead",
        "agenda",
        "overload",
        "evening_done_today",
        "habits_today",
        "week_review_due",
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


def test_snapshot_without_meds_has_no_meds_today(conn: sqlite3.Connection) -> None:
    fill(conn)
    assert "meds_today" not in call(conn, "get_morning_snapshot", date=DAY)


def test_snapshot_has_meds_today_for_active_course(conn: sqlite3.Connection) -> None:
    fill(conn)
    add_med(
        conn,
        {
            "name": "витамин D",
            "kind": "vitamin",
            "dose": 25.0,
            "unit": "mcg",
            "schedule": "daily",
            "start_date": "2026-10-01",
            "note": RAW,
            "created_at": f"{DAY} 06:00:00",
        },
    )
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert [r["name"] for r in snapshot["meds_today"]["rows"]] == ["витамин D"]
    assert RAW not in call_text(conn, "get_morning_snapshot", date=DAY)


def test_snapshot_with_many_big_meds_fits_total_limit(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_ROWS * 2):
        add_med(
            conn,
            {
                "name": f"курс {number} " + "я" * 300,
                "kind": "otc",
                "dose": 1.0,
                "unit": "pcs",
                "schedule": "daily",
                "time_note": "я" * 300,
                "start_date": "2026-10-01",
                "created_at": f"{DAY} 06:00:00",
            },
        )
    assert len(call_text(conn, "get_morning_snapshot", date=DAY)) <= MAX_CHARS


# --- шаг 20: catalog ---


def new_med(conn: sqlite3.Connection) -> int:
    return add_med(
        conn,
        {
            "name": "витамин D",
            "kind": "vitamin",
            "dose": 25.0,
            "unit": "mcg",
            "schedule": "daily",
            "start_date": "2026-10-01",
            "created_at": f"{DAY} 06:00:00",
        },
    )


def new_protocol(conn: sqlite3.Connection, name: str = "гель") -> int:
    return add_protocol(
        conn,
        {
            "name": name,
            "phase": "before",
            "sport": None,
            "min_duration_min": 0,
            "offset_min": 30,
            "carbs_g": 30.0,
            "protein_g": 0.0,
            "fluid_ml": 200.0,
            "sodium_mg": 0.0,
            "note": None,
            "created_at": f"{DAY} 06:00:00",
            "updated_at": f"{DAY} 06:00:00",
        },
    )


def new_supplement(conn: sqlite3.Connection) -> int:
    return add_supplement(
        conn,
        {
            "name": "креатин",
            "dose": 5.0,
            "unit": "g",
            "schedule": "daily",
            "time_note": None,
            "note": None,
            "created_at": f"{DAY} 06:00:00",
            "updated_at": f"{DAY} 06:00:00",
        },
    )


def test_snapshot_catalog_is_zero_when_empty(conn: sqlite3.Connection) -> None:
    catalog = call(conn, "get_morning_snapshot", date=DAY)["catalog"]
    assert catalog == {"protocols": 0, "supplements": 0, "meds": 0}


def test_snapshot_catalog_counts_one_each(conn: sqlite3.Connection) -> None:
    new_protocol(conn)
    new_supplement(conn)
    new_med(conn)
    catalog = call(conn, "get_morning_snapshot", date=DAY)["catalog"]
    assert catalog == {"protocols": 1, "supplements": 1, "meds": 1}


def test_snapshot_catalog_does_not_count_deleted(conn: sqlite3.Connection) -> None:
    delete_protocol(conn, new_protocol(conn), f"{DAY} 12:00:00")
    delete_supplement(conn, new_supplement(conn), f"{DAY} 12:00:00")
    delete_med(conn, new_med(conn), f"{DAY} 12:00:00")
    catalog = call(conn, "get_morning_snapshot", date=DAY)["catalog"]
    assert catalog == {"protocols": 0, "supplements": 0, "meds": 0}


def test_snapshot_catalog_counts_more_than_snapshot_rows(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_ROWS + 5):
        new_protocol(conn, f"гель {number}")
    catalog = call(conn, "get_morning_snapshot", date=DAY)["catalog"]
    assert catalog["protocols"] == SNAPSHOT_ROWS + 5


def test_snapshot_catalog_is_kept_when_sections_are_cut(conn: sqlite3.Connection) -> None:
    big = "я" * 300
    new_protocol(conn)
    new_supplement(conn)
    new_med(conn)
    for number in range(SNAPSHOT_ROWS * 2):
        add_goal(conn, {"title": f"Цель {number} {big}", "status": "active"})
        add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": f"еда {number} {big}"})
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert snapshot["catalog"] == {"protocols": 1, "supplements": 1, "meds": 1}


def test_snapshot_training_without_protocol_keeps_empty_protocol_catalog(
    conn: sqlite3.Connection,
) -> None:
    fill(conn)
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert snapshot["plan"]["rows"]
    assert snapshot["catalog"]["protocols"] == 0


def test_snapshot_training_today_without_protocol_has_workouts_and_no_rows(
    conn: sqlite3.Connection,
) -> None:
    fill(conn)
    part = call(conn, "get_morning_snapshot", date=DAY)["sport_nutrition_today"]
    assert part["workouts"]
    assert part["rows"] == []


# --- шаг 22: first_run_today ---


def sync_at(
    conn: sqlite3.Connection, started_at: str, kind: str = "sync", status: str = "ok"
) -> None:
    add_sync_log(conn, {"started_at": started_at, "kind": kind, "status": status})


def first_run(conn: sqlite3.Connection) -> bool:
    return call(conn, "get_morning_snapshot", date=DAY)["first_run_today"]


def test_snapshot_first_run_today_with_empty_sync_log(conn: sqlite3.Connection) -> None:
    assert first_run(conn) is True


def test_snapshot_first_run_today_with_one_sync(conn: sqlite3.Connection) -> None:
    sync_at(conn, f"{DAY} 06:00:00")
    assert first_run(conn) is True


def test_snapshot_not_first_run_today_with_two_syncs(conn: sqlite3.Connection) -> None:
    sync_at(conn, f"{DAY} 06:00:00")
    sync_at(conn, f"{DAY} 12:00:00")
    assert first_run(conn) is False


def test_snapshot_first_run_today_with_one_sync_yesterday_and_one_today(
    conn: sqlite3.Connection,
) -> None:
    sync_at(conn, f"{date.fromisoformat(DAY) - timedelta(days=1)} 06:00:00")
    sync_at(conn, f"{DAY} 06:00:00")
    assert first_run(conn) is True


def test_snapshot_not_first_run_today_when_error_and_ok_syncs(conn: sqlite3.Connection) -> None:
    sync_at(conn, f"{DAY} 06:00:00", status="error")
    sync_at(conn, f"{DAY} 06:05:00", status="ok")
    assert first_run(conn) is False


def test_snapshot_first_run_today_ignores_import(conn: sqlite3.Connection) -> None:
    sync_at(conn, f"{DAY} 06:00:00", kind="import")
    sync_at(conn, f"{DAY} 06:05:00", kind="sync")
    assert first_run(conn) is True


def test_snapshot_first_run_today_counts_both_started_at_formats(
    conn: sqlite3.Connection,
) -> None:
    sync_at(conn, f"{DAY}T06:00:00")
    sync_at(conn, f"{DAY} 12:00:00")
    assert first_run(conn) is False


def test_snapshot_first_run_today_is_kept_when_sections_are_cut(
    conn: sqlite3.Connection,
) -> None:
    big = "я" * 300
    sync_at(conn, f"{DAY} 06:00:00")
    sync_at(conn, f"{DAY} 12:00:00")
    for number in range(SNAPSHOT_ROWS * 2):
        add_goal(conn, {"title": f"Цель {number} {big}", "status": "active"})
        add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": f"еда {number} {big}"})
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert len(text) <= MAX_CHARS
    assert json.loads(text)["first_run_today"] is False
