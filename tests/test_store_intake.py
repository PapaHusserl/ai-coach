import sqlite3

import pytest

from ai_coach.store.intake import delete_intake, list_intake, log_intake
from ai_coach.store.sport_nutrition import add_supplement, delete_supplement

NOW = "2026-10-08 10:00:00"
LATER = "2026-10-08 18:00:00"
DAY = "2026-10-08"


def new_supplement(conn: sqlite3.Connection, name: str = "креатин") -> int:
    return add_supplement(
        conn,
        {
            "name": name,
            "dose": 5.0,
            "unit": "g",
            "schedule": "daily",
            "time_note": None,
            "note": None,
            "created_at": NOW,
            "updated_at": NOW,
        },
    )


def values(item_id: int, day: str = DAY, **fields: object) -> dict:
    base = {
        "kind": "supplement",
        "item_id": item_id,
        "date": day,
        "taken_at": f"{day} 09:00:00",
        "dose": None,
        "note": None,
    }
    return {**base, **fields}


def new_intake(conn: sqlite3.Connection, item_id: int, day: str = DAY, **fields: object) -> int:
    return log_intake(conn, values(item_id, day, **fields))


def log_ids(conn: sqlite3.Connection, start: str = DAY, end: str = DAY) -> list[int]:
    return [r["id"] for r in list_intake(conn, start, end)]


# --- log / list ---


def test_log_returns_id_and_list_shows_row_with_name(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    lid = new_intake(conn, sid, dose=3.0, note="с водой")
    row = list_intake(conn, DAY, DAY)[0]
    assert row["id"] == lid
    assert (row["kind"], row["item_id"], row["name"]) == ("supplement", sid, "креатин")
    assert (row["date"], row["dose"], row["note"]) == (DAY, 3.0, "с водой")
    assert row["taken_at"] == "2026-10-08 09:00:00"


def test_log_without_dose_keeps_null(conn: sqlite3.Connection) -> None:
    new_intake(conn, new_supplement(conn))
    assert list_intake(conn, DAY, DAY)[0]["dose"] is None


def test_list_on_empty_database(conn: sqlite3.Connection) -> None:
    assert list_intake(conn, DAY, DAY) == []


def test_log_zero_dose_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        new_intake(conn, new_supplement(conn), dose=0.0)


def test_log_bad_kind_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        new_intake(conn, new_supplement(conn), kind="med")


def test_several_intakes_per_day_are_allowed(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    first = new_intake(conn, sid)
    second = new_intake(conn, sid, taken_at=f"{DAY} 20:00:00")
    assert log_ids(conn) == [first, second]


def test_list_range_is_inclusive_on_both_ends(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    before = new_intake(conn, sid, "2026-10-05")
    first = new_intake(conn, sid, "2026-10-06")
    middle = new_intake(conn, sid, "2026-10-07")
    last = new_intake(conn, sid, "2026-10-08")
    after = new_intake(conn, sid, "2026-10-09")
    found = log_ids(conn, "2026-10-06", "2026-10-08")
    assert found == [first, middle, last]
    assert before not in found
    assert after not in found


def test_list_single_day_range(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    new_intake(conn, sid, "2026-10-07")
    today = new_intake(conn, sid, DAY)
    assert log_ids(conn) == [today]


def test_list_is_ordered_by_date_then_time(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    late = new_intake(conn, sid, DAY, taken_at=f"{DAY} 20:00:00")
    early = new_intake(conn, sid, DAY, taken_at=f"{DAY} 08:00:00")
    yesterday = new_intake(conn, sid, "2026-10-07")
    assert log_ids(conn, "2026-10-07", DAY) == [yesterday, early, late]


def test_backdated_intake_is_listed_on_its_date(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    lid = new_intake(conn, sid, "2026-09-01", taken_at=NOW)
    assert log_ids(conn, "2026-09-01", "2026-09-01") == [lid]
    assert log_ids(conn) == []


def test_list_shows_name_of_deleted_supplement(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn, "магний")
    new_intake(conn, sid)
    delete_supplement(conn, sid, LATER)
    assert [r["name"] for r in list_intake(conn, DAY, DAY)] == ["магний"]


def test_list_has_rows_of_different_supplements(conn: sqlite3.Connection) -> None:
    first = new_intake(conn, new_supplement(conn, "креатин"))
    second = new_intake(conn, new_supplement(conn, "магний"))
    found = {r["id"]: r["name"] for r in list_intake(conn, DAY, DAY)}
    assert found == {first: "креатин", second: "магний"}


# --- delete ---


def test_delete_hides_row_and_marks_it(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    lid = new_intake(conn, sid)
    assert delete_intake(conn, lid, LATER) is True
    assert log_ids(conn) == []
    assert conn.execute("SELECT deleted_at FROM intake_log").fetchone()[0] == LATER


def test_delete_twice_returns_false(conn: sqlite3.Connection) -> None:
    lid = new_intake(conn, new_supplement(conn))
    delete_intake(conn, lid, LATER)
    assert delete_intake(conn, lid, "2026-10-09 10:00:00") is False
    assert conn.execute("SELECT deleted_at FROM intake_log").fetchone()[0] == LATER


def test_delete_unknown_returns_false(conn: sqlite3.Connection) -> None:
    assert delete_intake(conn, 99, LATER) is False


def test_delete_keeps_other_rows(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    gone = new_intake(conn, sid)
    kept = new_intake(conn, sid)
    delete_intake(conn, gone, LATER)
    assert log_ids(conn) == [kept]
