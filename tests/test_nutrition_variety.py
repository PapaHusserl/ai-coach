"""variety_week(conn, monday): дни с группой за неделю Пн-Вс, low/high по порогам (шаг 24)."""

import sqlite3

from ai_coach.nutrition.groups import FOOD_GROUPS
from ai_coach.nutrition.variety import variety_week
from ai_coach.store.journal import add_food, add_food_groups, delete_food

MON = "2026-10-12"


def meal(
    conn: sqlite3.Connection, day: str, groups: list[str], time: str = "12:00:00"
) -> int:
    food_id = add_food(conn, {"logged_at": f"{day} {time}", "text": "еда"})
    if groups:
        add_food_groups(conn, food_id, groups)
    return food_id


def days(*numbers: int) -> list[str]:
    return [f"2026-10-{12 + n:02d}" for n in numbers]


def fill_ok(conn: sqlite3.Connection) -> None:
    """Все группы с порогами в норме: каждая группа в 5 дней, красное мясо в 3."""
    for day in days(0, 1, 2, 3, 4):
        meal(conn, day, ["fish", "legumes", "greens", "vegetables", "dairy", "nuts_seeds"])
    for day in days(0, 1, 2):
        meal(conn, day, ["red_meat"], "19:00:00")


def low_groups(result: dict) -> dict[str, dict]:
    return {item["group"]: item for item in result["low"]}


def test_fish_one_day_is_low(conn: sqlite3.Connection) -> None:
    meal(conn, days(0)[0], ["fish"])
    item = low_groups(variety_week(conn, MON))["fish"]
    assert (item["days"], item["min_days"]) == (1, 2)


def test_low_nutrients_come_from_food_groups(conn: sqlite3.Connection) -> None:
    meal(conn, days(0)[0], ["fish"])
    item = low_groups(variety_week(conn, MON))["fish"]
    assert item["nutrients"] == list(FOOD_GROUPS["fish"][1])


def test_legumes_two_days_not_low(conn: sqlite3.Connection) -> None:
    for day in days(0, 3):
        meal(conn, day, ["legumes"])
    result = variety_week(conn, MON)
    assert "legumes" not in low_groups(result)
    assert result["groups"]["legumes"] == 2


def test_red_meat_four_days_is_high(conn: sqlite3.Connection) -> None:
    for day in days(0, 1, 2, 3):
        meal(conn, day, ["red_meat"])
    assert variety_week(conn, MON)["high"] == [{"group": "red_meat", "days": 4, "max_days": 3}]


def test_red_meat_three_days_not_high(conn: sqlite3.Connection) -> None:
    for day in days(0, 1, 2):
        meal(conn, day, ["red_meat"])
    assert variety_week(conn, MON)["high"] == []


def test_group_without_threshold_is_counted_but_not_low(conn: sqlite3.Connection) -> None:
    meal(conn, days(0)[0], ["fish"])
    result = variety_week(conn, MON)
    assert result["groups"]["eggs"] == 0
    assert "eggs" not in low_groups(result)


def test_groups_has_all_keys(conn: sqlite3.Connection) -> None:
    meal(conn, days(0)[0], ["fish"])
    assert set(variety_week(conn, MON)["groups"]) == set(FOOD_GROUPS)


def test_all_in_norm_gives_no_signals(conn: sqlite3.Connection) -> None:
    fill_ok(conn)
    result = variety_week(conn, MON)
    assert (result["low"], result["high"]) == ([], [])


def test_empty_week_has_no_signals(conn: sqlite3.Connection) -> None:
    result = variety_week(conn, MON)
    assert (result["days_with_data"], result["low"], result["high"]) == (0, [], [])
    assert set(result["groups"]) == set(FOOD_GROUPS)


def test_days_with_data_counts_days_with_entries(conn: sqlite3.Connection) -> None:
    meal(conn, days(0)[0], ["fish"])
    meal(conn, days(0)[0], [], "19:00:00")
    meal(conn, days(2)[0], [])
    assert variety_week(conn, MON)["days_with_data"] == 2


def test_entries_without_groups_still_make_week_with_data(conn: sqlite3.Connection) -> None:
    meal(conn, days(1)[0], [])
    result = variety_week(conn, MON)
    assert result["days_with_data"] == 1
    assert "fish" in low_groups(result)


def test_deleted_entry_is_not_counted(conn: sqlite3.Connection) -> None:
    meal(conn, days(0)[0], ["fish"])
    gone = meal(conn, days(1)[0], ["fish"])
    delete_food(conn, gone, "2026-10-14 10:00:00")
    result = variety_week(conn, MON)
    assert result["groups"]["fish"] == 1
    assert result["days_with_data"] == 1


def test_two_fish_entries_same_day_count_one_day(conn: sqlite3.Connection) -> None:
    meal(conn, days(0)[0], ["fish"], "08:00:00")
    meal(conn, days(0)[0], ["fish"], "20:00:00")
    assert variety_week(conn, MON)["groups"]["fish"] == 1


def test_late_evening_entry_stays_on_its_calendar_day(conn: sqlite3.Connection) -> None:
    meal(conn, days(0)[0], ["fish"], "23:30:00")
    meal(conn, days(1)[0], ["fish"], "01:00:00")
    assert variety_week(conn, MON)["groups"]["fish"] == 2


def test_week_bounds_are_monday_to_sunday(conn: sqlite3.Connection) -> None:
    meal(conn, "2026-10-11", ["fish"])  # воскресенье до
    meal(conn, "2026-10-12", ["fish"])  # понедельник
    meal(conn, "2026-10-18", ["fish"])  # воскресенье
    meal(conn, "2026-10-19", ["fish"])  # понедельник после
    result = variety_week(conn, MON)
    assert result["groups"]["fish"] == 2
    assert result["days_with_data"] == 2


def test_accepts_date_object(conn: sqlite3.Connection) -> None:
    from datetime import date

    meal(conn, MON, ["fish"])
    assert variety_week(conn, date(2026, 10, 12))["groups"]["fish"] == 1
