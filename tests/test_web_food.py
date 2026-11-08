import sqlite3
from typing import Any

import pytest

from ai_coach.store.journal import list_food, list_food_pending
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
