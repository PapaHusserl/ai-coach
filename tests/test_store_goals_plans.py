import json
import sqlite3
from datetime import datetime

import pytest

from ai_coach.store.garmin_data import upsert_activity
from ai_coach.store.goals import (
    add_goal,
    add_goal_event,
    add_phase,
    get_goal,
    get_phase,
    list_goal_events,
    list_goals,
    list_phases,
    update_goal,
    update_phase,
)
from ai_coach.store.plans import (
    add_plan_actual,
    add_planned_workout,
    delete_plan_actual,
    get_planned_workout,
    list_plan_actual,
    list_planned_workouts,
    update_planned_workout,
)


def workout(date: str, name: str = "w") -> dict:
    return {"date": date, "sport": "run", "name": name, "workout_json": {"steps": []}}


def test_goal_defaults(conn: sqlite3.Connection) -> None:
    goal_id = add_goal(conn, {"title": "Марафон"})
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["title"] == "Марафон"
    assert goal["status"] == "active"
    assert goal["priority"] == 0
    assert goal["created_at"]


def test_goal_missing_is_none(conn: sqlite3.Connection) -> None:
    assert get_goal(conn, 1) is None


def test_goal_update_changes_only_given_fields(conn: sqlite3.Connection) -> None:
    goal_id = add_goal(conn, {"title": "Марафон", "target": "3:30"})
    update_goal(conn, goal_id, {"status": "done"})
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["status"] == "done"
    assert goal["title"] == "Марафон"
    assert goal["target"] == "3:30"


def test_list_goals_ordered_by_id(conn: sqlite3.Connection) -> None:
    ids = [add_goal(conn, {"title": t}) for t in ("a", "b", "c")]
    assert [g["id"] for g in list_goals(conn)] == ids


def test_goal_event_stores_json_payload(conn: sqlite3.Connection) -> None:
    goal_id = add_goal(conn, {"title": "g"})
    add_goal_event(
        conn,
        {
            "goal_id": goal_id,
            "event_type": "updated",
            "occurred_at": "2026-03-10T10:00:00",
            "payload_json": {"target": "3:20"},
        },
    )
    events = list_goal_events(conn, goal_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "updated"
    assert json.loads(events[0]["payload_json"]) == {"target": "3:20"}


def test_goal_event_requires_existing_goal(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_goal_event(conn, {"goal_id": 99, "event_type": "created", "occurred_at": "2026-03-10"})


def test_goal_events_sorted_by_time_then_id_and_filtered(conn: sqlite3.Connection) -> None:
    g1 = add_goal(conn, {"title": "g1"})
    g2 = add_goal(conn, {"title": "g2"})
    e_late = add_goal_event(conn, {"goal_id": g1, "event_type": "x", "occurred_at": "2026-03-12"})
    e_early = add_goal_event(conn, {"goal_id": g1, "event_type": "x", "occurred_at": "2026-03-10"})
    e_other = add_goal_event(conn, {"goal_id": g2, "event_type": "x", "occurred_at": "2026-03-11"})
    e_tie = add_goal_event(conn, {"goal_id": g1, "event_type": "x", "occurred_at": "2026-03-10"})
    assert [e["id"] for e in list_goal_events(conn, g1)] == [e_early, e_tie, e_late]
    assert [e["id"] for e in list_goal_events(conn)] == [e_early, e_tie, e_other, e_late]
    assert list_goal_events(conn, 12345) == []


def test_phase_default_status_is_proposed(conn: sqlite3.Connection) -> None:
    phase_id = add_phase(conn, {"name": "База"})
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "proposed"
    assert phase["accepted_at"] is None


def test_phase_missing_is_none(conn: sqlite3.Connection) -> None:
    assert get_phase(conn, 1) is None


def test_phase_accept(conn: sqlite3.Connection) -> None:
    phase_id = add_phase(conn, {"name": "База"})
    update_phase(conn, phase_id, {"status": "accepted", "accepted_at": "2026-03-10"})
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "accepted"
    assert phase["accepted_at"] == "2026-03-10"


def test_phase_rejects_unknown_status(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_phase(conn, {"name": "База", "status": "weird"})


def test_list_phases_filter_by_status(conn: sqlite3.Connection) -> None:
    p1 = add_phase(conn, {"name": "a"})
    p2 = add_phase(conn, {"name": "b", "status": "accepted"})
    assert [p["id"] for p in list_phases(conn)] == [p1, p2]
    assert [p["id"] for p in list_phases(conn, "accepted")] == [p2]
    assert [p["id"] for p in list_phases(conn, status="proposed")] == [p1]


def test_planned_workout_defaults_and_json(conn: sqlite3.Connection) -> None:
    wid = add_planned_workout(conn, workout("2026-03-10", "Интервалы"))
    row = get_planned_workout(conn, wid)
    assert row is not None
    assert row["status"] == "draft"
    assert row["name"] == "Интервалы"
    assert row["garmin_workout_id"] is None
    assert row["pushed_at"] is None
    assert json.loads(row["workout_json"]) == {"steps": []}


def test_planned_workout_missing_is_none(conn: sqlite3.Connection) -> None:
    assert get_planned_workout(conn, 1) is None


def test_planned_workout_status_flow(conn: sqlite3.Connection) -> None:
    wid = add_planned_workout(conn, workout("2026-03-10"))
    update_planned_workout(conn, wid, {"status": "approved"})
    update_planned_workout(
        conn,
        wid,
        {"status": "pushed", "garmin_workout_id": 11, "garmin_schedule_id": 22, "pushed_at": "t"},
    )
    row = get_planned_workout(conn, wid)
    assert row is not None
    assert row["status"] == "pushed"
    assert row["garmin_workout_id"] == 11
    assert row["garmin_schedule_id"] == 22
    assert row["pushed_at"] == "t"
    assert row["name"] == "w"


def test_planned_workout_rejects_unknown_status(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_planned_workout(conn, workout("2026-03-10") | {"status": "sent"})


def test_list_planned_workouts_inclusive_sorted(conn: sqlite3.Connection) -> None:
    w3 = add_planned_workout(conn, workout("2026-03-12"))
    w1 = add_planned_workout(conn, workout("2026-03-10"))
    w2 = add_planned_workout(conn, workout("2026-03-10"))
    add_planned_workout(conn, workout("2026-03-09"))
    add_planned_workout(conn, workout("2026-03-13"))
    rows = list_planned_workouts(conn, "2026-03-10", "2026-03-12")
    assert [r["id"] for r in rows] == [w1, w2, w3]


def test_plan_actual_roundtrip(conn: sqlite3.Connection) -> None:
    wid = add_planned_workout(conn, workout("2026-03-10"))
    upsert_activity(
        conn,
        {
            "activity_id": 5,
            "start_time_local": "2026-03-10 07:00:00",
            "type_key": "running",
            "raw_json": {},
        },
    )
    add_plan_actual(
        conn,
        {
            "date": "2026-03-10",
            "kind": "done",
            "planned_id": wid,
            "activity_id": 5,
            "details_json": {"match": "date+type"},
        },
    )
    rows = list_plan_actual(conn, "2026-03-10", "2026-03-10")
    assert len(rows) == 1
    assert rows[0]["kind"] == "done"
    assert rows[0]["planned_id"] == wid
    assert rows[0]["activity_id"] == 5
    assert json.loads(rows[0]["details_json"]) == {"match": "date+type"}


def seed_plan_and_activity(conn: sqlite3.Connection) -> tuple[int, int]:
    wid = add_planned_workout(conn, workout("2026-03-10"))
    upsert_activity(
        conn,
        {
            "activity_id": 5,
            "start_time_local": "2026-03-10 07:00:00",
            "type_key": "running",
            "raw_json": {},
        },
    )
    return wid, 5


def links(kind: str, wid: int, aid: int) -> dict:
    planned = {"done": True, "different": True, "skipped": True, "extra": False}[kind]
    actual = {"done": True, "different": True, "skipped": False, "extra": True}[kind]
    return {
        "date": "2026-03-10",
        "kind": kind,
        "planned_id": wid if planned else None,
        "activity_id": aid if actual else None,
    }


@pytest.mark.parametrize("kind", ["done", "skipped", "extra", "different"])
def test_plan_actual_accepts_valid_links_for_kind(conn: sqlite3.Connection, kind: str) -> None:
    wid, aid = seed_plan_and_activity(conn)
    add_plan_actual(conn, links(kind, wid, aid))
    row = list_plan_actual(conn, "2026-03-10", "2026-03-10")[0]
    assert row["kind"] == kind
    assert row["planned_id"] == (None if kind == "extra" else wid)
    assert row["activity_id"] == (None if kind == "skipped" else aid)


@pytest.mark.parametrize("kind", ["done", "different"])
def test_plan_actual_done_and_different_need_both_links(
    conn: sqlite3.Connection, kind: str
) -> None:
    wid, aid = seed_plan_and_activity(conn)
    for bad in (
        {"planned_id": wid},
        {"activity_id": aid},
        {},
    ):
        with pytest.raises(sqlite3.IntegrityError):
            add_plan_actual(conn, {"date": "2026-03-10", "kind": kind, **bad})


def test_plan_actual_skipped_needs_only_planned_id(conn: sqlite3.Connection) -> None:
    wid, aid = seed_plan_and_activity(conn)
    for bad in ({}, {"activity_id": aid}, {"planned_id": wid, "activity_id": aid}):
        with pytest.raises(sqlite3.IntegrityError):
            add_plan_actual(conn, {"date": "2026-03-10", "kind": "skipped", **bad})


def test_plan_actual_extra_needs_only_activity_id(conn: sqlite3.Connection) -> None:
    wid, aid = seed_plan_and_activity(conn)
    for bad in ({}, {"planned_id": wid}, {"planned_id": wid, "activity_id": aid}):
        with pytest.raises(sqlite3.IntegrityError):
            add_plan_actual(conn, {"date": "2026-03-10", "kind": "extra", **bad})


def test_plan_actual_rejects_unknown_kind(conn: sqlite3.Connection) -> None:
    wid, aid = seed_plan_and_activity(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_plan_actual(conn, links("done", wid, aid) | {"kind": "bogus"})


def test_plan_actual_requires_existing_planned_workout(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_plan_actual(conn, {"date": "2026-03-10", "kind": "skipped", "planned_id": 99})


def test_plan_actual_requires_existing_activity(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_plan_actual(conn, {"date": "2026-03-10", "kind": "extra", "activity_id": 99})


def test_list_plan_actual_inclusive_sorted(conn: sqlite3.Connection) -> None:
    _, aid = seed_plan_and_activity(conn)
    ids = {
        d: add_plan_actual(conn, {"date": d, "kind": "extra", "activity_id": aid})
        for d in ("2026-03-11", "2026-03-09", "2026-03-10", "2026-03-12")
    }
    rows = list_plan_actual(conn, "2026-03-10", "2026-03-11")
    assert [r["id"] for r in rows] == [ids["2026-03-10"], ids["2026-03-11"]]


def test_delete_plan_actual_removes_only_period(conn: sqlite3.Connection) -> None:
    _, aid = seed_plan_and_activity(conn)
    for day in ("2026-03-09", "2026-03-10", "2026-03-11", "2026-03-12"):
        add_plan_actual(conn, {"date": day, "kind": "extra", "activity_id": aid})
    delete_plan_actual(conn, "2026-03-10", "2026-03-11")
    rows = list_plan_actual(conn, "2026-03-01", "2026-03-31")
    assert [r["date"] for r in rows] == ["2026-03-09", "2026-03-12"]


@pytest.mark.parametrize("sport", ["strength", "mobility", "run", "bike", "swim"])
def test_planned_workout_accepts_known_sports(conn: sqlite3.Connection, sport: str) -> None:
    wid = add_planned_workout(conn, workout("2026-03-10") | {"sport": sport})
    row = get_planned_workout(conn, wid)
    assert row is not None
    assert row["sport"] == sport


@pytest.mark.parametrize("sport", ["running", "yoga", "RUN", ""])
def test_planned_workout_rejects_unknown_sport(conn: sqlite3.Connection, sport: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_planned_workout(conn, workout("2026-03-10") | {"sport": sport})


def test_planned_workout_update_rejects_unknown_sport(conn: sqlite3.Connection) -> None:
    wid = add_planned_workout(conn, workout("2026-03-10"))
    with pytest.raises(sqlite3.IntegrityError):
        update_planned_workout(conn, wid, {"sport": "yoga"})


def test_planned_workout_can_be_cancelled(conn: sqlite3.Connection) -> None:
    wid = add_planned_workout(conn, workout("2026-03-10"))
    update_planned_workout(conn, wid, {"status": "cancelled"})
    row = get_planned_workout(conn, wid)
    assert row is not None
    assert row["status"] == "cancelled"


@pytest.mark.parametrize("status", ["draft", "approved", "pushed", "cancelled"])
def test_planned_workout_accepts_all_statuses(conn: sqlite3.Connection, status: str) -> None:
    wid = add_planned_workout(conn, workout("2026-03-10") | {"status": status})
    row = get_planned_workout(conn, wid)
    assert row is not None
    assert row["status"] == status


def parse_db_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def test_default_timestamps_use_local_time(conn: sqlite3.Connection) -> None:
    before = datetime.now().replace(microsecond=0)
    goal = get_goal(conn, add_goal(conn, {"title": "g"}))
    phase = get_phase(conn, add_phase(conn, {"name": "p"}))
    wid = add_planned_workout(conn, workout("2026-03-10"))
    planned = get_planned_workout(conn, wid)
    _, aid = seed_plan_and_activity(conn)
    pa_id = add_plan_actual(conn, {"date": "2026-03-10", "kind": "extra", "activity_id": aid})
    actual = list_plan_actual(conn, "2026-03-10", "2026-03-10")[0]
    assert goal is not None
    assert phase is not None
    assert planned is not None
    assert actual["id"] == pa_id
    stamps = [
        goal["created_at"],
        goal["updated_at"],
        phase["created_at"],
        planned["created_at"],
        actual["created_at"],
    ]
    for stamp in stamps:
        assert abs((parse_db_time(stamp) - before).total_seconds()) <= 5
