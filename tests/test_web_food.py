import json
import sqlite3
from typing import Any

import pytest

from ai_coach.store.journal import list_food, list_food_groups, list_food_pending
from ai_coach.web.errors import MarkError
from ai_coach.web.food import save_food

D = "2026-11-08"
BASE = {"event_id": 5, "date": D, "logged_at": f"{D} 09:00:00"}


def test_text_goes_to_food_log_with_event_id_and_time(conn: sqlite3.Connection) -> None:
    food_id = save_food(conn, {"text": "  овсянка с бананом "}, BASE)
    [row] = list_food(conn, D, D)
    assert row["id"] == food_id
    assert (row["event_id"], row["logged_at"], row["text"]) == (
        5,
        f"{D} 09:00:00",
        "овсянка с бананом",
    )


def test_text_entry_has_no_nutrition_and_waits_for_coach_food(conn: sqlite3.Connection) -> None:
    save_food(conn, {"text": "борщ"}, BASE)
    [row] = list_food_pending(conn)
    assert (row["kcal"], row["protein_g"], row["fat_g"], row["carbs_g"]) == (None, None, None, None)


@pytest.mark.parametrize("fields", [{}, {"text": None}, {"text": ""}, {"text": "   "}, {"text": 5}])
def test_empty_text_is_rejected_and_nothing_written(
    conn: sqlite3.Connection, fields: dict[str, Any]
) -> None:
    with pytest.raises(MarkError):
        save_food(conn, fields, BASE)
    assert list_food(conn, D, D) == []


def test_two_entries_for_one_item_are_both_kept(conn: sqlite3.Connection) -> None:
    save_food(conn, {"text": "яйца"}, BASE)
    save_food(conn, {"text": "кофе"}, {**BASE, "logged_at": f"{D} 09:10:00"})
    assert [r["text"] for r in list_food(conn, D, D)] == ["яйца", "кофе"]


# Партия 6: запись варианта блюда (offer_id). Варианты кладём в таблицу напрямую.
ITEMS = [
    {"what": "яйца", "qty": "2 шт", "kcal": 150, "protein_g": 12, "fat_g": 10, "carbs_g": 1},
    {"what": "хлеб", "qty": "50 г", "kcal": 120, "protein_g": 4, "fat_g": 1, "carbs_g": 24},
]


def put_offer(
    conn: sqlite3.Connection,
    event_id: int = 5,
    name: str = "Омлет с хлебом",
    position: int = 1,
    day: str = D,
) -> int:
    sql = (
        "INSERT INTO meal_offer (event_id, date, position, name, items_json, kcal, protein_g, "
        "fat_g, carbs_g, groups_json) VALUES (?, ?, ?, ?, ?, 270, 16, 11, 25, ?)"
    )
    cursor = conn.execute(
        sql,
        (event_id, day, position, name, json.dumps(ITEMS), json.dumps(["eggs", "whole_grains"])),
    )
    conn.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def test_offer_goes_to_food_log_with_nutrition_event_id_and_time(conn: sqlite3.Connection) -> None:
    offer_id = put_offer(conn)
    food_id = save_food(conn, {"offer_id": offer_id}, BASE)
    [row] = list_food(conn, D, D)
    assert row["id"] == food_id
    assert (row["event_id"], row["logged_at"]) == (5, f"{D} 09:00:00")
    assert row["text"] == "Омлет с хлебом: яйца 2 шт, хлеб 50 г"
    assert (row["kcal"], row["protein_g"], row["fat_g"], row["carbs_g"]) == (270, 16, 11, 25)


def test_offer_entry_is_not_pending_for_coach_food(conn: sqlite3.Connection) -> None:
    save_food(conn, {"offer_id": put_offer(conn)}, BASE)
    assert list_food_pending(conn) == []


def test_offer_entry_gets_groups(conn: sqlite3.Connection) -> None:
    food_id = save_food(conn, {"offer_id": put_offer(conn)}, BASE)
    groups = {(r["food_id"], r["group_key"]) for r in list_food_groups(conn, D, D)}
    assert groups == {(food_id, "eggs"), (food_id, "whole_grains")}


def test_offer_of_another_item_is_rejected_and_nothing_written(conn: sqlite3.Connection) -> None:
    offer_id = put_offer(conn, event_id=6)
    with pytest.raises(MarkError):
        save_food(conn, {"offer_id": offer_id}, BASE)
    assert list_food(conn, D, D) == []


def test_offer_of_other_day_is_rejected_and_nothing_written(conn: sqlite3.Connection) -> None:
    offer_id = put_offer(conn, day="2026-11-07")
    with pytest.raises(MarkError):
        save_food(conn, {"offer_id": offer_id}, BASE)
    assert list_food(conn, D, D) == []


@pytest.mark.parametrize("offer_id", [999, 0, -1, "1", 1.5, True])
def test_missing_or_bad_offer_id_is_rejected(conn: sqlite3.Connection, offer_id: Any) -> None:
    put_offer(conn)
    with pytest.raises(MarkError):
        save_food(conn, {"offer_id": offer_id}, BASE)
    assert list_food(conn, D, D) == []


def test_text_and_offer_together_are_rejected_and_nothing_written(
    conn: sqlite3.Connection,
) -> None:
    offer_id = put_offer(conn)
    with pytest.raises(MarkError):
        save_food(conn, {"offer_id": offer_id, "text": "борщ"}, BASE)
    assert list_food(conn, D, D) == []


def test_offer_can_be_taken_twice_as_two_entries(conn: sqlite3.Connection) -> None:
    offer_id = put_offer(conn)
    save_food(conn, {"offer_id": offer_id}, BASE)
    save_food(conn, {"offer_id": offer_id}, {**BASE, "logged_at": f"{D} 09:10:00"})
    assert len(list_food(conn, D, D)) == 2
