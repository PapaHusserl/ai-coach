import contextlib
import sqlite3
from datetime import date

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, rows, tool_names

from ai_coach.store.journal import add_food, add_weight, list_food

TOOL = "save_food_nutrition"
DAY = "2026-10-07"
MACROS = {"kcal": 520.0, "protein_g": 31.5, "fat_g": 14.0, "carbs_g": 62.0}


def new_food(conn: sqlite3.Connection, text: str = "овсянка с бананом") -> int:
    return add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": text})


def food(conn: sqlite3.Connection) -> list[dict[str, object]]:
    return list_food(conn, "2000-01-01", "2100-01-01")


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert TOOL in tool_names(conn)


def test_macros_are_saved_to_entry(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, TOOL, food_id=food_id, groups=[], **MACROS)
    row = food(conn)[0]
    assert {k: row[k] for k in MACROS} == MACROS


def test_text_and_time_stay_unchanged(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, TOOL, food_id=food_id, groups=[], **MACROS)
    row = food(conn)[0]
    assert (row["id"], row["text"], row["logged_at"]) == (
        food_id,
        "овсянка с бананом",
        f"{DAY} 09:00:00",
    )


def test_other_entries_are_not_touched(conn: sqlite3.Connection) -> None:
    first = new_food(conn, "каша")
    second = new_food(conn, "борщ")
    call(conn, TOOL, food_id=second, groups=[], **MACROS)
    by_id = {r["id"]: r for r in food(conn)}
    assert by_id[first]["kcal"] is None
    assert by_id[second]["kcal"] == 520.0


def test_weights_are_not_touched(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": f"{DAY} 07:00:00", "weight_kg": 81.7})
    food_id = new_food(conn)
    call(conn, TOOL, food_id=food_id, groups=[], **MACROS)
    assert conn.execute("SELECT weight_kg FROM weight_log").fetchall()[0][0] == 81.7


def test_zero_macros_are_allowed(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn, "вода")
    call(conn, TOOL, food_id=food_id, groups=[], kcal=0, protein_g=0, fat_g=0, carbs_g=0)
    assert food(conn)[0]["kcal"] == 0


def test_unknown_entry_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="нет"):
        call(conn, TOOL, food_id=999, groups=[], **MACROS)
    assert food(conn) == []


@pytest.mark.parametrize("field", list(MACROS))
def test_negative_value_is_rejected(conn: sqlite3.Connection, field: str) -> None:
    food_id = new_food(conn)
    with pytest.raises(ToolError):
        call(conn, TOOL, food_id=food_id, groups=[], **{**MACROS, field: -1})
    assert food(conn)[0]["kcal"] is None


@pytest.mark.parametrize("field", list(MACROS))
def test_absurdly_large_value_is_rejected(conn: sqlite3.Connection, field: str) -> None:
    food_id = new_food(conn)
    with pytest.raises(ToolError):
        call(conn, TOOL, food_id=food_id, groups=[], **{**MACROS, field: 1e9})
    assert food(conn)[0]["kcal"] is None


@pytest.mark.parametrize("field", list(MACROS))
def test_missing_value_is_rejected(conn: sqlite3.Connection, field: str) -> None:
    food_id = new_food(conn)
    args = {k: v for k, v in MACROS.items() if k != field}
    with pytest.raises(Exception):  # noqa: B017 - схема MCP или ToolError
        call(conn, TOOL, food_id=food_id, groups=[], **args)
    assert food(conn)[0]["kcal"] is None


def test_tool_cannot_rewrite_text_or_time(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    with contextlib.suppress(Exception):
        call(
            conn, TOOL, food_id=food_id, groups=[], **MACROS, text="подмена", logged_at="2000-01-01"
        )
    row = food(conn)[0]
    assert (row["text"], row["logged_at"]) == ("овсянка с бананом", f"{DAY} 09:00:00")


def test_tool_does_not_create_entries(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, TOOL, food_id=food_id, groups=[], **MACROS)
    assert len(food(conn)) == 1


def test_macros_are_visible_in_get_food(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, TOOL, food_id=food_id, groups=[], **MACROS)
    row = rows(conn, "get_food", start=DAY, end=DAY)[0]
    assert (row["kcal"], row["protein_g"]) == (520.0, 31.5)


def test_macros_are_visible_in_morning_snapshot(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, TOOL, food_id=food_id, groups=[], **MACROS)
    row = call(conn, "get_morning_snapshot", date=DAY)["food_today"]["rows"][0]
    assert (row["kcal"], row["carbs_g"]) == (520.0, 62.0)


def test_snapshot_shows_weight_and_food_added_today(conn: sqlite3.Connection) -> None:
    today = date.today().isoformat()
    add_weight(conn, {"measured_at": f"{today} 07:00:00", "weight_kg": 80.3})
    add_food(conn, {"logged_at": f"{today} 08:00:00", "text": "творог"})
    snapshot = call(conn, "get_morning_snapshot", date=today)
    assert [r["weight_kg"] for r in snapshot["weights"]["rows"]] == [80.3]
    assert [r["text"] for r in snapshot["food_today"]["rows"]] == ["творог"]


def test_snapshot_food_today_has_only_that_day(conn: sqlite3.Connection) -> None:
    add_food(conn, {"logged_at": "2026-10-06 20:00:00", "text": "вчерашний ужин"})
    new_food(conn, "сегодняшняя каша")
    texts = [r["text"] for r in call(conn, "get_morning_snapshot", date=DAY)["food_today"]["rows"]]
    assert texts == ["сегодняшняя каша"]


def test_already_counted_entry_is_not_overwritten(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, TOOL, food_id=food_id, groups=[], **MACROS)
    with pytest.raises(ToolError, match="уже посчитано"):
        call(conn, TOOL, food_id=food_id, groups=[], **{**MACROS, "kcal": 1.0})
    assert food(conn)[0]["kcal"] == 520.0


def test_pending_lists_only_entries_without_macros(conn: sqlite3.Connection) -> None:
    done = new_food(conn, "каша")
    new_food(conn, "борщ")
    call(conn, TOOL, food_id=done, groups=[], **MACROS)
    assert [r["text"] for r in rows(conn, "get_food_pending")] == ["борщ"]


def test_pending_includes_older_days_oldest_first(conn: sqlite3.Connection) -> None:
    add_food(conn, {"logged_at": "2026-10-05 20:00:00", "text": "позавчера"})
    new_food(conn, "сегодня")
    add_food(conn, {"logged_at": "2026-10-06 20:00:00", "text": "вчера"})
    assert [r["text"] for r in rows(conn, "get_food_pending")] == ["позавчера", "вчера", "сегодня"]


def test_pending_is_empty_when_all_counted(conn: sqlite3.Connection) -> None:
    call(conn, TOOL, food_id=new_food(conn), groups=[], **MACROS)
    assert rows(conn, "get_food_pending") == []
