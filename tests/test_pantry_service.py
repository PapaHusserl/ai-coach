import sqlite3

import pytest

from ai_coach.pantry.service import missing, record, stock

T1 = "2026-10-01T10:00:00"
T2 = "2026-10-02T10:00:00"
T3 = "2026-10-03T10:00:00"


def amounts(conn: sqlite3.Connection) -> dict[str, float]:
    return {row["item"]: row["qty"] for row in stock(conn)}


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT count(*) FROM pantry_log").fetchone()[0]


def test_add_then_use_leaves_the_rest(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", T1)
    record(conn, "use", "курица", 200, "g", T2)
    assert amounts(conn) == {"курица": 300}


def test_stock_row_has_item_qty_and_unit(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", T1)
    row = stock(conn)[0]
    assert (row["item"], row["qty"], row["unit"]) == ("курица", 500, "g")


def test_set_replaces_the_stock(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", T1)
    record(conn, "set", "курица", 1000, "g", T2)
    assert amounts(conn) == {"курица": 1000}


def test_entries_before_set_do_not_matter(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", T1)
    record(conn, "use", "курица", 100, "g", T1)
    record(conn, "set", "курица", 1000, "g", T2)
    record(conn, "add", "курица", 50, "g", T3)
    assert amounts(conn) == {"курица": 1050}


def test_set_to_zero_removes_item_from_stock(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", T1)
    record(conn, "set", "курица", 0, "g", T2)
    assert amounts(conn) == {}


def test_item_is_normalized_to_lower_case_without_extra_spaces(conn: sqlite3.Connection) -> None:
    record(conn, "add", "Курица ", 500, "g", T1)
    record(conn, "add", "курица", 100, "g", T2)
    assert amounts(conn) == {"курица": 600}


def test_inner_spaces_are_collapsed(conn: sqlite3.Connection) -> None:
    record(conn, "add", "рис  басмати", 100, "g", T1)
    record(conn, "add", " рис басмати", 100, "g", T2)
    assert amounts(conn) == {"рис басмати": 200}


def test_synonyms_are_not_merged(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 500, "g", T1)
    record(conn, "add", "куриная грудка", 300, "g", T1)
    assert amounts(conn) == {"курица": 500, "куриная грудка": 300}


def test_other_unit_for_known_item_is_an_error_and_writes_nothing(
    conn: sqlite3.Connection,
) -> None:
    record(conn, "add", "курица", 500, "g", T1)
    with pytest.raises(ValueError):
        record(conn, "add", "курица", 2, "pcs", T2)
    assert count(conn) == 1


@pytest.mark.parametrize("op", ["add", "use"])
@pytest.mark.parametrize("qty", [0, -5])
def test_add_and_use_need_positive_qty(conn: sqlite3.Connection, op: str, qty: float) -> None:
    with pytest.raises(ValueError):
        record(conn, op, "курица", qty, "g", T1)
    assert count(conn) == 0


def test_set_with_negative_qty_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        record(conn, "set", "курица", -1, "g", T1)
    assert count(conn) == 0


def test_unknown_unit_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        record(conn, "add", "курица", 1, "kg", T1)
    assert count(conn) == 0


def test_unknown_op_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        record(conn, "delete", "курица", 1, "g", T1)
    assert count(conn) == 0


def test_empty_item_is_an_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        record(conn, "add", "   ", 1, "g", T1)
    assert count(conn) == 0


def test_use_more_than_stock_gives_zero_and_warning_without_exception(
    conn: sqlite3.Connection,
) -> None:
    record(conn, "add", "курица", 100, "g", T1)
    warnings = record(conn, "use", "курица", 300, "g", T2)
    assert warnings
    assert amounts(conn) == {}


def test_normal_use_has_no_warnings(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 100, "g", T1)
    assert not record(conn, "use", "курица", 50, "g", T2)


def test_overuse_does_not_become_debt_for_next_add(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 100, "g", T1)
    record(conn, "use", "курица", 300, "g", T2)
    record(conn, "set", "курица", 50, "g", T3)
    assert amounts(conn) == {"курица": 50}


def test_stock_of_empty_pantry_is_empty(conn: sqlite3.Connection) -> None:
    assert stock(conn) == []


def test_missing_lists_what_to_buy(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 200, "g", T1)
    need = [
        {"item": "курица", "qty": 300, "unit": "g"},
        {"item": "рис", "qty": 100, "unit": "g"},
    ]
    result = {r["item"]: (r["qty"], r["unit"]) for r in missing(conn, need)}
    assert result == {"курица": (100, "g"), "рис": (100, "g")}


def test_missing_is_empty_when_everything_is_there(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 300, "g", T1)
    record(conn, "add", "рис", 100, "g", T1)
    need = [
        {"item": "курица", "qty": 300, "unit": "g"},
        {"item": "рис", "qty": 100, "unit": "g"},
    ]
    assert missing(conn, need) == []


def test_missing_normalizes_item_names(conn: sqlite3.Connection) -> None:
    record(conn, "add", "курица", 300, "g", T1)
    assert missing(conn, [{"item": "Курица ", "qty": 300, "unit": "g"}]) == []
