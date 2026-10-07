import sqlite3

from mcp_fakes import call, rows

from ai_coach.store.meds import add_med
from ai_coach.store.plans import add_planned_workout

DAY = "2026-10-08"
NOW = "2026-10-08 10:00:00"


def new_med(conn: sqlite3.Connection, name: str, schedule: str) -> int:
    return add_med(
        conn,
        {
            "name": name,
            "kind": "vitamin",
            "dose": 1.0,
            "unit": "g",
            "schedule": schedule,
            "start_date": "2026-10-01",
            "created_at": NOW,
            "updated_at": NOW,
        },
    )


def new_workout(conn: sqlite3.Connection, status: str = "approved") -> int:
    row = {"date": DAY, "sport": "run", "name": "т", "workout_json": {}, "status": status}
    return add_planned_workout(conn, row)


def names(items: list[dict]) -> list[str]:
    return sorted(r["name"] for r in items)


def snapshot(conn: sqlite3.Connection) -> dict:
    return call(conn, "get_morning_snapshot", date=DAY)


# --- get_meds ---


def test_get_with_date_hides_training_course_without_training(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли", "daily")
    new_med(conn, "после", "after")
    assert names(rows(conn, "get_meds", date=DAY)) == ["дейли"]


def test_get_with_date_shows_training_course_with_training(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли", "daily")
    new_med(conn, "после", "after")
    new_workout(conn)
    assert names(rows(conn, "get_meds", date=DAY)) == ["дейли", "после"]


def test_get_with_date_hides_training_course_with_only_cancelled(
    conn: sqlite3.Connection,
) -> None:
    new_med(conn, "после", "after")
    new_workout(conn, "cancelled")
    assert rows(conn, "get_meds", date=DAY) == []


def test_get_without_date_returns_training_courses(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли", "daily")
    new_med(conn, "после", "after")
    assert names(rows(conn, "get_meds")) == ["дейли", "после"]


# --- snapshot ---


def test_snapshot_without_key_when_only_training_courses_and_no_training(
    conn: sqlite3.Connection,
) -> None:
    new_med(conn, "после", "after")
    new_med(conn, "до", "before")
    assert "meds_today" not in snapshot(conn)


def test_snapshot_without_key_when_only_cancelled_workout(conn: sqlite3.Connection) -> None:
    new_med(conn, "после", "training_day")
    new_workout(conn, "cancelled")
    assert "meds_today" not in snapshot(conn)


def test_snapshot_has_training_course_with_training(conn: sqlite3.Connection) -> None:
    new_med(conn, "после", "after")
    new_workout(conn)
    assert names(snapshot(conn)["meds_today"]["rows"]) == ["после"]


def test_snapshot_keeps_daily_course_without_training(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли", "daily")
    new_med(conn, "после", "after")
    assert names(snapshot(conn)["meds_today"]["rows"]) == ["дейли"]
