import sqlite3
from typing import Any

import pytest

from ai_coach.meds import public_meds, short_meds
from ai_coach.sport_nutrition import day_nutrition, has_training
from ai_coach.store.meds import add_med
from ai_coach.store.plans import add_planned_workout
from ai_coach.store.sport_nutrition import add_supplement

DAY = "2026-10-08"
NOW = "2026-10-08 10:00:00"
TRAINING_SCHEDULES = ["training_day", "before", "after"]


def new_med(conn: sqlite3.Connection, name: str, schedule: str = "daily", **fields: Any) -> int:
    base = {
        "name": name,
        "kind": "vitamin",
        "dose": 25.0,
        "unit": "mcg",
        "schedule": schedule,
        "start_date": "2026-10-01",
        "end_date": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return add_med(conn, {**base, **fields})


def new_workout(conn: sqlite3.Connection, status: str = "approved", day: str = DAY) -> int:
    row = {"date": day, "sport": "run", "name": "т", "workout_json": {}, "status": status}
    return add_planned_workout(conn, row)


def names(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(r["name"] for r in rows)


# --- has_training ---


def test_has_training_false_without_plan(conn: sqlite3.Connection) -> None:
    assert has_training(conn, DAY) is False


def test_has_training_true_with_workout(conn: sqlite3.Connection) -> None:
    new_workout(conn)
    assert has_training(conn, DAY) is True


def test_has_training_counts_draft(conn: sqlite3.Connection) -> None:
    new_workout(conn, "draft")
    assert has_training(conn, DAY) is True


def test_has_training_false_with_only_cancelled(conn: sqlite3.Connection) -> None:
    new_workout(conn, "cancelled")
    assert has_training(conn, DAY) is False


def test_has_training_true_with_cancelled_and_live(conn: sqlite3.Connection) -> None:
    new_workout(conn, "cancelled")
    new_workout(conn, "approved")
    assert has_training(conn, DAY) is True


def test_has_training_ignores_other_day(conn: sqlite3.Connection) -> None:
    new_workout(conn, day="2026-10-09")
    assert has_training(conn, DAY) is False


def test_day_nutrition_supplements_follow_has_training(conn: sqlite3.Connection) -> None:
    for name, schedule in [("ежедневная", "daily"), ("тренировочная", "after")]:
        add_supplement(
            conn,
            {
                "name": name,
                "dose": 1.0,
                "unit": "g",
                "schedule": schedule,
                "created_at": NOW,
                "updated_at": NOW,
            },
        )
    new_workout(conn, "cancelled")
    assert names(day_nutrition(conn, DAY)["supplements"]) == ["ежедневная"]


# --- public_meds / short_meds на день ---


def test_daily_course_shown_without_training(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли")
    assert names(public_meds(conn, DAY)) == ["дейли"]


@pytest.mark.parametrize("schedule", TRAINING_SCHEDULES)
def test_training_course_hidden_without_training(conn: sqlite3.Connection, schedule: str) -> None:
    new_med(conn, "тренировочный", schedule)
    assert public_meds(conn, DAY) == []


@pytest.mark.parametrize("schedule", TRAINING_SCHEDULES)
def test_training_course_shown_with_training(conn: sqlite3.Connection, schedule: str) -> None:
    new_med(conn, "тренировочный", schedule)
    new_workout(conn)
    assert names(public_meds(conn, DAY)) == ["тренировочный"]


@pytest.mark.parametrize("schedule", TRAINING_SCHEDULES)
def test_training_course_hidden_with_only_cancelled(
    conn: sqlite3.Connection, schedule: str
) -> None:
    new_med(conn, "тренировочный", schedule)
    new_workout(conn, "cancelled")
    assert public_meds(conn, DAY) == []


def test_daily_course_shown_with_only_cancelled(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли")
    new_workout(conn, "cancelled")
    assert names(public_meds(conn, DAY)) == ["дейли"]


def test_training_course_shown_with_cancelled_and_live(conn: sqlite3.Connection) -> None:
    new_med(conn, "тренировочный", "before")
    new_workout(conn, "cancelled")
    new_workout(conn, "approved")
    assert names(public_meds(conn, DAY)) == ["тренировочный"]


def test_two_workouts_give_course_once(conn: sqlite3.Connection) -> None:
    new_med(conn, "тренировочный", "after")
    new_med(conn, "дейли")
    new_workout(conn)
    new_workout(conn)
    assert names(public_meds(conn, DAY)) == ["дейли", "тренировочный"]
    assert len(short_meds(conn, DAY)) == 2


def test_workout_on_other_day_does_not_show_training_course(conn: sqlite3.Connection) -> None:
    new_med(conn, "тренировочный", "after")
    new_workout(conn, day="2026-10-09")
    assert public_meds(conn, DAY) == []


def test_course_borders_still_apply_with_training(conn: sqlite3.Connection) -> None:
    new_med(conn, "курс", "after", start_date="2026-10-08", end_date="2026-10-10")
    new_workout(conn, day="2026-10-07")
    new_workout(conn, day="2026-10-08")
    new_workout(conn, day="2026-10-10")
    new_workout(conn, day="2026-10-11")
    assert public_meds(conn, "2026-10-07") == []
    assert names(public_meds(conn, "2026-10-08")) == ["курс"]
    assert names(public_meds(conn, "2026-10-10")) == ["курс"]
    assert public_meds(conn, "2026-10-11") == []


def test_without_day_returns_all_courses_without_filter(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли")
    new_med(conn, "тренировочный", "after")
    new_med(conn, "закончен", "after", start_date="2026-08-01", end_date="2026-08-31")
    assert names(public_meds(conn, None)) == ["дейли", "закончен", "тренировочный"]


def test_short_meds_filtered_like_public(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли")
    new_med(conn, "тренировочный", "training_day")
    assert [r["name"] for r in short_meds(conn, DAY)] == ["дейли"]
    new_workout(conn)
    assert [r["name"] for r in short_meds(conn, DAY)] == ["дейли", "тренировочный"]


def test_public_meds_has_no_service_fields(conn: sqlite3.Connection) -> None:
    new_med(conn, "дейли")
    row = public_meds(conn, DAY)[0]
    assert "created_at" not in row
    assert "deleted_at" not in row
