import sqlite3

from ai_coach.sport_nutrition import compact_nutrition, day_nutrition
from ai_coach.store.intake import delete_intake, log_intake
from ai_coach.store.plans import add_planned_workout
from ai_coach.store.sport_nutrition import add_supplement

DAY = "2026-10-08"
NOW = "2026-10-08 10:00:00"


def new_supplement(conn: sqlite3.Connection, name: str = "креатин", schedule: str = "daily") -> int:
    return add_supplement(
        conn,
        {
            "name": name,
            "dose": 5.0,
            "unit": "g",
            "schedule": schedule,
            "time_note": None,
            "note": None,
            "created_at": NOW,
            "updated_at": NOW,
        },
    )


def take(conn: sqlite3.Connection, item_id: int, day: str = DAY) -> int:
    values = {
        "kind": "supplement",
        "item_id": item_id,
        "date": day,
        "taken_at": f"{day} 09:00:00",
        "dose": None,
        "note": None,
    }
    return log_intake(conn, values)


def new_workout(conn: sqlite3.Connection) -> int:
    row = {"date": DAY, "sport": "run", "name": "т", "workout_json": {}, "status": "approved"}
    return add_planned_workout(conn, row)


def taken_by_name(conn: sqlite3.Connection, day: str = DAY) -> dict[str, bool]:
    return {s["name"]: s["taken"] for s in day_nutrition(conn, day)["supplements"]}


# --- day_nutrition: taken ---


def test_supplement_without_intake_is_not_taken(conn: sqlite3.Connection) -> None:
    new_supplement(conn)
    assert taken_by_name(conn) == {"креатин": False}


def test_supplement_with_intake_is_taken(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn))
    assert taken_by_name(conn) == {"креатин": True}


def test_two_intakes_are_still_taken_once_in_flag(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    take(conn, sid)
    take(conn, sid)
    day = day_nutrition(conn, DAY)
    assert [s["taken"] for s in day["supplements"]] == [True]


def test_intake_of_other_date_does_not_count(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn), "2026-10-07")
    assert taken_by_name(conn) == {"креатин": False}


def test_backdated_intake_marks_that_day(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn), "2026-10-07")
    assert taken_by_name(conn, "2026-10-07") == {"креатин": True}


def test_deleted_intake_does_not_count(conn: sqlite3.Connection) -> None:
    lid = take(conn, new_supplement(conn))
    delete_intake(conn, lid, "2026-10-08 12:00:00")
    assert taken_by_name(conn) == {"креатин": False}


def test_one_deleted_of_two_intakes_still_counts(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    first = take(conn, sid)
    take(conn, sid)
    delete_intake(conn, first, "2026-10-08 12:00:00")
    assert taken_by_name(conn) == {"креатин": True}


def test_taken_is_per_supplement(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn, "креатин"))
    new_supplement(conn, "магний")
    assert taken_by_name(conn) == {"креатин": True, "магний": False}


def test_taken_on_training_day_for_training_supplement(conn: sqlite3.Connection) -> None:
    new_workout(conn)
    take(conn, new_supplement(conn, "кофеин", "before"))
    new_supplement(conn, "магний", "training_day")
    assert taken_by_name(conn) == {"кофеин": True, "магний": False}


def test_taken_is_a_bool(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn))
    new_supplement(conn, "магний")
    for item in day_nutrition(conn, DAY)["supplements"]:
        assert isinstance(item["taken"], bool)


# --- compact_nutrition ---


def line(conn: sqlite3.Connection) -> str:
    found = compact_nutrition(day_nutrition(conn, DAY))
    assert found is not None
    return found["supplements"]


def part(text: str, name: str) -> str:
    return next(p for p in text.split("; ") if p.startswith(name))


def test_compact_marks_taken_supplement(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn, "креатин"))
    new_supplement(conn, "магний")
    text = line(conn)
    assert "принят" in part(text, "креатин")
    assert "принят" not in part(text, "магний")


def test_compact_without_intake_has_no_mark(conn: sqlite3.Connection) -> None:
    new_supplement(conn, "креатин")
    assert "принят" not in line(conn)


def test_compact_keeps_name_and_dose(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn, "креатин"))
    assert "креатин 5 g" in line(conn)


def test_compact_mark_has_no_emoji(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn, "креатин"))
    assert all(ord(char) < 0x2000 for char in line(conn))


def test_compact_marks_all_taken_supplements_without_cut(conn: sqlite3.Connection) -> None:
    for number in range(10):
        take(conn, new_supplement(conn, f"добавка номер {number}"))
    text = line(conn)
    for number in range(10):
        assert "принят" in part(text, f"добавка номер {number}")
