import sqlite3
from datetime import date, timedelta

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, rows

from ai_coach.goals import create_goal
from ai_coach.mcp_server.tools import MAX_CHARS, MAX_DAYS, MAX_ROWS
from ai_coach.store.garmin_data import (
    upsert_activity,
    upsert_daily_metrics,
    upsert_strength_set,
    upsert_threshold,
)
from ai_coach.store.goals import add_goal, add_phase
from ai_coach.store.journal import add_food, add_weight
from ai_coach.store.plans import add_plan_actual, add_planned_workout

RAW = "SECRET_RAW_PAYLOAD"


def metrics(conn: sqlite3.Connection, date: str, hrv: int = 55) -> None:
    upsert_daily_metrics(
        conn,
        {
            "date": date,
            "sleep_seconds": 27000,
            "sleep_score": 81,
            "hrv_last_night": hrv,
            "readiness_level": "HIGH",
            "raw_json": {"secret": RAW},
        },
    )


def activity(
    conn: sqlite3.Connection, activity_id: int, start: str, name: str = "Утренний бег"
) -> None:
    upsert_activity(
        conn,
        {
            "activity_id": activity_id,
            "start_time_local": start,
            "type_key": "running",
            "name": name,
            "duration_s": 3000,
            "raw_json": {"secret": RAW},
        },
    )


def test_daily_metrics_returns_rows_of_period(conn: sqlite3.Connection) -> None:
    metrics(conn, "2026-10-01")
    metrics(conn, "2026-10-02", hrv=61)
    metrics(conn, "2026-10-09")
    result = rows(conn, "get_daily_metrics", start="2026-10-01", end="2026-10-03")
    assert [row["date"] for row in result] == ["2026-10-01", "2026-10-02"]
    assert result[1]["hrv_last_night"] == 61


def test_daily_metrics_have_no_raw_json(conn: sqlite3.Connection) -> None:
    metrics(conn, "2026-10-01")
    text = call_text(conn, "get_daily_metrics", start="2026-10-01", end="2026-10-02")
    assert "raw_json" not in text
    assert RAW not in text


def test_activities_have_no_raw_json(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-10-01 07:00:00")
    text = call_text(conn, "get_activities", start="2026-10-01", end="2026-10-02")
    assert "Утренний бег" in text
    assert "raw_json" not in text
    assert RAW not in text


def test_strength_sets_have_no_raw_json(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-10-01 07:00:00")
    upsert_strength_set(
        conn,
        {"activity_id": 1, "set_index": 0, "reps": 8, "weight": 40.0, "raw_json": {"s": RAW}},
    )
    text = call_text(conn, "get_strength_sets", activity_id=1)
    assert "40.0" in text
    assert "raw_json" not in text
    assert RAW not in text


def test_plan_returns_workouts_of_period_with_spec_as_object(conn: sqlite3.Connection) -> None:
    add_planned_workout(
        conn,
        {"date": "2026-10-05", "sport": "run", "name": "Лёгкий бег", "workout_json": {"steps": []}},
    )
    result = rows(conn, "get_plan", start="2026-10-05", end="2026-10-06")
    assert [row["name"] for row in result] == ["Лёгкий бег"]
    assert result[0]["status"] == "draft"
    assert result[0]["workout_json"] == {"steps": []}


def test_period_without_data_gives_empty_list(conn: sqlite3.Connection) -> None:
    assert rows(conn, "get_daily_metrics", start="2026-10-01", end="2026-10-08") == []


def test_period_without_data_is_not_truncated(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_daily_metrics", start="2026-10-01", end="2026-10-08")
    assert result == {"rows": [], "truncated": False}


def test_rows_are_limited_and_marked_truncated(conn: sqlite3.Connection) -> None:
    for day in range(MAX_ROWS + 10):
        metrics(conn, (date(2026, 1, 1) + timedelta(days=day)).isoformat())
    result = call(conn, "get_daily_metrics", start="2026-01-01", end="2026-03-31")
    assert len(result["rows"]) == MAX_ROWS
    assert result["truncated"] is True


def test_response_size_is_limited(conn: sqlite3.Connection) -> None:
    for activity_id in range(MAX_ROWS):
        activity(conn, activity_id, "2026-10-01 07:00:00", name="Бег " * 2000)
    text = call_text(conn, "get_activities", start="2026-10-01", end="2026-10-02")
    assert 0 < len(text) <= MAX_CHARS
    assert call(conn, "get_activities", start="2026-10-01", end="2026-10-02")["truncated"] is True


def test_goals_are_listed(conn: sqlite3.Connection) -> None:
    add_goal(conn, {"title": "Полумарафон", "status": "active"})
    assert [goal["title"] for goal in rows(conn, "get_goals")] == ["Полумарафон"]


def test_goals_filtered_by_status(conn: sqlite3.Connection) -> None:
    add_goal(conn, {"title": "Старая", "status": "done"})
    add_goal(conn, {"title": "Новая", "status": "active"})
    assert [goal["title"] for goal in rows(conn, "get_goals", status="done")] == ["Старая"]


def test_weights_and_food_are_listed(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-05 07:00:00", "weight_kg": 82.4})
    add_food(conn, {"logged_at": "2026-10-05 13:00:00", "text": "борщ и хлеб"})
    weights = rows(conn, "get_weights", start="2026-10-05", end="2026-10-06")
    food = rows(conn, "get_food", start="2026-10-05", end="2026-10-06")
    assert weights[0]["weight_kg"] == 82.4
    assert food[0]["text"] == "борщ и хлеб"


def test_reversed_period_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        rows(conn, "get_daily_metrics", start="2026-10-08", end="2026-10-01")


def test_too_long_period_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_activities", start="2025-01-01", end=f"2025-{MAX_DAYS // 30 + 3:02d}-28")


def test_bad_date_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        rows(conn, "get_plan", start="завтра", end="2026-10-08")


def heart_rate(conn: sqlite3.Connection, rest_hr: int = 50, lthr: int = 170) -> None:
    """Пульс покоя лежит в ответе сна (raw_json), порог — в таблице thresholds."""
    upsert_daily_metrics(
        conn, {"date": "2026-10-01", "raw_json": {"sleep": {"restingHeartRate": rest_hr}}}
    )
    upsert_threshold(conn, {"calendar_date": "2026-09-30", "lthr": lthr, "raw_json": {}})


def test_load_without_rest_hr_asks_for_sync(conn: sqlite3.Connection) -> None:
    upsert_threshold(conn, {"calendar_date": "2026-09-30", "lthr": 170, "raw_json": {}})
    with pytest.raises(ToolError, match="пульса покоя"):
        call(conn, "get_load", start="2026-10-01", end="2026-10-07")


def test_load_without_lthr_says_garmin_gave_none(conn: sqlite3.Connection) -> None:
    upsert_daily_metrics(
        conn, {"date": "2026-10-01", "raw_json": {"sleep": {"restingHeartRate": 50}}}
    )
    with pytest.raises(ToolError, match="LTHR"):
        call(conn, "get_load", start="2026-10-01", end="2026-10-07")


def test_load_with_lthr_not_above_rest_hr_is_rejected(conn: sqlite3.Connection) -> None:
    heart_rate(conn, rest_hr=60, lthr=60)
    with pytest.raises(ToolError, match="LTHR"):
        call(conn, "get_load", start="2026-10-01", end="2026-10-07")


def test_load_uses_latest_rest_hr_up_to_end_of_period(conn: sqlite3.Connection) -> None:
    heart_rate(conn, rest_hr=50, lthr=170)
    upsert_daily_metrics(
        conn, {"date": "2026-10-04", "raw_json": {"sleep": {"restingHeartRate": 60}}}
    )
    upsert_daily_metrics(conn, {"date": "2026-10-05", "raw_json": {"sleep": {}}})
    upsert_activity(
        conn,
        {
            "activity_id": 1,
            "start_time_local": "2026-10-05 07:00:00",
            "type_key": "running",
            "duration_s": 3600,
            "avg_hr": 170,
            "raw_json": {},
        },
    )
    result = rows(conn, "get_load", start="2026-10-05", end="2026-10-05")
    # пульс покоя 60 (последний непустой), порог 170: IF = 1, TSS = 100
    assert result[0]["tss"] == pytest.approx(100)


def test_load_returns_ctl_atl_by_day_from_start(conn: sqlite3.Connection) -> None:
    heart_rate(conn)
    upsert_activity(
        conn,
        {
            "activity_id": 1,
            "start_time_local": "2026-10-03 07:00:00",
            "type_key": "running",
            "duration_s": 3600,
            "avg_hr": 170,
            "raw_json": {},
        },
    )
    result = rows(conn, "get_load", start="2026-10-03", end="2026-10-05")
    assert [row["date"] for row in result] == ["2026-10-03", "2026-10-04", "2026-10-05"]
    assert result[0]["tss"] == pytest.approx(100)
    assert result[0]["ctl"] == pytest.approx(100 / 42)
    assert result[0]["atl"] == pytest.approx(100 / 7)


def test_goals_on_day_show_goal_created_before_it(conn: sqlite3.Connection) -> None:
    create_goal(conn, "Полумарафон", now="2026-09-01 10:00:00")
    conn.commit()
    assert [g["title"] for g in rows(conn, "get_goals_on", day="2026-09-02")] == ["Полумарафон"]
    assert rows(conn, "get_goals_on", day="2026-08-31") == []


def test_phases_are_listed_by_status(conn: sqlite3.Connection) -> None:
    add_phase(conn, {"name": "База", "status": "proposed"})
    add_phase(conn, {"name": "Пик", "status": "accepted"})
    assert [p["name"] for p in rows(conn, "get_phases", status="accepted")] == ["Пик"]
    assert len(rows(conn, "get_phases")) == 2


def test_plan_actual_is_listed_without_raw_json(conn: sqlite3.Connection) -> None:
    planned = add_planned_workout(
        conn,
        {
            "date": "2026-10-05",
            "sport": "run",
            "name": "Бег",
            "status": "pushed",
            "workout_json": {},
        },
    )
    add_plan_actual(conn, {"date": "2026-10-05", "planned_id": planned, "kind": "skipped"})
    result = rows(conn, "get_plan_actual", start="2026-10-05", end="2026-10-06")
    assert [(row["kind"], row["planned_id"]) for row in result] == [("skipped", planned)]


def test_date_series_keeps_newest_rows(conn: sqlite3.Connection) -> None:
    for day in range(90):
        metrics(conn, (date(2026, 1, 1) + timedelta(days=day)).isoformat())
    result = rows(conn, "get_daily_metrics", start="2026-01-01", end="2026-03-31")
    assert len(result) == MAX_ROWS
    assert result[-1]["date"] == "2026-03-31"


def test_load_ignores_lthr_measured_after_end_of_period(conn: sqlite3.Connection) -> None:
    upsert_daily_metrics(
        conn, {"date": "2026-10-01", "raw_json": {"sleep": {"restingHeartRate": 50}}}
    )
    upsert_threshold(conn, {"calendar_date": "2026-10-08", "lthr": 170, "raw_json": {}})
    with pytest.raises(ToolError, match="LTHR"):
        call(conn, "get_load", start="2026-10-01", end="2026-10-07")
