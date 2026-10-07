import sqlite3

import pytest

from ai_coach.store.meds import (
    add_med,
    delete_med,
    edit_med,
    get_med,
    list_meds,
    meds_on,
)

NOW = "2026-10-08 10:00:00"
LATER = "2026-10-08 18:00:00"


def med_values(name: str = "витамин D", **fields: object) -> dict:
    base = {
        "name": name,
        "kind": "vitamin",
        "dose": 25.0,
        "unit": "mcg",
        "schedule": "daily",
        "time_note": "с едой",
        "start_date": "2026-10-01",
        "end_date": None,
        "note": "по инструкции",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return {**base, **fields}


def new_med(conn: sqlite3.Connection, name: str = "витамин D", **fields: object) -> int:
    return add_med(conn, med_values(name, **fields))


def must_med(conn: sqlite3.Connection, key: int | str) -> dict:
    found = get_med(conn, key)
    assert found is not None
    return found


def names_on(conn: sqlite3.Connection, day: str) -> list[str]:
    return [r["name"] for r in meds_on(conn, day)]


# --- add / get ---


def test_add_and_get_by_id(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    row = must_med(conn, mid)
    assert row["id"] == mid
    assert (row["name"], row["kind"], row["dose"], row["unit"]) == (
        "витамин D",
        "vitamin",
        25.0,
        "mcg",
    )
    assert (row["schedule"], row["time_note"], row["note"]) == ("daily", "с едой", "по инструкции")
    assert (row["start_date"], row["end_date"]) == ("2026-10-01", None)


def test_add_sets_dates(conn: sqlite3.Connection) -> None:
    row = must_med(conn, new_med(conn))
    assert (row["created_at"], row["updated_at"], row["deleted_at"]) == (NOW, NOW, None)


def test_get_by_name_ignores_case(conn: sqlite3.Connection) -> None:
    mid = new_med(conn, "Магний")
    assert must_med(conn, "магний")["id"] == mid
    assert must_med(conn, "МАГНИЙ")["id"] == mid


def test_get_unknown_returns_none(conn: sqlite3.Connection) -> None:
    assert get_med(conn, 99) is None
    assert get_med(conn, "нет такого") is None


def test_duplicate_name_is_refused(conn: sqlite3.Connection) -> None:
    new_med(conn)
    with pytest.raises(ValueError):
        new_med(conn)
    assert len(list_meds(conn)) == 1


def test_duplicate_name_ignores_case(conn: sqlite3.Connection) -> None:
    new_med(conn, "Магний")
    with pytest.raises(ValueError):
        new_med(conn, "магний")


def test_name_can_be_reused_after_delete(conn: sqlite3.Connection) -> None:
    first = new_med(conn)
    delete_med(conn, first, LATER)
    second = new_med(conn)
    assert second != first
    assert must_med(conn, "витамин D")["id"] == second


def test_get_deleted_returns_none(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    delete_med(conn, mid, LATER)
    assert get_med(conn, mid) is None
    assert get_med(conn, "витамин D") is None


# --- list ---


def test_list_on_empty_database(conn: sqlite3.Connection) -> None:
    assert list_meds(conn) == []


def test_list_returns_alive_only_sorted_by_name(conn: sqlite3.Connection) -> None:
    new_med(conn, "цинк")
    gone = new_med(conn, "омега")
    new_med(conn, "железо")
    delete_med(conn, gone, LATER)
    assert [r["name"] for r in list_meds(conn)] == ["железо", "цинк"]


def test_list_includes_finished_and_future_courses(conn: sqlite3.Connection) -> None:
    new_med(conn, "прошлый", end_date="2026-09-01", start_date="2026-08-01")
    new_med(conn, "будущий", start_date="2027-01-01")
    assert len(list_meds(conn)) == 2


# --- edit ---


def test_edit_changes_fields_and_returns_true(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    assert edit_med(conn, mid, {"dose": 50.0, "note": "новая"}, LATER) is True
    row = must_med(conn, mid)
    assert (row["dose"], row["note"]) == (50.0, "новая")
    assert row["updated_at"] == LATER
    assert row["created_at"] == NOW


def test_edit_keeps_other_fields(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    edit_med(conn, mid, {"dose": 50.0}, LATER)
    row = must_med(conn, mid)
    assert (row["name"], row["unit"], row["start_date"]) == ("витамин D", "mcg", "2026-10-01")


def test_edit_can_set_end_date(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    edit_med(conn, mid, {"end_date": "2026-10-31"}, LATER)
    assert must_med(conn, mid)["end_date"] == "2026-10-31"


def test_edit_unknown_or_deleted_returns_false(conn: sqlite3.Connection) -> None:
    assert edit_med(conn, 99, {"dose": 1.0}, LATER) is False
    mid = new_med(conn)
    delete_med(conn, mid, LATER)
    assert edit_med(conn, mid, {"dose": 1.0}, LATER) is False


def test_edit_name_to_taken_is_refused(conn: sqlite3.Connection) -> None:
    new_med(conn, "цинк")
    mid = new_med(conn, "железо")
    with pytest.raises(ValueError):
        edit_med(conn, mid, {"name": "Цинк"}, LATER)
    assert must_med(conn, mid)["name"] == "железо"


def test_edit_name_to_itself_is_allowed(conn: sqlite3.Connection) -> None:
    mid = new_med(conn, "цинк")
    assert edit_med(conn, mid, {"name": "ЦИНК"}, LATER) is True


# --- delete ---


def test_delete_marks_row_and_returns_true(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    assert delete_med(conn, mid, LATER) is True
    row = conn.execute("SELECT deleted_at FROM med_course WHERE id = ?", (mid,)).fetchone()
    assert row[0] == LATER


def test_delete_twice_or_unknown_returns_false(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    delete_med(conn, mid, LATER)
    assert delete_med(conn, mid, "2026-10-09 10:00:00") is False
    assert delete_med(conn, 99, LATER) is False
    row = conn.execute("SELECT deleted_at FROM med_course WHERE id = ?", (mid,)).fetchone()
    assert row[0] == LATER


# --- meds_on: границы дат ---


def test_meds_on_empty_database(conn: sqlite3.Connection) -> None:
    assert meds_on(conn, "2026-10-08") == []


def test_meds_on_includes_start_and_end_days(conn: sqlite3.Connection) -> None:
    new_med(conn, "курс", start_date="2026-10-05", end_date="2026-10-10")
    assert names_on(conn, "2026-10-05") == ["курс"]
    assert names_on(conn, "2026-10-07") == ["курс"]
    assert names_on(conn, "2026-10-10") == ["курс"]


def test_meds_on_excludes_day_before_start_and_after_end(conn: sqlite3.Connection) -> None:
    new_med(conn, "курс", start_date="2026-10-05", end_date="2026-10-10")
    assert names_on(conn, "2026-10-04") == []
    assert names_on(conn, "2026-10-11") == []


def test_meds_on_one_day_course(conn: sqlite3.Connection) -> None:
    new_med(conn, "разовый", start_date="2026-10-08", end_date="2026-10-08")
    assert names_on(conn, "2026-10-07") == []
    assert names_on(conn, "2026-10-08") == ["разовый"]
    assert names_on(conn, "2026-10-09") == []


def test_meds_on_open_ended_course_has_no_upper_bound(conn: sqlite3.Connection) -> None:
    new_med(conn, "бессрочный", start_date="2026-10-05", end_date=None)
    assert names_on(conn, "2026-10-04") == []
    assert names_on(conn, "2026-10-05") == ["бессрочный"]
    assert names_on(conn, "2099-01-01") == ["бессрочный"]


def test_meds_on_skips_deleted(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    new_med(conn, "цинк")
    delete_med(conn, mid, LATER)
    assert names_on(conn, "2026-10-08") == ["цинк"]


def test_meds_on_returns_only_courses_of_that_day(conn: sqlite3.Connection) -> None:
    new_med(conn, "а-текущий", start_date="2026-10-01", end_date="2026-10-31")
    new_med(conn, "б-закончен", start_date="2026-09-01", end_date="2026-09-30")
    new_med(conn, "в-будущий", start_date="2026-11-01")
    new_med(conn, "г-бессрочный", start_date="2026-01-01")
    assert names_on(conn, "2026-10-08") == ["а-текущий", "г-бессрочный"]


def test_meds_on_row_has_fields(conn: sqlite3.Connection) -> None:
    mid = new_med(conn)
    row = meds_on(conn, "2026-10-08")[0]
    assert (row["id"], row["kind"], row["dose"], row["unit"], row["schedule"]) == (
        mid,
        "vitamin",
        25.0,
        "mcg",
        "daily",
    )
