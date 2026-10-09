import sqlite3

from ai_coach.store.journal import (
    add_food,
    add_sync_log,
    add_weight,
    last_sync_log,
    list_food,
    list_weights,
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
