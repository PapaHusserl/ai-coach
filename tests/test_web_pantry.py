"""Вкладка «Еда» в пульте: вид кладовой и запись из пульта (шаг П4, партия 4)."""

import sqlite3
from datetime import date, datetime
from typing import Any

import pytest

from ai_coach.pantry.service import PantryEntry, record, stock
from ai_coach.profile.service import set_value
from ai_coach.store.journal import add_food, add_weight
from ai_coach.store.pantry import list_entries
from ai_coach.web.errors import MarkError
from ai_coach.web.pantry import pantry_view, save_pantry

DAY = date(2026, 11, 7)
D = "2026-11-07"
NOW = datetime(2026, 11, 7, 9, 30, 15)
LOGGED = "2026-11-07 09:30:15"
T0 = "2026-11-01 10:00:00"


def put(
    conn: sqlite3.Connection, item: str, qty: float, unit: str = "g", until: str | None = None
) -> None:
    record(conn, PantryEntry("add", item, qty, unit, T0, expires_on=until))
    conn.commit()


def amounts(conn: sqlite3.Connection) -> dict[str, float]:
    return {row["item"]: row["qty"] for row in stock(conn)}


def rows_by_item(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {row["item"]: row for row in pantry_view(conn, DAY, NOW)["rows"]}


def test_view_has_rows_remaining_and_food(conn: sqlite3.Connection) -> None:
    assert set(pantry_view(conn, DAY, NOW)) == {"rows", "remaining", "food"}


def test_view_of_empty_pantry_has_no_rows(conn: sqlite3.Connection) -> None:
    assert pantry_view(conn, DAY, NOW)["rows"] == []


def test_view_row_has_the_agreed_keys(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 500, until="2026-12-01")
    [row] = pantry_view(conn, DAY, NOW)["rows"]
    assert set(row) == {"item", "qty", "unit", "expires_on", "opened", "expired", "soon"}
    assert (row["item"], row["qty"], row["unit"], row["expires_on"]) == (
        "рис",
        500,
        "g",
        "2026-12-01",
    )


def test_view_rows_are_in_stock_order(conn: sqlite3.Connection) -> None:
    put(conn, "яйца", 10, "pcs")
    put(conn, "авокадо", 2, "pcs")
    put(conn, "мука", 1000)
    assert [r["item"] for r in pantry_view(conn, DAY, NOW)["rows"]] == ["авокадо", "мука", "яйца"]


def test_view_expired_batch_is_flagged_expired_not_soon(conn: sqlite3.Connection) -> None:
    put(conn, "молоко", 500, "ml", until="2026-11-06")
    row = rows_by_item(conn)["молоко"]
    assert (row["expired"], row["soon"]) == (True, False)


def test_view_expiry_in_one_day_is_soon(conn: sqlite3.Connection) -> None:
    put(conn, "кефир", 500, "ml", until="2026-11-08")
    row = rows_by_item(conn)["кефир"]
    assert (row["expired"], row["soon"]) == (False, True)


def test_view_expiry_today_is_soon_not_expired(conn: sqlite3.Connection) -> None:
    put(conn, "хлеб", 400, until=D)
    row = rows_by_item(conn)["хлеб"]
    assert (row["expired"], row["soon"]) == (False, True)


def test_view_expiry_in_two_days_is_still_soon(conn: sqlite3.Connection) -> None:
    put(conn, "сыр", 200, until="2026-11-09")
    assert rows_by_item(conn)["сыр"]["soon"] is True


def test_view_expiry_in_three_days_is_not_soon(conn: sqlite3.Connection) -> None:
    put(conn, "творог", 200, until="2026-11-10")
    row = rows_by_item(conn)["творог"]
    assert (row["expired"], row["soon"]) == (False, False)


def test_view_without_expiry_has_no_flags(conn: sqlite3.Connection) -> None:
    put(conn, "соль", 1000)
    row = rows_by_item(conn)["соль"]
    assert (row["expires_on"], row["expired"], row["soon"]) == (None, False, False)


def test_view_flags_depend_on_viewed_day(conn: sqlite3.Connection) -> None:
    put(conn, "кефир", 500, "ml", until="2026-11-08")
    later = pantry_view(conn, date(2026, 11, 9), NOW)["rows"][0]
    assert (later["expired"], later["soon"]) == (True, False)


def test_view_rows_match_stock_quantities(conn: sqlite3.Connection) -> None:
    put(conn, "курица", 500)
    record(conn, PantryEntry("use", "курица", 150, "g", T0))
    conn.commit()
    assert rows_by_item(conn)["курица"]["qty"] == amounts(conn)["курица"] == 350


def profile(conn: sqlite3.Connection) -> None:
    for key, value in [
        ("sex", "m"),
        ("birth_date", "1990-01-15"),
        ("height_cm", "180"),
        ("kcal_target", "2400"),
    ]:
        set_value(conn, key, value, "manual", "2026-10-01T10:00:00")
    add_weight(conn, {"measured_at": "2026-11-06 07:00:00", "weight_kg": 80.0})
    conn.commit()


def eaten(conn: sqlite3.Connection, text: str, kcal: float | None, day: str = D) -> None:
    values: dict[str, Any] = {"logged_at": f"{day} 08:00:00", "text": text, "kcal": kcal}
    if kcal is not None:
        values |= {"protein_g": 30, "fat_g": 10, "carbs_g": 50}
    add_food(conn, values)
    conn.commit()


def test_view_remaining_is_none_without_profile(conn: sqlite3.Connection) -> None:
    assert pantry_view(conn, DAY, NOW)["remaining"] is None


def test_view_remaining_is_target_minus_day_food(conn: sqlite3.Connection) -> None:
    profile(conn)
    eaten(conn, "каша", 500)
    eaten(conn, "вчера", 900, day="2026-11-06")
    eaten(conn, "без КБЖУ", None)
    remaining = pantry_view(conn, DAY, NOW)["remaining"]
    assert remaining["kcal"] == 2400 - 500
    assert remaining["pending_count"] == 1


def test_view_food_lists_only_the_day_entries_with_time_text_kcal(
    conn: sqlite3.Connection,
) -> None:
    eaten(conn, "каша", 500)
    eaten(conn, "вчера", 900, day="2026-11-06")
    [food] = pantry_view(conn, DAY, NOW)["food"]
    assert (food["text"], food["kcal"], food["logged_at"]) == ("каша", 500, f"{D} 08:00:00")


def test_view_food_empty_day_is_empty_list(conn: sqlite3.Connection) -> None:
    assert pantry_view(conn, DAY, NOW)["food"] == []


def test_save_add_puts_quantity_in_stock_with_time_of_request(conn: sqlite3.Connection) -> None:
    reply = save_pantry(conn, {"op": "add", "item": "рис", "qty": 200, "unit": "g"}, NOW)
    assert reply == {"warning": None}
    assert amounts(conn) == {"рис": 200}
    assert [e["logged_at"] for e in list_entries(conn, "рис")] == [LOGGED]


def test_save_add_to_existing_item_sums_up(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 300)
    save_pantry(conn, {"op": "add", "item": "рис", "qty": 200, "unit": "g"}, NOW)
    assert amounts(conn) == {"рис": 500}


def test_save_add_with_until_sets_expiry(conn: sqlite3.Connection) -> None:
    save_pantry(
        conn,
        {"op": "add", "item": "кефир", "qty": 1000, "unit": "ml", "until": "2026-11-12"},
        NOW,
    )
    assert rows_by_item(conn)["кефир"]["expires_on"] == "2026-11-12"


def test_save_item_is_normalized(conn: sqlite3.Connection) -> None:
    save_pantry(conn, {"op": "add", "item": "  Куриная  Грудка ", "qty": 1, "unit": "pcs"}, NOW)
    assert amounts(conn) == {"куриная грудка": 1}


def test_save_use_takes_from_stock(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 500)
    reply = save_pantry(conn, {"op": "use", "item": "рис", "qty": 50, "unit": "g"}, NOW)
    assert reply == {"warning": None}
    assert amounts(conn) == {"рис": 450}


def test_save_use_more_than_stock_answers_warning_and_zeroes(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 100)
    reply = save_pantry(conn, {"op": "use", "item": "рис", "qty": 150, "unit": "g"}, NOW)
    assert "остаток 0" in reply["warning"]
    assert amounts(conn) == {}


def test_save_set_replaces_stock(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 500)
    save_pantry(conn, {"op": "set", "item": "рис", "qty": 120, "unit": "g"}, NOW)
    assert amounts(conn) == {"рис": 120}


def test_save_spoil_without_qty_writes_off_whole_expired_stock(conn: sqlite3.Connection) -> None:
    put(conn, "молоко", 700, "ml", until="2026-11-06")
    reply = save_pantry(conn, {"op": "spoil", "item": "молоко", "unit": "ml"}, NOW)
    assert reply == {"warning": None}
    assert amounts(conn) == {}


def test_save_spoil_without_qty_keeps_fresh_batch(conn: sqlite3.Connection) -> None:
    put(conn, "молоко", 700, "ml", until="2026-11-06")
    put(conn, "молоко", 300, "ml", until="2026-11-20")
    save_pantry(conn, {"op": "spoil", "item": "молоко", "unit": "ml"}, NOW)
    assert amounts(conn) == {"молоко": 300}


def test_save_spoil_without_qty_of_fresh_item_is_rejected_and_nothing_written(
    conn: sqlite3.Connection,
) -> None:
    put(conn, "молоко", 700, "ml", until="2026-11-20")
    before = len(list_entries(conn, "молоко"))
    with pytest.raises(MarkError, match="нет просроченного остатка"):
        save_pantry(conn, {"op": "spoil", "item": "молоко", "unit": "ml"}, NOW)
    assert len(list_entries(conn, "молоко")) == before


def test_save_open_is_not_a_pult_op_and_writes_nothing(conn: sqlite3.Connection) -> None:
    fields = {"op": "open", "item": "рис", "qty": 0, "unit": "g", "until": "2026-12-01"}
    with pytest.raises(MarkError):
        save_pantry(conn, fields, NOW)
    assert list_entries(conn) == []


def test_save_spoil_with_qty_takes_from_fresh_stock(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 500)
    reply = save_pantry(conn, {"op": "spoil", "item": "рис", "qty": 100, "unit": "g"}, NOW)
    assert reply == {"warning": None}
    assert amounts(conn) == {"рис": 400}


def test_save_spoil_with_qty_over_stock_answers_warning(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 100)
    reply = save_pantry(conn, {"op": "spoil", "item": "рис", "qty": 150, "unit": "g"}, NOW)
    assert "остаток 0" in reply["warning"]
    assert amounts(conn) == {}


def test_save_set_zero_removes_item_from_rows(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 500)
    save_pantry(conn, {"op": "set", "item": "рис", "qty": 0, "unit": "g"}, NOW)
    assert pantry_view(conn, DAY, NOW)["rows"] == []


def test_view_after_save_shows_expired_and_after_spoil_no_row(conn: sqlite3.Connection) -> None:
    save_pantry(
        conn,
        {"op": "add", "item": "молоко", "qty": 500, "unit": "ml", "until": "2026-11-06"},
        NOW,
    )
    assert rows_by_item(conn)["молоко"]["expired"] is True
    save_pantry(conn, {"op": "spoil", "item": "молоко", "unit": "ml"}, NOW)
    assert pantry_view(conn, DAY, NOW)["rows"] == []


def test_save_other_unit_is_rejected_and_nothing_written(conn: sqlite3.Connection) -> None:
    put(conn, "рис", 500)
    with pytest.raises(MarkError, match="единица g"):
        save_pantry(conn, {"op": "add", "item": "рис", "qty": 1, "unit": "pcs"}, NOW)
    assert amounts(conn) == {"рис": 500}


@pytest.mark.parametrize(
    "fields",
    [
        {"op": "eat", "item": "рис", "qty": 1, "unit": "g"},
        {"op": "add", "item": "   ", "qty": 1, "unit": "g"},
        {"op": "add", "item": "рис", "qty": 1, "unit": "kg"},
        {"op": "add", "item": "рис", "qty": 0, "unit": "g"},
        {"op": "add", "item": "рис", "qty": -5, "unit": "g"},
        {"op": "add", "item": "рис", "qty": "abc", "unit": "g"},
        {"op": "add", "item": "рис", "qty": True, "unit": "g"},
        {"op": "add", "item": "рис", "qty": None, "unit": "g"},
        {"op": "add", "item": "рис", "unit": "g"},
        {"op": "add", "item": 5, "qty": 1, "unit": "g"},
        {"op": "add", "item": "рис", "qty": 1, "unit": "g", "until": "завтра"},
        {"op": "add", "item": "рис", "qty": 1, "unit": "g", "until": 5},
        {"op": "add", "item": "рис", "qty": 1, "unit": "g", "until": True},
        {"item": "рис", "qty": 1, "unit": "g"},
        {"op": "use", "item": "нет такого", "qty": 1, "unit": "g"},
    ],
)
def test_save_bad_payload_is_mark_error_and_writes_nothing(
    conn: sqlite3.Connection, fields: dict[str, Any]
) -> None:
    with pytest.raises(MarkError):
        save_pantry(conn, fields, NOW)
    assert list_entries(conn) == []


def test_save_error_text_goes_to_user(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError) as caught:
        save_pantry(conn, {"op": "use", "item": "нет такого", "qty": 1, "unit": "g"}, NOW)
    assert "нет дома" in str(caught.value)
