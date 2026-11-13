import json
import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest
from fake_clock import freeze
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text

from ai_coach.goals.service import accept_phase, propose_phase
from ai_coach.mcp_server import snapshot as snapshot_module
from ai_coach.mcp_server.server import TOOLS
from ai_coach.mcp_server.snapshot import SNAPSHOT_CHARS, SNAPSHOT_MAX_CHARS, SNAPSHOT_ROWS
from ai_coach.mcp_server.tools import MAX_CHARS
from ai_coach.store.garmin_data import upsert_activity, upsert_daily_metrics, upsert_threshold
from ai_coach.store.goals import add_goal, add_phase
from ai_coach.store.journal import add_food, add_sync_log, add_weight
from ai_coach.store.meds import add_med, delete_med
from ai_coach.store.pantry import add_entry
from ai_coach.store.plans import add_plan_actual, add_planned_workout
from ai_coach.store.recipes import add_recipe
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
        "claude",
        "workload_ahead",
        "agenda",
        "overload",
        "sleep",
        "illness",
        "who5",
        "evening_done_today",
        "habits_today",
        "week_review_due",
        "day_part",
        "decisions_pending",
        "decisions_to_check",
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


def overfill(conn: sqlite3.Connection) -> None:
    """Данных больше SNAPSHOT_MAX_CHARS: каждый список упирается в свой лимит."""
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
        add_entry(
            conn,
            {
                "item": f"продукт {number} {big}",
                "qty": 1.0,
                "unit": "g",
                "op": "add",
                "logged_at": f"{DAY} 06:00:00",
            },
        )
        conn.execute(
            "INSERT INTO wellbeing_log (date, score, text, logged_at) VALUES (?, 3, ?, ?)",
            (DAY, big, f"{DAY} 08:00:00"),
        )


def test_snapshot_fits_total_limit(conn: sqlite3.Connection) -> None:
    overfill(conn)
    # обрезка работает по новому лимиту, а не по прежним 20000
    length = len(call_text(conn, "get_morning_snapshot", date=DAY))
    assert MAX_CHARS < length <= SNAPSHOT_MAX_CHARS


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
    sync_at(conn, f"{DAY} 06:00:00")
    sync_at(conn, f"{DAY} 12:00:00")
    overfill(conn)
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert MAX_CHARS < len(json.dumps(snapshot, ensure_ascii=False)) <= SNAPSHOT_MAX_CHARS
    assert snapshot["first_run_today"] is False


# --- Н12: самочувствие за 7 дней ---


def feel_at(conn: sqlite3.Connection, day: str) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, text, logged_at) VALUES (?, 3, NULL, ?)",
        (day, f"{day} 08:00:00"),
    )


def test_snapshot_wellbeing_covers_seven_days_and_excludes_eighth(
    conn: sqlite3.Connection,
) -> None:
    for day in ("2026-09-30", "2026-10-01", DAY):
        feel_at(conn, day)
    found = call(conn, "get_morning_snapshot", date=DAY)["wellbeing"]["rows"]
    assert [r["date"] for r in found] == ["2026-10-01", DAY]


def test_wellbeing_tool_keeps_entry_cut_from_snapshot(conn: sqlite3.Connection) -> None:
    feel_at(conn, "2026-09-30")
    found = call(conn, "get_wellbeing", start="2026-09-30", end=DAY)["rows"]
    assert [r["date"] for r in found] == ["2026-09-30"]


def test_snapshot_description_names_seven_days_and_limit() -> None:
    text = TOOLS["get_morning_snapshot"][1]
    assert "самочувствие за 7 дней" in text
    assert "32768 символов" in text


def test_snapshot_description_names_day_part_and_evening() -> None:
    text = TOOLS["get_morning_snapshot"][1]
    assert "day_part" in text
    assert "evening" in text
    assert "вернусь утром" in text
    assert "coach-decisions.md" in text


def test_snapshot_description_names_decision_keys() -> None:
    text = TOOLS["get_morning_snapshot"][1]
    assert "decisions_pending" in text
    assert "decisions_to_check" in text


@pytest.mark.parametrize(
    ("clock", "part"), [("09:00:00", "morning"), ("14:00:00", "day"), ("21:00:00", "evening")]
)
def test_snapshot_day_part_for_today(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch, clock: str, part: str
) -> None:
    freeze(monkeypatch, f"{DAY} {clock}")
    assert call(conn, "get_morning_snapshot", date=DAY)["day_part"] == part


def test_snapshot_day_part_is_none_for_past_date(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, f"{day_shift(1)} 09:00:00")
    assert call(conn, "get_morning_snapshot", date=DAY)["day_part"] is None


def test_snapshot_with_day_part_is_cut_without_error(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    overfill(conn)
    freeze(monkeypatch, f"{DAY} 09:00:00")
    text = call_text(conn, "get_morning_snapshot", date=DAY)
    assert len(text) <= SNAPSHOT_MAX_CHARS
    assert json.loads(text)["day_part"] == "morning"


# --- Н24: выжившие мутанты сводки (окна, порядок обрезки, лимиты) ---


def day_shift(days: int) -> str:
    return (date.fromisoformat(DAY) + timedelta(days=days)).isoformat()


def extra_actual(conn: sqlite3.Connection, activity_id: int, day: str) -> None:
    upsert_activity(
        conn,
        {
            "activity_id": activity_id,
            "start_time_local": "2026-01-01 07:00:00",
            "type_key": "running",
            "raw_json": {},
        },
    )
    add_plan_actual(
        conn, {"date": day, "activity_id": activity_id, "kind": "extra", "details_json": {}}
    )


def test_snapshot_load_error_tells_to_run_sync_on_empty_base(conn: sqlite3.Connection) -> None:
    assert "coach sync" in call(conn, "get_morning_snapshot", date=DAY)["load_error"]


def test_snapshot_deviations_use_load_of_the_day(conn: sqlite3.Connection) -> None:
    fill(conn)
    upsert_activity(
        conn,
        {
            "activity_id": 2,
            "start_time_local": f"{DAY} 07:00:00",
            "type_key": "running",
            "name": "Длинный бег",
            "duration_s": 10800,
            "avg_hr": 170,
            "raw_json": {},
        },
    )
    kinds = [r["kind"] for r in call(conn, "get_morning_snapshot", date=DAY)["deviations"]["rows"]]
    assert "atl_over_ctl" in kinds


def test_snapshot_goals_keep_first_rows_when_cut(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_ROWS + 5):
        add_goal(conn, {"title": f"Цель {number}", "status": "active"})
    found = call(conn, "get_morning_snapshot", date=DAY)["goals"]["rows"]
    assert (len(found), found[0]["title"]) == (SNAPSHOT_ROWS, "Цель 0")


def test_snapshot_metrics_keep_newest_when_cut_by_chars(conn: sqlite3.Connection) -> None:
    for back in range(8):
        upsert_daily_metrics(
            conn, {"date": day_shift(-back), "readiness_level": "я" * 600, "raw_json": {}}
        )
    found = call(conn, "get_morning_snapshot", date=DAY)["metrics"]
    assert found["truncated"] is True
    assert found["rows"][-1]["date"] == DAY


def test_snapshot_metrics_window_is_seven_days_back(conn: sqlite3.Connection) -> None:
    for back in (8, 7, 0):
        upsert_daily_metrics(conn, {"date": day_shift(-back), "raw_json": {}})
    found = call(conn, "get_morning_snapshot", date=DAY)["metrics"]["rows"]
    assert [r["date"] for r in found] == [day_shift(-7), DAY]


def test_snapshot_activities_keep_newest_when_cut(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_ROWS + 5):
        upsert_activity(
            conn,
            {
                "activity_id": number + 1,
                "start_time_local": f"{DAY} 07:{number:02d}:00",
                "type_key": "running",
                "name": f"Бег {number}",
                "raw_json": {},
            },
        )
    found = call(conn, "get_morning_snapshot", date=DAY)["activities"]["rows"]
    assert found[-1]["name"] == f"Бег {SNAPSHOT_ROWS + 4}"


def test_snapshot_activities_window_is_seven_days_back(conn: sqlite3.Connection) -> None:
    for number, back in enumerate((8, 7, 0)):
        upsert_activity(
            conn,
            {
                "activity_id": number + 1,
                "start_time_local": f"{day_shift(-back)} 07:00:00",
                "type_key": "running",
                "raw_json": {},
            },
        )
    found = call(conn, "get_morning_snapshot", date=DAY)["activities"]["rows"]
    assert [r["start_time_local"][:10] for r in found] == [day_shift(-7), DAY]


def test_snapshot_phases_proposed_has_only_proposed(conn: sqlite3.Connection) -> None:
    propose_phase(conn, "Новая", now="2026-10-01T10:00:00")
    taken = propose_phase(conn, "Принятая", now="2026-10-01T10:00:00")
    accept_phase(conn, taken, now="2026-10-02T10:00:00")
    found = call(conn, "get_morning_snapshot", date=DAY)["phases_proposed"]["rows"]
    assert [r["name"] for r in found] == ["Новая"]


def test_snapshot_phases_now_has_phases_of_the_day(conn: sqlite3.Connection) -> None:
    propose_phase(conn, "Фаза", now="2026-10-01T10:00:00")
    found = call(conn, "get_morning_snapshot", date=DAY)["phases_now"]["rows"]
    assert [r["name"] for r in found] == ["Фаза"]


def test_snapshot_plan_covers_today_and_six_days_ahead(conn: sqlite3.Connection) -> None:
    for ahead in (-1, 0, 6, 7):
        add_planned_workout(
            conn,
            {"date": day_shift(ahead), "sport": "run", "name": "Бег", "workout_json": {}},
        )
    found = call(conn, "get_morning_snapshot", date=DAY)["plan"]["rows"]
    assert [r["date"] for r in found] == [DAY, day_shift(6)]


def test_snapshot_plan_actual_window_is_seven_days_back_to_today(
    conn: sqlite3.Connection,
) -> None:
    for number, back in enumerate((8, 7, 0, -1)):
        extra_actual(conn, number + 1, day_shift(-back))
    found = call(conn, "get_morning_snapshot", date=DAY)["plan_actual"]["rows"]
    assert [r["date"] for r in found] == [day_shift(-7), DAY]


def test_snapshot_plan_actual_keeps_newest_when_cut(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_ROWS + 5):
        extra_actual(conn, number + 1, DAY)
    found = call(conn, "get_morning_snapshot", date=DAY)["plan_actual"]["rows"]
    assert found[-1]["id"] == SNAPSHOT_ROWS + 5


def test_snapshot_weights_window_is_fourteen_days_back(conn: sqlite3.Connection) -> None:
    for back in (15, 14, 0):
        add_weight(conn, {"measured_at": f"{day_shift(-back)} 07:00:00", "weight_kg": 80})
    found = call(conn, "get_morning_snapshot", date=DAY)["weights"]["rows"]
    assert [r["measured_at"][:10] for r in found] == [day_shift(-14), DAY]


def test_snapshot_weights_keep_newest_when_cut(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_ROWS + 5):
        add_weight(conn, {"measured_at": f"{DAY} 07:{number:02d}:00", "weight_kg": 80 + number})
    found = call(conn, "get_morning_snapshot", date=DAY)["weights"]["rows"]
    assert found[-1]["weight_kg"] == 80 + SNAPSHOT_ROWS + 4


def test_snapshot_food_today_keeps_newest_when_cut(conn: sqlite3.Connection) -> None:
    for number in range(SNAPSHOT_ROWS + 5):
        add_food(conn, {"logged_at": f"{DAY} 09:{number:02d}:00", "text": f"еда {number}"})
    found = call(conn, "get_morning_snapshot", date=DAY)["food_today"]["rows"]
    assert found[-1]["text"] == f"еда {SNAPSHOT_ROWS + 4}"


def test_snapshot_wellbeing_keeps_newest_when_cut(conn: sqlite3.Connection) -> None:
    for number in range(65):
        conn.execute(
            "INSERT INTO wellbeing_log (date, score, text, logged_at) VALUES (?, 3, ?, ?)",
            (DAY, f"м{number}", f"{DAY} {number // 60:02d}:{number % 60:02d}:00"),
        )
    found = call(conn, "get_morning_snapshot", date=DAY)["wellbeing"]
    assert found["truncated"] is True
    assert found["rows"][-1]["text"] == "м64"


def test_snapshot_workload_ahead_starts_tomorrow(conn: sqlite3.Connection) -> None:
    found = call(conn, "get_morning_snapshot", date=DAY)["workload_ahead"]["rows"]
    assert found[0]["date"] == day_shift(1)


def test_snapshot_sleep_has_awake_hours_for_today(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    millis = int(datetime.fromisoformat(f"{DAY} 07:10:00").replace(tzinfo=UTC).timestamp() * 1000)
    upsert_daily_metrics(
        conn,
        {
            "date": DAY,
            "sleep_seconds": 6 * 3600,
            "raw_json": {"sleep": {"dailySleepDTO": {"sleepEndTimestampLocal": millis}}},
        },
    )
    freeze(monkeypatch, f"{DAY} 11:00:00")
    assert call(conn, "get_morning_snapshot", date=DAY)["sleep"]["awake_h"] == 3.8


@pytest.mark.parametrize("name", ["pantry", "pantry_expiring", "recipes"])
def test_snapshot_short_lists_are_limited_by_chars(conn: sqlite3.Connection, name: str) -> None:
    big = "я" * 300
    for number in range(20):
        add_entry(
            conn,
            {
                "item": f"продукт {number} {big}",
                "qty": 1.0,
                "unit": "g",
                "op": "add",
                "expires_on": DAY,
                "logged_at": f"{DAY} 06:00:00",
            },
        )
        add_recipe(
            conn,
            {
                "name": f"рецепт {number} {big}",
                "kcal_100": 1,
                "protein_100": 1,
                "fat_100": 1,
                "carbs_100": 1,
                "created_at": f"{DAY} 06:00:00",
            },
            [],
        )
    found = call(conn, "get_morning_snapshot", date=DAY)[name]
    assert 0 < len(json.dumps(found["rows"], ensure_ascii=False)) <= SNAPSHOT_CHARS


def total_limit(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    """Общий лимит на один символ меньше, чем весь ответ: срезается ровно один ряд."""
    full = len(
        json.dumps(snapshot_module.morning_snapshot(conn, DAY), ensure_ascii=False, default=str)
    )
    monkeypatch.setattr(snapshot_module, "SNAPSHOT_MAX_CHARS", full - 1)


def test_snapshot_exactly_at_total_limit_is_not_cut(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    full = json.dumps(snapshot_module.morning_snapshot(conn, DAY), ensure_ascii=False, default=str)
    monkeypatch.setattr(snapshot_module, "SNAPSHOT_MAX_CHARS", len(full))
    cut = snapshot_module.morning_snapshot(conn, DAY)
    assert json.dumps(cut, ensure_ascii=False, default=str) == full
    assert cut["workload"]["truncated"] is False


def test_snapshot_cut_takes_longest_list_and_drops_oldest_of_date_series(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    # на пустой базе самый длинный список — workload (ряды по датам), следом workload_ahead
    total_limit(conn, monkeypatch)
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert [r["date"] for r in snapshot["workload"]["rows"]] == [
        day_shift(-n) for n in range(5, -1, -1)
    ]
    assert snapshot["workload"]["truncated"] is True
    assert (len(snapshot["workload_ahead"]["rows"]), snapshot["workload_ahead"]["truncated"]) == (
        7,
        False,
    )


def test_snapshot_cut_drops_last_row_of_other_lists(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snapshot_module, "SNAPSHOT_CHARS", 20000)  # цели длиннее workload
    for number in range(15):
        add_goal(conn, {"title": f"цель {number:02d} " + "я" * 300, "status": "active"})
    total_limit(conn, monkeypatch)
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert [r["title"][:7] for r in snapshot["goals"]["rows"]] == [
        f"цель {n:02d}" for n in range(14)
    ]
    assert snapshot["goals"]["truncated"] is True
    assert len(snapshot["workload"]["rows"]) == 7


def test_snapshot_that_cannot_be_cut_enough_raises(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_goal(conn, {"title": "Цель", "status": "active"})
    monkeypatch.setattr(snapshot_module, "SNAPSHOT_MAX_CHARS", 10)
    with pytest.raises(ToolError, match=r"Снапшот не помещается в лимит даже без списков\.$"):
        call(conn, "get_morning_snapshot", date=DAY)
