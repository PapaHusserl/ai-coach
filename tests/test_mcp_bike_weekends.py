import contextlib
import sqlite3

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call

from ai_coach.store.plans import list_planned_workouts

STEPS = {"steps": [{"type": "interval", "meters": 20000}]}
FRIDAY = "2026-10-09"
SATURDAY = "2026-10-10"
SUNDAY = "2026-10-11"
MONDAY = "2026-10-12"


def bike(day: str) -> dict[str, object]:
    return {"date": day, "sport": "bike", "name": "Вело", "spec": STEPS}


def saved(conn: sqlite3.Connection) -> list[dict[str, object]]:
    return list_planned_workouts(conn, "2026-01-01", "2026-12-31")


@pytest.mark.parametrize("day", [SATURDAY, SUNDAY])
def test_bike_on_weekend_is_saved_as_draft(conn: sqlite3.Connection, day: str) -> None:
    call(conn, "create_draft_workout", **bike(day))
    assert [(r["date"], r["sport"], r["status"]) for r in saved(conn)] == [(day, "bike", "draft")]


@pytest.mark.parametrize("day", ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", FRIDAY])
def test_bike_on_weekday_is_rejected_and_not_saved(conn: sqlite3.Connection, day: str) -> None:
    with pytest.raises(ToolError):
        call(conn, "create_draft_workout", **bike(day))
    assert saved(conn) == []


def test_bike_on_monday_after_weekend_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "create_draft_workout", **bike(MONDAY))


def test_rejection_message_names_the_rule(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError) as error:
        call(conn, "create_draft_workout", **bike(FRIDAY))
    assert "вело" in str(error.value).lower()


@pytest.mark.parametrize("sport", ["run", "swim"])
@pytest.mark.parametrize("day", [FRIDAY, SATURDAY, MONDAY])
def test_other_sports_are_allowed_any_day(conn: sqlite3.Connection, sport: str, day: str) -> None:
    call(conn, "create_draft_workout", date=day, sport=sport, name="Тренировка", spec=STEPS)
    assert [r["sport"] for r in saved(conn)] == [sport]


def test_strength_is_allowed_on_weekday(conn: sqlite3.Connection) -> None:
    spec = {
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
    }
    call(conn, "create_draft_workout", date=FRIDAY, sport="strength", name="Силовая", spec=spec)
    assert [r["sport"] for r in saved(conn)] == ["strength"]


def test_weekday_bike_does_not_block_following_valid_draft(conn: sqlite3.Connection) -> None:
    with contextlib.suppress(ToolError):
        call(conn, "create_draft_workout", **bike(FRIDAY))
    call(conn, "create_draft_workout", **bike(SATURDAY))
    assert [r["date"] for r in saved(conn)] == [SATURDAY]
