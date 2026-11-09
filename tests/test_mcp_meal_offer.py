"""MCP create_meal_offers / cancel_meal_offers (П3, партия 6): варианты блюд к пункту еды."""

import json
import sqlite3
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, tool_names
from workload_fakes import coach_event

from ai_coach.store.agenda import add_event

DAY = "2026-11-07"


def meal_event(conn: sqlite3.Connection, **fields: Any) -> int:
    day = fields.pop("date", DAY)
    values = coach_event(
        kind="meal",
        title=fields.pop("title", "Завтрак"),
        date=day,
        start_at=f"{day}T08:00:00",
        end_at=f"{day}T09:00:00",
        **fields,
    )
    event_id = add_event(conn, values)
    conn.commit()
    return event_id


def line(what: str, kcal: float, protein: float = 10, fat: float = 5, carbs: float = 20) -> dict:
    return {
        "what": what,
        "qty": "100 г",
        "kcal": kcal,
        "protein_g": protein,
        "fat_g": fat,
        "carbs_g": carbs,
    }


def offer(name: str = "Омлет", **fields: Any) -> dict[str, Any]:
    base = {"name": name, "items": [line("яйца", 150), line("хлеб", 100)], "groups": ["eggs"]}
    return base | fields


def create(conn: sqlite3.Connection, event_id: int, offers: list[dict], day: str = DAY) -> Any:
    return call(conn, "create_meal_offers", event_id=event_id, date=day, offers=offers)


def stored(conn: sqlite3.Connection, event_id: int, day: str = DAY) -> list[sqlite3.Row]:
    sql = "SELECT * FROM meal_offer WHERE event_id = ? AND date = ? ORDER BY position"
    return conn.execute(sql, (event_id, day)).fetchall()


def test_tools_are_registered(conn: sqlite3.Connection) -> None:
    assert {"create_meal_offers", "cancel_meal_offers"} <= tool_names(conn)


def test_create_stores_offers_in_order_with_positions(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    create(conn, event_id, [offer("Омлет"), offer("Каша")])
    rows = stored(conn, event_id)
    assert [r["name"] for r in rows] == ["Омлет", "Каша"]
    assert rows[0]["position"] < rows[1]["position"]


def test_create_totals_are_sums_of_items(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    items = [line("яйца", 150, 12, 10, 1), line("хлеб", 100, 3, 1, 20)]
    create(conn, event_id, [offer(items=items)])
    [row] = stored(conn, event_id)
    assert (row["kcal"], row["protein_g"], row["fat_g"], row["carbs_g"]) == (250, 15, 11, 21)


def test_create_keeps_items_and_groups_as_json(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    create(conn, event_id, [offer(groups=["eggs", "dairy"])])
    [row] = stored(conn, event_id)
    assert [i["what"] for i in json.loads(row["items_json"])] == ["яйца", "хлеб"]
    assert json.loads(row["groups_json"]) == ["eggs", "dairy"]


def test_create_replaces_earlier_offers_of_same_item_and_day(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    create(conn, event_id, [offer("Старый 1"), offer("Старый 2")])
    create(conn, event_id, [offer("Новый")])
    assert [r["name"] for r in stored(conn, event_id)] == ["Новый"]


def test_create_does_not_touch_other_item_or_other_day(conn: sqlite3.Connection) -> None:
    first, second = meal_event(conn), meal_event(conn, title="Обед")
    third = meal_event(conn, title="Ужин", date="2026-11-08")
    create(conn, first, [offer("А")])
    create(conn, second, [offer("Б")])
    create(conn, third, [offer("В")], day="2026-11-08")
    assert [r["name"] for r in stored(conn, first)] == ["А"]
    assert [r["name"] for r in stored(conn, second)] == ["Б"]
    assert [r["name"] for r in stored(conn, third, "2026-11-08")] == ["В"]


def test_create_five_offers_is_ok_six_is_rejected(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    create(conn, event_id, [offer(f"В{n}") for n in range(5)])
    assert len(stored(conn, event_id)) == 5
    with pytest.raises(ToolError):
        create(conn, event_id, [offer(f"В{n}") for n in range(6)])
    assert len(stored(conn, event_id)) == 5


def test_create_twelve_lines_is_ok_thirteen_is_rejected(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    create(conn, event_id, [offer(items=[line(f"п{n}", 10) for n in range(12)])])
    with pytest.raises(ToolError):
        create(conn, event_id, [offer(items=[line(f"п{n}", 10) for n in range(13)])])
    assert len(stored(conn, event_id)) == 1


def test_create_for_missing_event_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        create(conn, 999, [offer()])
    assert conn.execute("SELECT COUNT(*) FROM meal_offer").fetchone()[0] == 0


def test_create_for_non_meal_item_is_rejected_and_writes_nothing(conn: sqlite3.Connection) -> None:
    event_id = add_event(
        conn,
        coach_event(kind="task", date=DAY, start_at=f"{DAY}T08:00:00", end_at=f"{DAY}T09:00:00"),
    )
    conn.commit()
    with pytest.raises(ToolError):
        create(conn, event_id, [offer()])
    assert stored(conn, event_id) == []


def test_create_on_other_date_than_item_is_rejected_and_writes_nothing(
    conn: sqlite3.Connection,
) -> None:
    event_id = meal_event(conn)
    with pytest.raises(ToolError):
        create(conn, event_id, [offer()], day="2026-11-08")
    assert stored(conn, event_id, "2026-11-08") == []


@pytest.mark.parametrize("name", ["", "   ", None])
def test_create_with_empty_or_null_name_is_rejected(conn: sqlite3.Connection, name: Any) -> None:
    event_id = meal_event(conn)
    with pytest.raises(ToolError):
        create(conn, event_id, [offer(name)])
    assert stored(conn, event_id) == []


@pytest.mark.parametrize("what", ["", "   ", None])
def test_create_with_empty_or_null_what_is_rejected(conn: sqlite3.Connection, what: Any) -> None:
    event_id = meal_event(conn)
    bad = {**line("яйца", 150), "what": what}
    with pytest.raises(ToolError):
        create(conn, event_id, [offer(items=[bad])])
    assert stored(conn, event_id) == []


@pytest.mark.parametrize("key", ["kcal", "protein_g", "fat_g", "carbs_g"])
@pytest.mark.parametrize("value", [-1, 1_000_000])
def test_create_with_nutrition_out_of_range_is_rejected(
    conn: sqlite3.Connection, key: str, value: int
) -> None:
    event_id = meal_event(conn)
    bad = {**line("яйца", 150), key: value}
    with pytest.raises(ToolError):
        create(conn, event_id, [offer(items=[bad])])
    assert stored(conn, event_id) == []


def test_create_with_unknown_group_is_rejected_and_writes_nothing(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    with pytest.raises(ToolError):
        create(conn, event_id, [offer(groups=["пончики"])])
    assert stored(conn, event_id) == []


def test_create_without_qty_is_rejected_and_writes_nothing(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    no_qty = {k: v for k, v in line("яйца", 150).items() if k != "qty"}
    with pytest.raises(ToolError):
        create(conn, event_id, [offer(items=[no_qty])])
    assert stored(conn, event_id) == []


def test_create_with_empty_qty_text_is_ok(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    create(conn, event_id, [offer(items=[{**line("яйца", 150), "qty": ""}])])
    assert len(stored(conn, event_id)) == 1


def test_create_with_empty_offers_is_rejected(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    with pytest.raises(ToolError):
        create(conn, event_id, [])


def test_cancel_removes_offers_of_item_and_day(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    create(conn, event_id, [offer("А"), offer("Б")])
    call(conn, "cancel_meal_offers", event_id=event_id, date=DAY)
    assert stored(conn, event_id) == []


def test_cancel_keeps_other_item_and_other_day(conn: sqlite3.Connection) -> None:
    first, second = meal_event(conn), meal_event(conn, title="Обед")
    third = meal_event(conn, title="Ужин", date="2026-11-08")
    create(conn, first, [offer("А")])
    create(conn, second, [offer("Б")])
    create(conn, third, [offer("В")], day="2026-11-08")
    call(conn, "cancel_meal_offers", event_id=first, date=DAY)
    assert stored(conn, first) == []
    assert stored(conn, second)[0]["name"] == "Б"
    assert stored(conn, third, "2026-11-08")[0]["name"] == "В"


def test_cancel_without_offers_does_not_fail(conn: sqlite3.Connection) -> None:
    event_id = meal_event(conn)
    call(conn, "cancel_meal_offers", event_id=event_id, date=DAY)
