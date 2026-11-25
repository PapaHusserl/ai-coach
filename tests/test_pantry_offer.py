import sqlite3

import pytest

from ai_coach.pantry.service import PantryEntry, stock
from ai_coach.pantry.service import record as save
from ai_coach.store.pantry import list_entries

T1 = "2026-11-08 08:00:00"
T2 = "2026-11-08 12:00:00"


def add(conn: sqlite3.Connection, item: str, qty: float, unit: str) -> None:
    save(conn, PantryEntry("add", item, qty, unit, T1))


def amounts(conn: sqlite3.Connection) -> dict[str, float]:
    return {row["item"]: row["qty"] for row in stock(conn)}


def use_count(conn: sqlite3.Connection) -> int:
    return len([e for e in list_entries(conn) if e["op"] == "use"])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("150 г", (150.0, "g")),
        ("200 мл", (200.0, "ml")),
        ("2 шт", (2.0, "pcs")),
        ("1,5 шт", (1.5, "pcs")),
        ("горсть", None),
        ("", None),
        ("150", None),
        ("0 г", None),
        ("0,0 г", None),
        ("0 шт", None),
    ],
)
def test_parse_qty(text: str, expected: tuple[float, str] | None) -> None:
    from ai_coach.pantry.offer import parse_qty

    assert parse_qty(text) == expected


def test_use_offer_writes_use_with_food_note_and_lowers_stock(conn: sqlite3.Connection) -> None:
    from ai_coach.pantry.offer import use_offer

    add(conn, "рис", 500, "g")
    result = use_offer(conn, [{"what": "рис", "qty": "150 г"}], 7, T2)
    assert amounts(conn) == {"рис": 350}
    [use] = [e for e in list_entries(conn) if e["op"] == "use"]
    assert use["note"] == "food:7"
    assert result == {"used": ["рис 150 г"], "skipped": [], "warnings": []}


def test_use_offer_skips_product_not_in_pantry(conn: sqlite3.Connection) -> None:
    from ai_coach.pantry.offer import use_offer

    result = use_offer(conn, [{"what": "соус", "qty": "20 г"}], 7, T2)
    assert result == {"used": [], "skipped": ["соус 20 г"], "warnings": []}
    assert list_entries(conn) == []


def test_use_offer_skips_other_unit(conn: sqlite3.Connection) -> None:
    from ai_coach.pantry.offer import use_offer

    add(conn, "молоко", 1000, "ml")
    result = use_offer(conn, [{"what": "молоко", "qty": "50 г"}], 7, T2)
    assert result["skipped"] == ["молоко 50 г"]
    assert (result["used"], use_count(conn)) == ([], 0)
    assert amounts(conn) == {"молоко": 1000}


def test_use_offer_skips_unreadable_qty(conn: sqlite3.Connection) -> None:
    from ai_coach.pantry.offer import use_offer

    add(conn, "зелень", 100, "g")
    result = use_offer(conn, [{"what": "зелень", "qty": "горсть"}], 7, T2)
    assert result["skipped"] == ["зелень горсть"]
    assert (result["used"], use_count(conn)) == ([], 0)
    assert amounts(conn) == {"зелень": 100}


def test_use_offer_more_than_stock_leaves_zero_with_warning(conn: sqlite3.Connection) -> None:
    from ai_coach.pantry.offer import use_offer

    add(conn, "рис", 100, "g")
    result = use_offer(conn, [{"what": "рис", "qty": "150 г"}], 7, T2)
    assert amounts(conn) == {}
    assert result["warnings"] == ["рис: списано больше остатка, остаток 0."]
    assert result["used"] == ["рис 150 г"]


@pytest.mark.parametrize(
    ("what", "qty", "unit", "line"),
    [
        ("соль", "0 г", "g", "соль 0 г"),
        ("соль", "0,0 г", "g", "соль 0,0 г"),
        ("яйцо", "0 шт", "pcs", "яйцо 0 шт"),
    ],
)
def test_use_offer_skips_zero_qty_without_error(
    conn: sqlite3.Connection, what: str, qty: str, unit: str, line: str
) -> None:
    from ai_coach.pantry.offer import use_offer

    add(conn, what, 100, unit)
    result = use_offer(conn, [{"what": what, "qty": qty}], 7, T2)
    assert result == {"used": [], "skipped": [line], "warnings": []}
    assert (use_count(conn), amounts(conn)) == (0, {what: 100})


def test_use_offer_product_with_zero_stock_goes_to_used_with_warning(
    conn: sqlite3.Connection,
) -> None:
    from ai_coach.pantry.offer import use_offer

    add(conn, "рис", 100, "g")
    save(conn, PantryEntry("use", "рис", 100, "g", "2026-11-08 09:00:00"))
    result = use_offer(conn, [{"what": "рис", "qty": "150 г"}], 7, T2)
    assert result["used"] == ["рис 150 г"]
    assert result["skipped"] == []
    assert result["warnings"] == ["рис: списано больше остатка, остаток 0."]
    assert use_count(conn) == 2


def test_use_offer_matches_name_by_normalize(conn: sqlite3.Connection) -> None:
    from ai_coach.pantry.offer import use_offer

    add(conn, "рис басмати", 500, "g")
    use_offer(conn, [{"what": "  Рис   Басмати ", "qty": "100 г"}], 7, T2)
    assert amounts(conn) == {"рис басмати": 400}


def test_use_offer_mixed_items_split_between_used_and_skipped(conn: sqlite3.Connection) -> None:
    from ai_coach.pantry.offer import use_offer

    add(conn, "яйцо", 10, "pcs")
    items = [{"what": "яйцо", "qty": "2 шт"}, {"what": "соус", "qty": "20 г"}]
    result = use_offer(conn, items, 7, T2)
    assert (result["used"], result["skipped"]) == (["яйцо 2 шт"], ["соус 20 г"])
    assert amounts(conn) == {"яйцо": 8}
