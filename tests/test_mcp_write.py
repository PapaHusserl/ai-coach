import contextlib
import json
import sqlite3
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call

from ai_coach.store.goals import add_goal, list_phase_events, list_phase_goal_ids, list_phases
from ai_coach.store.plans import list_planned_workouts

RUN = {
    "date": "2026-10-08",
    "sport": "run",
    "name": "Бег 5 км",
    "spec": {"steps": [{"type": "interval", "meters": 5000}]},
}
STRENGTH = {
    "date": "2026-10-09",
    "sport": "strength",
    "name": "Силовая",
    "spec": {
        "exercises": [
            {
                "category": "BENCH_PRESS",
                "exercise": "BARBELL_BENCH_PRESS",
                "sets": 3,
                "reps": 8,
                "rest_seconds": 90,
                "weight_kg": 40,
            }
        ]
    },
}


def saved(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return list_planned_workouts(conn, "2026-01-01", "2026-12-31")


def test_workout_is_saved_as_draft(conn: sqlite3.Connection) -> None:
    result = call(conn, "create_draft_workout", **RUN)
    rows = saved(conn)
    assert [(r["name"], r["sport"], r["status"]) for r in rows] == [("Бег 5 км", "run", "draft")]
    assert result["draft_id"] == rows[0]["id"]


def test_strength_workout_is_saved_as_draft(conn: sqlite3.Connection) -> None:
    call(conn, "create_draft_workout", **STRENGTH)
    assert [(r["sport"], r["status"]) for r in saved(conn)] == [("strength", "draft")]


def plank_args(**timing: Any) -> dict[str, Any]:
    item = {**STRENGTH["spec"]["exercises"][0], "category": "PLANK", "exercise": "PLANK"}
    del item["reps"]
    return {**STRENGTH, "spec": {"exercises": [item | timing]}}


def test_strength_seconds_workout_is_saved_with_seconds(conn: sqlite3.Connection) -> None:
    call(conn, "create_draft_workout", **plank_args(seconds=60))
    rows = saved(conn)
    assert [r["status"] for r in rows] == ["draft"]
    assert json.loads(rows[0]["workout_json"])["exercises"][0]["seconds"] == 60


def test_strength_with_reps_and_seconds_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "create_draft_workout", **plank_args(reps=8, seconds=60))
    assert saved(conn) == []


def test_strength_without_reps_and_seconds_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "create_draft_workout", **plank_args())
    assert saved(conn) == []


def test_draft_keeps_spec_with_name(conn: sqlite3.Connection) -> None:
    call(conn, "create_draft_workout", **RUN)
    spec = json.loads(saved(conn)[0]["workout_json"])
    assert spec["name"] == "Бег 5 км"
    assert spec["steps"] == RUN["spec"]["steps"]


def test_draft_does_not_touch_garmin_fields(conn: sqlite3.Connection) -> None:
    call(conn, "create_draft_workout", **RUN)
    row = saved(conn)[0]
    assert row["garmin_workout_id"] is None
    assert row["garmin_schedule_id"] is None
    assert row["pushed_at"] is None


def test_draft_cannot_get_other_status(conn: sqlite3.Connection) -> None:
    with contextlib.suppress(ToolError):
        call(conn, "create_draft_workout", **RUN, status="pushed")
    assert {row["status"] for row in saved(conn)} <= {"draft"}


def test_draft_with_unknown_sport_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "create_draft_workout", **{**RUN, "sport": "yoga"})
    assert saved(conn) == []


def test_draft_with_bad_date_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "create_draft_workout", **{**RUN, "date": "в среду"})
    assert saved(conn) == []


def test_draft_with_broken_spec_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "create_draft_workout", **{**RUN, "spec": {}})
    assert saved(conn) == []


def test_phase_is_saved_as_proposal_with_goals(conn: sqlite3.Connection) -> None:
    goal_id = add_goal(conn, {"title": "Полумарафон", "status": "active"})
    conn.commit()
    result = call(
        conn,
        "propose_phase",
        name="База",
        description="Аэробный объём",
        start_date="2026-10-12",
        end_date="2026-11-08",
        goal_ids=[goal_id],
    )
    phases = list_phases(conn)
    assert [(p["name"], p["status"]) for p in phases] == [("База", "proposed")]
    assert result["phase_id"] == phases[0]["id"]
    assert list_phase_goal_ids(conn, phases[0]["id"]) == [goal_id]
    assert [e["event_type"] for e in list_phase_events(conn)] == ["proposed"]


def test_phase_needs_only_name(conn: sqlite3.Connection) -> None:
    call(conn, "propose_phase", name="Отдых")
    assert [p["status"] for p in list_phases(conn)] == ["proposed"]


def test_phase_with_unknown_goal_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "propose_phase", name="База", goal_ids=[999])
    assert list_phases(conn) == []


def test_phase_ending_before_start_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "propose_phase", name="База", start_date="2026-11-08", end_date="2026-10-12")
    assert list_phases(conn) == []


def test_phase_cannot_get_accepted_status(conn: sqlite3.Connection) -> None:
    with contextlib.suppress(ToolError):
        call(conn, "propose_phase", name="База", status="accepted")
    assert list_phases(conn, "accepted") == []


def test_draft_can_be_cancelled(conn: sqlite3.Connection) -> None:
    draft_id = call(conn, "create_draft_workout", **RUN)["draft_id"]
    result = call(conn, "cancel_draft_workout", workout_id=draft_id)
    assert result == {"cancelled_id": draft_id}
    assert [row["status"] for row in saved(conn)] == ["cancelled"]


@pytest.mark.parametrize("status", ["approved", "pushed", "cancelled"])
def test_only_draft_can_be_cancelled(conn: sqlite3.Connection, status: str) -> None:
    draft_id = call(conn, "create_draft_workout", **RUN)["draft_id"]
    conn.execute("UPDATE planned_workouts SET status = ? WHERE id = ?", (status, draft_id))
    with pytest.raises(ToolError):
        call(conn, "cancel_draft_workout", workout_id=draft_id)
    assert [row["status"] for row in saved(conn)] == [status]


def test_cancelling_unknown_workout_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "cancel_draft_workout", workout_id=999)
