import sqlite3

import pytest

from ai_coach.store.sport_nutrition import (
    add_protocol,
    add_supplement,
    delete_protocol,
    delete_supplement,
    edit_protocol,
    edit_supplement,
    get_protocol,
    get_supplement,
    list_protocols,
    list_supplements,
)

NOW = "2026-10-07 10:00:00"
LATER = "2026-10-07 18:00:00"


def protocol_values(name: str = "гель", **fields: object) -> dict:
    base = {
        "name": name,
        "phase": "during",
        "sport": None,
        "min_duration_min": 75,
        "offset_min": 0,
        "carbs_g": 60.0,
        "protein_g": 0.0,
        "fluid_ml": 500.0,
        "sodium_mg": 300.0,
        "note": "по вкусу",
        "created_at": NOW,
        "updated_at": NOW,
    }
    return {**base, **fields}


def supplement_values(name: str = "креатин", **fields: object) -> dict:
    base = {
        "name": name,
        "dose": 5.0,
        "unit": "g",
        "schedule": "daily",
        "time_note": "утром",
        "note": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return {**base, **fields}


def new_protocol(conn: sqlite3.Connection, name: str = "гель", **fields: object) -> int:
    return add_protocol(conn, protocol_values(name, **fields))


def new_supplement(conn: sqlite3.Connection, name: str = "креатин", **fields: object) -> int:
    return add_supplement(conn, supplement_values(name, **fields))


def must_protocol(conn: sqlite3.Connection, key: int | str) -> dict:
    found = get_protocol(conn, key)
    assert found is not None
    return found


def must_supplement(conn: sqlite3.Connection, key: int | str) -> dict:
    found = get_supplement(conn, key)
    assert found is not None
    return found


# --- protocol: add / get ---


def test_protocol_add_and_get_by_id(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    row = must_protocol(conn, pid)
    assert row["id"] == pid
    assert (row["name"], row["phase"], row["sport"]) == ("гель", "during", None)
    assert (row["min_duration_min"], row["offset_min"]) == (75, 0)
    assert (row["carbs_g"], row["protein_g"], row["fluid_ml"], row["sodium_mg"]) == (
        60.0,
        0.0,
        500.0,
        300.0,
    )
    assert row["note"] == "по вкусу"


def test_protocol_get_by_name_ignores_case(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn, "Гель")
    assert must_protocol(conn, "гель")["id"] == pid
    assert must_protocol(conn, "ГЕЛЬ")["id"] == pid


def test_protocol_get_unknown_returns_none(conn: sqlite3.Connection) -> None:
    assert get_protocol(conn, 99) is None
    assert get_protocol(conn, "нет такого") is None


def test_protocol_sets_dates(conn: sqlite3.Connection) -> None:
    row = must_protocol(conn, new_protocol(conn))
    assert (row["created_at"], row["updated_at"], row["deleted_at"]) == (NOW, NOW, None)


def test_protocol_with_sport(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn, "гель бег", sport="run")
    assert must_protocol(conn, pid)["sport"] == "run"


def test_protocol_duplicate_name_is_refused(conn: sqlite3.Connection) -> None:
    new_protocol(conn)
    with pytest.raises(ValueError):
        new_protocol(conn)
    assert len(list_protocols(conn)) == 1


def test_protocol_duplicate_name_ignores_case(conn: sqlite3.Connection) -> None:
    new_protocol(conn, "Гель")
    with pytest.raises(ValueError):
        new_protocol(conn, "гель")


def test_protocol_name_can_be_reused_after_delete(conn: sqlite3.Connection) -> None:
    first = new_protocol(conn)
    delete_protocol(conn, first, LATER)
    second = new_protocol(conn)
    assert second != first
    assert must_protocol(conn, "гель")["id"] == second


# --- protocol: list ---


def test_protocol_list_on_empty_database(conn: sqlite3.Connection) -> None:
    assert list_protocols(conn) == []


def test_protocol_list_returns_alive_only(conn: sqlite3.Connection) -> None:
    keep = new_protocol(conn, "гель")
    gone = new_protocol(conn, "напиток")
    delete_protocol(conn, gone, LATER)
    assert [r["id"] for r in list_protocols(conn)] == [keep]


# --- protocol: edit ---


def test_protocol_edit_changes_fields_and_returns_true(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    assert edit_protocol(conn, pid, {"carbs_g": 90.0, "note": "новое"}, LATER) is True
    row = must_protocol(conn, pid)
    assert (row["carbs_g"], row["note"]) == (90.0, "новое")
    assert row["fluid_ml"] == 500.0


def test_protocol_edit_sets_updated_at_only(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    edit_protocol(conn, pid, {"carbs_g": 90.0}, LATER)
    row = must_protocol(conn, pid)
    assert (row["updated_at"], row["created_at"]) == (LATER, NOW)


def test_protocol_edit_renames(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    edit_protocol(conn, pid, {"name": "гель сильный"}, LATER)
    assert must_protocol(conn, "гель сильный")["id"] == pid
    assert get_protocol(conn, "гель") is None


def test_protocol_edit_to_existing_name_is_refused(conn: sqlite3.Connection) -> None:
    new_protocol(conn, "гель")
    other = new_protocol(conn, "напиток")
    with pytest.raises(ValueError):
        edit_protocol(conn, other, {"name": "Гель"}, LATER)
    assert must_protocol(conn, other)["name"] == "напиток"


def test_protocol_edit_keeping_own_name_is_allowed(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn, "гель")
    assert edit_protocol(conn, pid, {"name": "Гель"}, LATER) is True


def test_protocol_edit_unknown_returns_false(conn: sqlite3.Connection) -> None:
    assert edit_protocol(conn, 99, {"carbs_g": 1.0}, LATER) is False


def test_protocol_edit_deleted_returns_false(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    delete_protocol(conn, pid, LATER)
    assert edit_protocol(conn, pid, {"carbs_g": 1.0}, LATER) is False


def test_protocol_edit_does_not_touch_others(conn: sqlite3.Connection) -> None:
    first = new_protocol(conn, "гель")
    second = new_protocol(conn, "напиток")
    edit_protocol(conn, second, {"carbs_g": 1.0}, LATER)
    assert must_protocol(conn, first)["carbs_g"] == 60.0


# --- protocol: delete ---


def test_protocol_delete_hides_it(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    assert delete_protocol(conn, pid, LATER) is True
    assert get_protocol(conn, pid) is None
    assert get_protocol(conn, "гель") is None
    assert list_protocols(conn) == []


def test_protocol_delete_marks_row_instead_of_removing(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    delete_protocol(conn, pid, LATER)
    row = conn.execute("SELECT deleted_at FROM nutrition_protocol WHERE id = ?", (pid,)).fetchone()
    assert row[0] == LATER


def test_protocol_delete_twice_returns_false(conn: sqlite3.Connection) -> None:
    pid = new_protocol(conn)
    delete_protocol(conn, pid, LATER)
    assert delete_protocol(conn, pid, "2026-10-08 10:00:00") is False
    row = conn.execute("SELECT deleted_at FROM nutrition_protocol WHERE id = ?", (pid,)).fetchone()
    assert row[0] == LATER


def test_protocol_delete_unknown_returns_false(conn: sqlite3.Connection) -> None:
    assert delete_protocol(conn, 99, LATER) is False


def test_protocol_delete_does_not_touch_others(conn: sqlite3.Connection) -> None:
    keep = new_protocol(conn, "гель")
    gone = new_protocol(conn, "напиток")
    delete_protocol(conn, gone, LATER)
    assert get_protocol(conn, keep) is not None


# --- supplement ---


def test_supplement_add_and_get_by_id(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    row = must_supplement(conn, sid)
    assert row["id"] == sid
    assert (row["name"], row["dose"], row["unit"]) == ("креатин", 5.0, "g")
    assert (row["schedule"], row["time_note"], row["note"]) == ("daily", "утром", None)
    assert (row["created_at"], row["updated_at"], row["deleted_at"]) == (NOW, NOW, None)


def test_supplement_get_by_name_ignores_case(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn, "Креатин")
    assert must_supplement(conn, "креатин")["id"] == sid


def test_supplement_get_unknown_returns_none(conn: sqlite3.Connection) -> None:
    assert get_supplement(conn, 99) is None
    assert get_supplement(conn, "нет такого") is None


def test_supplement_duplicate_name_is_refused(conn: sqlite3.Connection) -> None:
    new_supplement(conn, "Креатин")
    with pytest.raises(ValueError):
        new_supplement(conn, "креатин")
    assert len(list_supplements(conn)) == 1


def test_supplement_name_can_be_reused_after_delete(conn: sqlite3.Connection) -> None:
    first = new_supplement(conn)
    delete_supplement(conn, first, LATER)
    assert new_supplement(conn) != first


def test_supplement_list_returns_alive_only(conn: sqlite3.Connection) -> None:
    keep = new_supplement(conn, "креатин")
    gone = new_supplement(conn, "магний")
    delete_supplement(conn, gone, LATER)
    assert [r["id"] for r in list_supplements(conn)] == [keep]


def test_supplement_list_on_empty_database(conn: sqlite3.Connection) -> None:
    assert list_supplements(conn) == []


def test_supplement_edit_changes_dose_and_schedule(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    assert edit_supplement(conn, sid, {"dose": 3.0, "schedule": "after"}, LATER) is True
    row = must_supplement(conn, sid)
    assert (row["dose"], row["schedule"], row["unit"]) == (3.0, "after", "g")
    assert (row["updated_at"], row["created_at"]) == (LATER, NOW)


def test_supplement_edit_to_existing_name_is_refused(conn: sqlite3.Connection) -> None:
    new_supplement(conn, "креатин")
    other = new_supplement(conn, "магний")
    with pytest.raises(ValueError):
        edit_supplement(conn, other, {"name": "Креатин"}, LATER)


def test_supplement_edit_unknown_or_deleted_returns_false(conn: sqlite3.Connection) -> None:
    assert edit_supplement(conn, 99, {"dose": 1.0}, LATER) is False
    sid = new_supplement(conn)
    delete_supplement(conn, sid, LATER)
    assert edit_supplement(conn, sid, {"dose": 1.0}, LATER) is False


def test_supplement_delete_hides_and_marks_row(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    assert delete_supplement(conn, sid, LATER) is True
    assert get_supplement(conn, sid) is None
    row = conn.execute("SELECT deleted_at FROM supplement WHERE id = ?", (sid,)).fetchone()
    assert row[0] == LATER


def test_supplement_delete_twice_or_unknown_returns_false(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    delete_supplement(conn, sid, LATER)
    assert delete_supplement(conn, sid, LATER) is False
    assert delete_supplement(conn, 99, LATER) is False
