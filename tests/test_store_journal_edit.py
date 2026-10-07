import sqlite3

from ai_coach.store.journal import (
    add_food,
    add_weight,
    delete_food,
    delete_weight,
    edit_food,
    edit_weight,
    list_food,
    list_food_pending,
    list_weights,
    update_food,
)

DAY = "2026-10-07"
DELETED = "2026-10-07 12:00:00"
MACROS = {"kcal": 350.0, "protein_g": 12.0, "fat_g": 6.0, "carbs_g": 60.0}


def new_weight(conn: sqlite3.Connection, kg: float = 81.0) -> int:
    return add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": kg})


def new_food(conn: sqlite3.Connection, text: str = "каша") -> int:
    return add_food(conn, {"logged_at": f"{DAY} 08:00:00", "text": text})


def weights(conn: sqlite3.Connection) -> list[dict]:
    return list_weights(conn, "2000-01-01", "2100-01-01")


def food(conn: sqlite3.Connection) -> list[dict]:
    return list_food(conn, "2000-01-01", "2100-01-01")


def test_edit_weight_changes_value_and_returns_true(conn: sqlite3.Connection) -> None:
    wid = new_weight(conn)
    assert edit_weight(conn, wid, weight_kg=80.2) is True
    row = weights(conn)[0]
    assert (row["id"], row["weight_kg"], row["measured_at"]) == (wid, 80.2, f"{DAY} 07:00:00")


def test_edit_weight_does_not_touch_other_rows(conn: sqlite3.Connection) -> None:
    first = new_weight(conn, 81.0)
    second = new_weight(conn, 82.0)
    edit_weight(conn, second, weight_kg=79.0)
    by_id = {r["id"]: r for r in weights(conn)}
    assert by_id[first]["weight_kg"] == 81.0
    assert by_id[second]["weight_kg"] == 79.0


def test_edit_weight_time(conn: sqlite3.Connection) -> None:
    wid = new_weight(conn)
    assert edit_weight(conn, wid, measured_at="2026-10-05 12:00:00") is True
    row = weights(conn)[0]
    assert (row["weight_kg"], row["measured_at"]) == (81.0, "2026-10-05 12:00:00")


def test_edit_unknown_weight_is_false(conn: sqlite3.Connection) -> None:
    assert edit_weight(conn, 999, weight_kg=80.0) is False


def test_edit_food_changes_text_and_returns_true(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    assert edit_food(conn, fid, text="гречка") is True
    row = food(conn)[0]
    assert (row["id"], row["text"], row["logged_at"]) == (fid, "гречка", f"{DAY} 08:00:00")


def test_edit_food_text_resets_macros(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    update_food(conn, fid, MACROS)
    edit_food(conn, fid, text="гречка")
    row = food(conn)[0]
    assert (row["kcal"], row["protein_g"], row["fat_g"], row["carbs_g"]) == (None,) * 4


def test_edited_food_is_pending_again(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    update_food(conn, fid, MACROS)
    assert list_food_pending(conn) == []
    edit_food(conn, fid, text="гречка")
    assert [r["id"] for r in list_food_pending(conn)] == [fid]


def test_macros_can_be_written_again_after_edit(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    update_food(conn, fid, MACROS)
    edit_food(conn, fid, text="гречка")
    assert update_food(conn, fid, {**MACROS, "kcal": 410.0}) is True
    assert food(conn)[0]["kcal"] == 410.0


def test_edit_food_time(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    assert edit_food(conn, fid, logged_at="2026-10-05 12:00:00") is True
    row = food(conn)[0]
    assert (row["text"], row["logged_at"]) == ("каша", "2026-10-05 12:00:00")


def test_edit_food_time_keeps_macros(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    update_food(conn, fid, MACROS)
    edit_food(conn, fid, logged_at="2026-10-05 12:00:00")
    assert food(conn)[0]["kcal"] == 350.0


def test_edit_food_does_not_touch_other_rows(conn: sqlite3.Connection) -> None:
    first = new_food(conn, "каша")
    second = new_food(conn, "суп")
    update_food(conn, first, MACROS)
    edit_food(conn, second, text="борщ")
    by_id = {r["id"]: r for r in food(conn)}
    assert (by_id[first]["text"], by_id[first]["kcal"]) == ("каша", 350.0)
    assert by_id[second]["text"] == "борщ"


def test_edit_unknown_food_is_false(conn: sqlite3.Connection) -> None:
    assert edit_food(conn, 999, text="x") is False


def test_delete_weight_hides_it_from_list(conn: sqlite3.Connection) -> None:
    keep = new_weight(conn, 81.0)
    gone = new_weight(conn, 82.0)
    assert delete_weight(conn, gone, DELETED) is True
    assert [r["id"] for r in weights(conn)] == [keep]


def test_delete_weight_marks_row_and_does_not_remove_it(conn: sqlite3.Connection) -> None:
    wid = new_weight(conn)
    delete_weight(conn, wid, DELETED)
    row = conn.execute("SELECT deleted_at FROM weight_log WHERE id = ?", (wid,)).fetchone()
    assert row is not None
    assert row[0] == DELETED


def test_delete_weight_twice_is_false(conn: sqlite3.Connection) -> None:
    wid = new_weight(conn)
    delete_weight(conn, wid, DELETED)
    first_mark = conn.execute("SELECT deleted_at FROM weight_log").fetchone()[0]
    assert delete_weight(conn, wid, DELETED) is False
    assert conn.execute("SELECT deleted_at FROM weight_log").fetchone()[0] == first_mark


def test_delete_unknown_weight_is_false(conn: sqlite3.Connection) -> None:
    assert delete_weight(conn, 999, DELETED) is False


def test_edit_deleted_weight_is_false_and_changes_nothing(conn: sqlite3.Connection) -> None:
    wid = new_weight(conn, 81.0)
    delete_weight(conn, wid, DELETED)
    assert edit_weight(conn, wid, weight_kg=70.0) is False
    assert conn.execute("SELECT weight_kg FROM weight_log").fetchone()[0] == 81.0


def test_delete_food_hides_it_from_list_and_pending(conn: sqlite3.Connection) -> None:
    keep = new_food(conn, "каша")
    gone = new_food(conn, "суп")
    assert delete_food(conn, gone, DELETED) is True
    assert [r["id"] for r in food(conn)] == [keep]
    assert [r["id"] for r in list_food_pending(conn)] == [keep]


def test_delete_food_marks_row_and_does_not_remove_it(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    delete_food(conn, fid, DELETED)
    row = conn.execute("SELECT deleted_at FROM food_log WHERE id = ?", (fid,)).fetchone()
    assert row is not None
    assert row[0] == DELETED


def test_delete_food_twice_is_false(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    delete_food(conn, fid, DELETED)
    assert delete_food(conn, fid, DELETED) is False


def test_delete_unknown_food_is_false(conn: sqlite3.Connection) -> None:
    assert delete_food(conn, 999, DELETED) is False


def test_edit_deleted_food_is_false_and_changes_nothing(conn: sqlite3.Connection) -> None:
    fid = new_food(conn, "каша")
    delete_food(conn, fid, DELETED)
    assert edit_food(conn, fid, text="борщ") is False
    assert conn.execute("SELECT text FROM food_log").fetchone()[0] == "каша"


def test_update_food_does_not_write_into_deleted(conn: sqlite3.Connection) -> None:
    fid = new_food(conn)
    delete_food(conn, fid, DELETED)
    assert update_food(conn, fid, MACROS) is False
    assert conn.execute("SELECT kcal FROM food_log").fetchone()[0] is None


def test_delete_weight_does_not_touch_food_with_same_id(conn: sqlite3.Connection) -> None:
    wid = new_weight(conn)
    fid = new_food(conn)
    assert wid == fid
    delete_weight(conn, wid, DELETED)
    assert [r["id"] for r in food(conn)] == [fid]
