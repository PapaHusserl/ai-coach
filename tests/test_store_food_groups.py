"""Группы продуктов записи еды (шаг 24): food_group, add_food_groups, list_food_groups,
сброс групп в edit_food, словарь FOOD_GROUPS и CHECK миграции 0020."""

import sqlite3

import pytest

from ai_coach.nutrition.groups import FOOD_GROUPS, GROUP_MAX_DAYS, GROUP_MIN_DAYS
from ai_coach.store.journal import (
    add_food,
    add_food_groups,
    delete_food,
    edit_food,
    list_food_groups,
    list_food_without_groups,
    update_food,
)

DAY = "2026-10-07"
MACROS = {"kcal": 520.0, "protein_g": 31.5, "fat_g": 14.0, "carbs_g": 62.0}


def new_food(conn: sqlite3.Connection, text: str = "рыба с салатом") -> int:
    return add_food(conn, {"logged_at": f"{DAY} 08:00:00", "text": text})


def stored(conn: sqlite3.Connection, food_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT group_key FROM food_group WHERE food_id = ? ORDER BY group_key", (food_id,)
    ).fetchall()
    return [r[0] for r in rows]


def test_add_food_groups_writes_rows(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    assert add_food_groups(conn, food_id, ["fish", "greens"]) is True
    assert stored(conn, food_id) == ["fish", "greens"]


def test_add_food_groups_second_call_returns_false_and_keeps_rows(
    conn: sqlite3.Connection,
) -> None:
    food_id = new_food(conn)
    add_food_groups(conn, food_id, ["fish"])
    assert add_food_groups(conn, food_id, ["eggs", "fish"]) is False
    assert stored(conn, food_id) == ["fish"]


def test_add_food_groups_unknown_key_is_integrity_error(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_food_groups(conn, food_id, ["organ_meat"])
    assert stored(conn, food_id) == []


def test_add_food_groups_unknown_key_rolls_back_in_transaction(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError), conn:
        add_food_groups(conn, food_id, ["fish", "organ_meat"])
    assert stored(conn, food_id) == []


def test_edit_food_new_text_drops_groups(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    add_food_groups(conn, food_id, ["fish"])
    assert edit_food(conn, food_id, text="гречка") is True
    assert stored(conn, food_id) == []


def test_edit_food_new_text_keeps_other_entries_groups(conn: sqlite3.Connection) -> None:
    first = new_food(conn, "рыба")
    second = new_food(conn, "борщ")
    add_food_groups(conn, first, ["fish"])
    add_food_groups(conn, second, ["vegetables"])
    edit_food(conn, second, text="плов")
    assert stored(conn, first) == ["fish"]


def test_edit_food_only_time_keeps_groups(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    add_food_groups(conn, food_id, ["fish", "greens"])
    edit_food(conn, food_id, logged_at=f"{DAY} 09:30:00")
    assert stored(conn, food_id) == ["fish", "greens"]


def test_groups_can_be_set_again_after_text_edit(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    add_food_groups(conn, food_id, ["fish"])
    edit_food(conn, food_id, text="курица")
    assert add_food_groups(conn, food_id, ["poultry"]) is True
    assert stored(conn, food_id) == ["poultry"]


def test_list_food_groups_returns_day_and_key_in_range(conn: sqlite3.Connection) -> None:
    inside = new_food(conn)
    outside = add_food(conn, {"logged_at": "2026-10-20 08:00:00", "text": "яйца"})
    add_food_groups(conn, inside, ["fish"])
    add_food_groups(conn, outside, ["eggs"])
    rows = list_food_groups(conn, DAY, DAY)
    assert [(r["food_id"], r["day"], r["group_key"]) for r in rows] == [(inside, DAY, "fish")]


def test_list_food_groups_skips_deleted_entries(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    add_food_groups(conn, food_id, ["fish"])
    delete_food(conn, food_id, f"{DAY} 12:00:00")
    assert list_food_groups(conn, DAY, DAY) == []


def counted_food(conn: sqlite3.Connection, day: str = DAY, time: str = "08:00:00") -> int:
    food_id = add_food(conn, {"logged_at": f"{day} {time}", "text": "еда"})
    update_food(conn, food_id, MACROS)
    return food_id


def test_without_groups_lists_counted_entry_without_groups(conn: sqlite3.Connection) -> None:
    food_id = counted_food(conn)
    assert [r["id"] for r in list_food_without_groups(conn, DAY, DAY)] == [food_id]


def test_without_groups_skips_entry_with_groups(conn: sqlite3.Connection) -> None:
    food_id = counted_food(conn)
    add_food_groups(conn, food_id, ["fish"])
    assert list_food_without_groups(conn, DAY, DAY) == []


def test_without_groups_skips_entry_without_macros(conn: sqlite3.Connection) -> None:
    new_food(conn)
    assert list_food_without_groups(conn, DAY, DAY) == []


def test_without_groups_skips_deleted_entry(conn: sqlite3.Connection) -> None:
    food_id = counted_food(conn)
    delete_food(conn, food_id, f"{DAY} 12:00:00")
    assert list_food_without_groups(conn, DAY, DAY) == []


def test_without_groups_skips_entry_out_of_range(conn: sqlite3.Connection) -> None:
    counted_food(conn, "2026-10-20")
    assert list_food_without_groups(conn, DAY, DAY) == []


def test_without_groups_includes_both_range_bounds(conn: sqlite3.Connection) -> None:
    first = counted_food(conn, "2026-10-07", "00:00:00")
    last = counted_food(conn, "2026-10-09", "23:59:59")
    assert [r["id"] for r in list_food_without_groups(conn, "2026-10-07", "2026-10-09")] == [
        first,
        last,
    ]


def test_without_groups_ordered_by_logged_at(conn: sqlite3.Connection) -> None:
    late = counted_food(conn, DAY, "20:00:00")
    early = counted_food(conn, DAY, "07:00:00")
    assert [r["id"] for r in list_food_without_groups(conn, DAY, DAY)] == [early, late]


def test_food_groups_has_eleven_keys() -> None:
    assert len(FOOD_GROUPS) == 11


def test_food_groups_has_no_organ_meat() -> None:
    assert "organ_meat" not in FOOD_GROUPS


def test_threshold_keys_are_known_groups() -> None:
    assert set(GROUP_MIN_DAYS) <= set(FOOD_GROUPS)
    assert set(GROUP_MAX_DAYS) <= set(FOOD_GROUPS)


@pytest.mark.parametrize("key", ["poultry", "eggs", "fruit_berries", "whole_grains"])
def test_groups_without_threshold(key: str) -> None:
    assert key not in GROUP_MIN_DAYS
    assert key not in GROUP_MAX_DAYS


def test_start_thresholds() -> None:
    assert GROUP_MIN_DAYS == {
        "fish": 2,
        "legumes": 2,
        "greens": 5,
        "vegetables": 5,
        "dairy": 5,
        "nuts_seeds": 3,
    }
    assert GROUP_MAX_DAYS == {"red_meat": 3}


@pytest.mark.parametrize("key", sorted(FOOD_GROUPS))
def test_migration_check_accepts_every_food_group(conn: sqlite3.Connection, key: str) -> None:
    food_id = new_food(conn)
    conn.execute("INSERT INTO food_group (food_id, group_key) VALUES (?, ?)", (food_id, key))
    assert stored(conn, food_id) == [key]


def test_migration_check_rejects_organ_meat(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO food_group (food_id, group_key) VALUES (?, 'organ_meat')", (food_id,)
        )


def test_migration_primary_key_rejects_duplicate(conn: sqlite3.Connection) -> None:
    food_id = new_food(conn)
    conn.execute("INSERT INTO food_group (food_id, group_key) VALUES (?, 'fish')", (food_id,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO food_group (food_id, group_key) VALUES (?, 'fish')", (food_id,))
