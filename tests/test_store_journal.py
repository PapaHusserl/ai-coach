import sqlite3
from typing import Any

import pytest

from ai_coach.store.journal import (
    add_food,
    add_sync_log,
    add_weight,
    add_who5,
    last_sync_log,
    last_who5,
    list_food,
    list_weights,
    list_who5,
    sync_runs_on,
    update_food,
)


def test_weight_roundtrip(conn: sqlite3.Connection) -> None:
    wid = add_weight(conn, {"measured_at": "2026-03-10T07:00:00", "weight_kg": 81.4})
    rows = list_weights(conn, "2026-03-10", "2026-03-10")
    row = {"id": wid, "measured_at": "2026-03-10T07:00:00", "weight_kg": 81.4, "deleted_at": None}
    assert rows == [row]


def test_weights_inclusive_by_date_sorted_by_time_then_id(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-03-09T23:59:00", "weight_kg": 1.0})
    late = add_weight(conn, {"measured_at": "2026-03-11T22:00:00", "weight_kg": 2.0})
    early = add_weight(conn, {"measured_at": "2026-03-10T00:00:00", "weight_kg": 3.0})
    same_a = add_weight(conn, {"measured_at": "2026-03-11T06:00:00", "weight_kg": 4.0})
    same_b = add_weight(conn, {"measured_at": "2026-03-11T06:00:00", "weight_kg": 5.0})
    add_weight(conn, {"measured_at": "2026-03-12T00:00:00", "weight_kg": 6.0})
    rows = list_weights(conn, "2026-03-10", "2026-03-11")
    assert [r["id"] for r in rows] == [early, same_a, same_b, late]


def test_weight_log_has_no_raw_json_column(conn: sqlite3.Connection) -> None:
    # Вес вводится руками, не из Garmin.
    columns = {r[1] for r in conn.execute("PRAGMA table_info(weight_log)").fetchall()}
    assert "raw_json" not in columns


def test_food_saved_as_raw_text_without_macros(conn: sqlite3.Connection) -> None:
    fid = add_food(conn, {"logged_at": "2026-03-10T08:00:00", "text": "овсянка, 2 яйца"})
    row = list_food(conn, "2026-03-10", "2026-03-10")[0]
    assert row["id"] == fid
    assert row["text"] == "овсянка, 2 яйца"
    assert row["kcal"] is None
    assert row["protein_g"] is None
    assert row["fat_g"] is None
    assert row["carbs_g"] is None


def test_food_update_sets_macros_keeps_text(conn: sqlite3.Connection) -> None:
    fid = add_food(conn, {"logged_at": "2026-03-10T08:00:00", "text": "каша"})
    other = add_food(conn, {"logged_at": "2026-03-10T09:00:00", "text": "чай"})
    update_food(conn, fid, {"kcal": 350.0, "protein_g": 12.0, "fat_g": 6.0, "carbs_g": 60.0})
    rows = {r["id"]: r for r in list_food(conn, "2026-03-10", "2026-03-10")}
    assert rows[fid]["text"] == "каша"
    assert rows[fid]["kcal"] == 350.0
    assert rows[fid]["protein_g"] == 12.0
    assert rows[fid]["fat_g"] == 6.0
    assert rows[fid]["carbs_g"] == 60.0
    assert rows[other]["kcal"] is None


def test_food_inclusive_by_date_sorted(conn: sqlite3.Connection) -> None:
    add_food(conn, {"logged_at": "2026-03-09T23:00:00", "text": "a"})
    dinner = add_food(conn, {"logged_at": "2026-03-11T19:00:00", "text": "b"})
    breakfast = add_food(conn, {"logged_at": "2026-03-10T08:00:00", "text": "c"})
    add_food(conn, {"logged_at": "2026-03-12T08:00:00", "text": "d"})
    rows = list_food(conn, "2026-03-10", "2026-03-11")
    assert [r["id"] for r in rows] == [breakfast, dinner]


def test_last_sync_log_empty_is_none(conn: sqlite3.Connection) -> None:
    assert last_sync_log(conn) is None


def test_last_sync_log_returns_latest_by_id(conn: sqlite3.Connection) -> None:
    add_sync_log(conn, {"started_at": "2026-03-11T00:00:00", "kind": "sync", "status": "ok"})
    last = add_sync_log(
        conn,
        {
            "started_at": "2026-03-10T00:00:00",
            "finished_at": "2026-03-10T00:01:00",
            "kind": "import",
            "status": "error",
            "message": "429",
        },
    )
    row = last_sync_log(conn)
    assert row is not None
    assert row["id"] == last
    assert row["kind"] == "import"
    assert row["status"] == "error"
    assert row["message"] == "429"
    assert row["finished_at"] == "2026-03-10T00:01:00"


# --- шаг 22: sync_runs_on ---


def test_sync_runs_on_is_zero_for_empty_log(conn: sqlite3.Connection) -> None:
    assert sync_runs_on(conn, "2026-03-10") == 0


def test_sync_runs_on_counts_sync_of_the_day_in_both_formats(conn: sqlite3.Connection) -> None:
    add_sync_log(conn, {"started_at": "2026-03-10T06:00:00", "kind": "sync", "status": "ok"})
    add_sync_log(conn, {"started_at": "2026-03-10 12:00:00", "kind": "sync", "status": "ok"})
    assert sync_runs_on(conn, "2026-03-10") == 2


def test_sync_runs_on_counts_error_status(conn: sqlite3.Connection) -> None:
    add_sync_log(conn, {"started_at": "2026-03-10 06:00:00", "kind": "sync", "status": "error"})
    assert sync_runs_on(conn, "2026-03-10") == 1


def test_sync_runs_on_ignores_import(conn: sqlite3.Connection) -> None:
    add_sync_log(conn, {"started_at": "2026-03-10 06:00:00", "kind": "import", "status": "ok"})
    assert sync_runs_on(conn, "2026-03-10") == 0


def test_sync_runs_on_ignores_other_days(conn: sqlite3.Connection) -> None:
    add_sync_log(conn, {"started_at": "2026-03-09 23:59:59", "kind": "sync", "status": "ok"})
    add_sync_log(conn, {"started_at": "2026-03-11T00:00:00", "kind": "sync", "status": "ok"})
    assert sync_runs_on(conn, "2026-03-10") == 0


# --- Н12: who5_log ---


def who5_values(
    day: str, at: str = "09:00:00", q1: int = 5, text: str | None = None
) -> dict[str, Any]:
    """Замер: q1 задаётся, остальные ответы по 1; балл сходится с суммой."""
    return {
        "date": day,
        "logged_at": f"{day} {at}",
        "q1": q1,
        "q2": 1,
        "q3": 1,
        "q4": 1,
        "q5": 1,
        "score": (q1 + 4) * 4,
        "text": text,
    }


def test_who5_saves_every_field(conn: sqlite3.Connection) -> None:
    wid = add_who5(conn, who5_values("2026-03-10", "08:30:00", 3, "устал"))
    (row,) = list_who5(conn, "2026-03-10", "2026-03-10")
    assert row == {
        "id": wid,
        "date": "2026-03-10",
        "logged_at": "2026-03-10 08:30:00",
        "q1": 3,
        "q2": 1,
        "q3": 1,
        "q4": 1,
        "q5": 1,
        "score": 28,
        "text": "устал",
    }


def test_who5_text_may_be_empty(conn: sqlite3.Connection) -> None:
    add_who5(conn, who5_values("2026-03-10"))
    assert list_who5(conn, "2026-03-10", "2026-03-10")[0]["text"] is None


def test_who5_list_inclusive_by_date_sorted_by_time(conn: sqlite3.Connection) -> None:
    add_who5(conn, who5_values("2026-03-09"))
    late = add_who5(conn, who5_values("2026-03-11", "22:00:00"))
    early = add_who5(conn, who5_values("2026-03-10", "07:00:00"))
    add_who5(conn, who5_values("2026-03-12"))
    rows = list_who5(conn, "2026-03-10", "2026-03-11")
    assert [r["id"] for r in rows] == [early, late]


def test_last_who5_returns_two_latest_not_after_day_newest_first(conn: sqlite3.Connection) -> None:
    add_who5(conn, who5_values("2026-03-01", q1=1))
    middle = add_who5(conn, who5_values("2026-03-10", q1=2))
    newest = add_who5(conn, who5_values("2026-03-12", q1=3))
    add_who5(conn, who5_values("2026-03-20", q1=4))
    rows = last_who5(conn, "2026-03-12", 2)
    assert [r["id"] for r in rows] == [newest, middle]


def test_last_who5_same_date_takes_later_entry_first(conn: sqlite3.Connection) -> None:
    add_who5(conn, who5_values("2026-03-12", "08:00:00"))
    later = add_who5(conn, who5_values("2026-03-12", "21:00:00"))
    assert last_who5(conn, "2026-03-12", 1)[0]["id"] == later


def test_last_who5_empty(conn: sqlite3.Connection) -> None:
    assert last_who5(conn, "2026-03-12", 2) == []


def test_who5_rejects_answer_above_five(conn: sqlite3.Connection) -> None:
    values = who5_values("2026-03-10") | {"q1": 6, "score": 40}
    with pytest.raises(sqlite3.IntegrityError):
        add_who5(conn, values)


def test_who5_rejects_negative_answer(conn: sqlite3.Connection) -> None:
    values = who5_values("2026-03-10") | {"q3": -1, "score": 8}
    with pytest.raises(sqlite3.IntegrityError):
        add_who5(conn, values)


def test_who5_rejects_score_not_equal_sum_times_four(conn: sqlite3.Connection) -> None:
    values = who5_values("2026-03-10") | {"score": 99}
    with pytest.raises(sqlite3.IntegrityError):
        add_who5(conn, values)
