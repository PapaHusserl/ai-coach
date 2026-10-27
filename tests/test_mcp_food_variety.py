"""MCP шага 24: save_food_nutrition(groups), get_food_variety, get_nutrient_norms."""

import asyncio
import sqlite3

import pytest
from fake_clock import freeze
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, db_file, rows, tool_names

from ai_coach.mcp_server import build_server
from ai_coach.nutrition.groups import FOOD_GROUPS
from ai_coach.nutrition.norms import norms_table
from ai_coach.store.journal import (
    add_food,
    add_food_groups,
    delete_food,
    edit_food,
    list_food,
    update_food,
)

SAVE = "save_food_nutrition"
SAVE_GROUPS = "save_food_groups"
WITHOUT = "get_food_without_groups"
DAY = "2026-10-07"
MACROS = {"kcal": 520.0, "protein_g": 31.5, "fat_g": 14.0, "carbs_g": 62.0}
WED = "2026-10-14 12:00:00"  # неделя Пн 2026-10-12


def new_food(conn: sqlite3.Connection, day: str = DAY) -> int:
    return add_food(conn, {"logged_at": f"{day} 09:00:00", "text": "рыба с салатом"})


def stored(conn: sqlite3.Connection, food_id: int) -> list[str]:
    found = conn.execute(
        "SELECT group_key FROM food_group WHERE food_id = ? ORDER BY group_key", (food_id,)
    ).fetchall()
    return [r[0] for r in found]


def kcal(conn: sqlite3.Connection, food_id: int) -> float | None:
    rows = list_food(conn, "2000-01-01", "2100-01-01")
    return next(r["kcal"] for r in rows if r["id"] == food_id)


def test_tools_exist(conn: sqlite3.Connection) -> None:
    assert {"get_food_variety", "get_nutrient_norms"} <= tool_names(conn)


# --- save_food_nutrition(groups) ---


def test_save_with_groups_writes_macros_and_groups(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, SAVE, food_id=food_id, groups=["fish", "greens"], **MACROS)
    assert kcal(conn, food_id) == 520.0
    assert stored(conn, food_id) == ["fish", "greens"]


def test_save_schema_requires_groups(conn: sqlite3.Connection) -> None:
    server = build_server(db_file(conn))
    tool = next(t for t in asyncio.run(server.list_tools()) if t.name == SAVE)
    assert "groups" in tool.input_schema["required"]


def test_save_without_groups_is_error_and_writes_nothing(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    with pytest.raises(ToolError):
        call(conn, SAVE, food_id=food_id, **MACROS)
    assert kcal(conn, food_id) is None
    assert stored(conn, food_id) == []


def test_save_with_empty_groups_writes_no_groups(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, SAVE, food_id=food_id, groups=[], **MACROS)
    assert kcal(conn, food_id) == 520.0
    assert stored(conn, food_id) == []


def test_save_unknown_group_is_error_listing_allowed(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    with pytest.raises(ToolError) as error:
        call(conn, SAVE, food_id=food_id, groups=["fish", "organ_meat"], **MACROS)
    text = str(error.value)
    assert "organ_meat" in text
    assert all(key in text for key in FOOD_GROUPS)


def test_save_unknown_group_leaves_macros_empty(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    with pytest.raises(ToolError):
        call(conn, SAVE, food_id=food_id, groups=["fish", "organ_meat"], **MACROS)
    assert kcal(conn, food_id) is None
    assert stored(conn, food_id) == []


def test_save_on_already_calculated_entry_is_error(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, SAVE, food_id=food_id, groups=["fish"], **MACROS)
    with pytest.raises(ToolError, match="уже посчитано"):
        call(conn, SAVE, food_id=food_id, groups=["eggs"], **MACROS)
    assert stored(conn, food_id) == ["fish"]


def test_entry_with_macros_but_no_groups_is_already_calculated(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    update_food(conn, food_id, MACROS)
    with pytest.raises(ToolError, match="уже посчитано"):
        call(conn, SAVE, food_id=food_id, groups=["fish"], **MACROS)
    assert stored(conn, food_id) == []


def test_text_edit_allows_recalculation_with_new_groups(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    call(conn, SAVE, food_id=food_id, groups=["fish"], **MACROS)
    edit_food(conn, food_id, text="курица")
    call(conn, SAVE, food_id=food_id, groups=["poultry"], **MACROS)
    assert stored(conn, food_id) == ["poultry"]


# --- get_food_without_groups / save_food_groups (партия 5) ---


def counted(conn: sqlite3.Connection, day: str = DAY, time: str = "09:00:00") -> int:
    food_id = add_food(conn, {"logged_at": f"{day} {time}", "text": "рыба с салатом"})
    update_food(conn, food_id, MACROS)
    return food_id


def test_new_tools_exist(conn: sqlite3.Connection) -> None:
    assert {WITHOUT, SAVE_GROUPS} <= tool_names(conn)


def test_without_groups_rows_have_fields(conn: sqlite3.Connection) -> None:
    food_id = counted(conn)
    row = rows(conn, WITHOUT, start=DAY, end=DAY)[0]
    assert (row["id"], row["logged_at"], row["text"], row["kcal"]) == (
        food_id,
        f"{DAY} 09:00:00",
        "рыба с салатом",
        520.0,
    )


def test_without_groups_hides_marked_entry(conn: sqlite3.Connection) -> None:
    food_id = counted(conn)
    add_food_groups(conn, food_id, ["fish"])
    assert rows(conn, WITHOUT, start=DAY, end=DAY) == []


def test_without_groups_end_before_start_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, WITHOUT, start="2026-10-08", end="2026-10-07")


def test_without_groups_too_long_period_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, WITHOUT, start="2026-01-01", end="2026-12-31")


def test_without_groups_caps_at_sixty_oldest_first(conn: sqlite3.Connection) -> None:
    ids = [counted(conn, DAY, f"{h:02d}:{m:02d}:00") for h in range(7, 9) for m in range(0, 31)]
    result = call(conn, WITHOUT, start=DAY, end=DAY)
    assert result["truncated"] is True
    assert [r["id"] for r in result["rows"]] == ids[:60]


def test_save_groups_writes_groups_and_keeps_macros(conn: sqlite3.Connection) -> None:
    food_id = counted(conn)
    before = kcal(conn, food_id)
    call(conn, SAVE_GROUPS, food_id=food_id, groups=["fish"])
    assert stored(conn, food_id) == ["fish"]
    assert kcal(conn, food_id) == before == 520.0


def test_save_groups_twice_is_error_and_keeps_rows(conn: sqlite3.Connection) -> None:
    food_id = counted(conn)
    call(conn, SAVE_GROUPS, food_id=food_id, groups=["fish"])
    with pytest.raises(ToolError, match="уже размечена"):
        call(conn, SAVE_GROUPS, food_id=food_id, groups=["eggs"])
    assert stored(conn, food_id) == ["fish"]


def test_save_groups_without_macros_points_to_save_nutrition(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    with pytest.raises(ToolError, match="save_food_nutrition"):
        call(conn, SAVE_GROUPS, food_id=food_id, groups=["fish"])
    assert stored(conn, food_id) == []


def test_save_groups_empty_list_is_error(conn: sqlite3.Connection) -> None:
    food_id = counted(conn)
    with pytest.raises(ToolError):
        call(conn, SAVE_GROUPS, food_id=food_id, groups=[])
    assert stored(conn, food_id) == []


def test_save_groups_unknown_group_lists_allowed_and_writes_nothing(
    conn: sqlite3.Connection,
) -> None:
    food_id = counted(conn)
    with pytest.raises(ToolError) as error:
        call(conn, SAVE_GROUPS, food_id=food_id, groups=["fish", "organ_meat"])
    assert all(key in str(error.value) for key in FOOD_GROUPS)
    assert stored(conn, food_id) == []


def test_save_groups_deleted_entry_is_error(conn: sqlite3.Connection) -> None:
    food_id = counted(conn)
    delete_food(conn, food_id, f"{DAY} 12:00:00")
    with pytest.raises(ToolError, match="удалена"):
        call(conn, SAVE_GROUPS, food_id=food_id, groups=["fish"])
    assert stored(conn, food_id) == []


def test_save_groups_missing_entry_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="нет"):
        call(conn, SAVE_GROUPS, food_id=999, groups=["fish"])


# --- get_food_variety ---


def test_variety_default_four_weeks_oldest_first(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, WED)
    result = call(conn, "get_food_variety")
    assert set(result) == {"rows", "truncated"}
    starts = [r["week_start"] for r in result["rows"]]
    assert starts == ["2026-09-21", "2026-09-28", "2026-10-05", "2026-10-12"]


def test_variety_only_last_week_is_partial(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, WED)
    partial = [r["partial"] for r in rows(conn, "get_food_variety")]
    assert partial == [False, False, False, True]


def test_variety_week_fields(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, WED)
    row = rows(conn, "get_food_variety", weeks=1)[0]
    assert {"week_start", "week_end", "partial", "days_with_data", "groups", "low", "high"} <= set(
        row
    )
    assert row["week_end"] == "2026-10-18"


def test_variety_counts_groups_of_current_week(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, WED)
    for day in ("2026-10-12", "2026-10-13"):
        add_food_groups(conn, new_food(conn, day), ["fish"])
    row = rows(conn, "get_food_variety", weeks=1)[0]
    assert row["groups"]["fish"] == 2
    assert row["days_with_data"] == 2
    assert "fish" not in {item["group"] for item in row["low"]}


def test_variety_empty_week_has_no_signals(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, WED)
    row = rows(conn, "get_food_variety", weeks=1)[0]
    assert (row["days_with_data"], row["low"], row["high"]) == (0, [], [])


@pytest.mark.parametrize("weeks", [1, 2, 12])
def test_variety_weeks_in_range(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch, weeks: int
) -> None:
    freeze(monkeypatch, WED)
    assert len(rows(conn, "get_food_variety", weeks=weeks)) == weeks


@pytest.mark.parametrize("weeks", [0, -1, 13, 100])
def test_variety_weeks_out_of_range_is_error(conn: sqlite3.Connection, weeks: int) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_food_variety", weeks=weeks)


# --- get_nutrient_norms ---


def test_norms_tool_returns_table_from_code(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_nutrient_norms")
    assert result["truncated"] is False
    assert result["rows"] == norms_table()


def test_norms_tool_has_twelve_rows_with_sources(conn: sqlite3.Connection) -> None:
    got = rows(conn, "get_nutrient_norms")
    assert len(got) == 12
    assert all(r["norm_source"] and r["upper_source"] and r["food_source"] for r in got)


def test_norms_tool_vitamin_d_has_iu(conn: sqlite3.Connection) -> None:
    row = next(r for r in rows(conn, "get_nutrient_norms") if r["nutrient"] == "витамин D")
    assert (row["norm_iu"], row["upper_iu"]) == (600, 600)
