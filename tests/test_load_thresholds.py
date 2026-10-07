import sqlite3

from ai_coach.load import resolve_thresholds
from ai_coach.store.garmin_data import upsert_activity, upsert_threshold

END = "2026-10-07"


def threshold(
    conn: sqlite3.Connection,
    sport: str,
    lthr: int,
    day: str = "2026-10-01",
    source: str = "garmin_lt",
) -> None:
    upsert_threshold(
        conn,
        {"sport": sport, "calendar_date": day, "lthr": lthr, "source": source, "raw_json": {}},
    )


def activity_with_max_hr(conn: sqlite3.Connection, max_hr: int, start: str = "2026-10-01") -> None:
    upsert_activity(
        conn,
        {
            "activity_id": max_hr,
            "start_time_local": f"{start} 07:00:00",
            "type_key": "running",
            "max_hr": max_hr,
            "raw_json": {},
        },
    )


def test_only_run_threshold_derives_bike_and_swim(conn: sqlite3.Connection) -> None:
    threshold(conn, "run", 170)
    found = resolve_thresholds(conn, END)
    assert (found["run"]["lthr"], found["run"]["source"]) == (170, "garmin_lt")
    assert (found["bike"]["lthr"], found["bike"]["source"]) == (163, "derived")
    assert (found["swim"]["lthr"], found["swim"]["source"]) == (158, "derived")


def test_bike_from_zones_is_used_instead_of_offset(conn: sqlite3.Connection) -> None:
    threshold(conn, "run", 170)
    threshold(conn, "bike", 165, source="garmin_zones")
    found = resolve_thresholds(conn, END)
    assert (found["bike"]["lthr"], found["bike"]["source"]) == (165, "garmin_zones")
    assert (found["swim"]["lthr"], found["swim"]["source"]) == (158, "derived")


def test_swim_from_zones_is_used_instead_of_offset(conn: sqlite3.Connection) -> None:
    threshold(conn, "run", 170)
    threshold(conn, "swim", 160, source="garmin_zones")
    assert resolve_thresholds(conn, END)["swim"]["lthr"] == 160


def test_without_run_threshold_uses_89_percent_of_max_hr(conn: sqlite3.Connection) -> None:
    activity_with_max_hr(conn, 200)
    found = resolve_thresholds(conn, END)
    for sport in ("run", "bike", "swim"):
        assert (found[sport]["lthr"], found[sport]["source"]) == (178, "derived")


def test_max_hr_is_taken_only_up_to_end(conn: sqlite3.Connection) -> None:
    activity_with_max_hr(conn, 200)
    activity_with_max_hr(conn, 210, start="2026-10-08")
    assert resolve_thresholds(conn, END)["run"]["lthr"] == 178


def test_without_any_data_has_no_thresholds(conn: sqlite3.Connection) -> None:
    assert resolve_thresholds(conn, END) == {}


def test_latest_threshold_up_to_end_wins(conn: sqlite3.Connection) -> None:
    threshold(conn, "run", 165, day="2026-09-01")
    threshold(conn, "run", 170, day="2026-10-05")
    threshold(conn, "run", 175, day="2026-10-09")
    found = resolve_thresholds(conn, END)
    assert (found["run"]["lthr"], found["run"]["date"]) == (170, "2026-10-05")


def test_sports_do_not_overwrite_each_other_on_same_date(conn: sqlite3.Connection) -> None:
    threshold(conn, "run", 170, day="2026-10-05")
    threshold(conn, "bike", 165, day="2026-10-05", source="garmin_zones")
    found = resolve_thresholds(conn, END)
    assert (found["run"]["lthr"], found["bike"]["lthr"]) == (170, 165)


def test_derived_threshold_is_not_stored(conn: sqlite3.Connection) -> None:
    threshold(conn, "run", 170)
    resolve_thresholds(conn, END)
    assert conn.execute("SELECT COUNT(*) FROM thresholds").fetchone()[0] == 1


def zones_row(conn: sqlite3.Connection, sport: str, max_hr: int, lthr: int | None = None) -> None:
    upsert_threshold(
        conn,
        {
            "sport": sport,
            "calendar_date": "2026-10-01",
            "lthr": lthr,
            "max_hr": max_hr,
            "source": "garmin_zones",
            "raw_json": {},
        },
    )


def test_max_hr_from_zones_of_sport_beats_activities(conn: sqlite3.Connection) -> None:
    activity_with_max_hr(conn, 200)
    zones_row(conn, "run", 190)
    zones_row(conn, "swim", 170)
    found = resolve_thresholds(conn, END)
    assert found["run"]["lthr"] == 169
    assert found["swim"]["lthr"] == 151
    assert found["bike"]["lthr"] == 178


def test_max_hr_fallback_takes_only_run_and_bike_for_last_365_days(
    conn: sqlite3.Connection,
) -> None:
    activity_with_max_hr(conn, 200)
    activity_with_max_hr(conn, 220, start="2025-10-01")
    upsert_activity(
        conn,
        {
            "activity_id": 1,
            "start_time_local": "2026-10-02 07:00:00",
            "type_key": "strength_training",
            "max_hr": 230,
            "raw_json": {},
        },
    )
    assert resolve_thresholds(conn, END)["run"]["lthr"] == 178


def test_zones_row_without_lthr_is_not_a_threshold(conn: sqlite3.Connection) -> None:
    threshold(conn, "run", 170)
    zones_row(conn, "bike", 190)
    found = resolve_thresholds(conn, END)
    assert (found["bike"]["lthr"], found["bike"]["source"]) == (163, "derived")


def test_same_day_lactate_and_zones_without_lthr_keep_both(conn: sqlite3.Connection) -> None:
    from ai_coach.store.garmin_data import last_zones_max_hr

    threshold(conn, "run", 170)
    zones_row(conn, "run", 190)
    found = resolve_thresholds(conn, END)["run"]
    assert (found["lthr"], found["source"]) == (170, "garmin_lt")
    assert last_zones_max_hr(conn, "run", END) == 190


def test_same_day_zones_win_over_lactate(conn: sqlite3.Connection) -> None:
    threshold(conn, "run", 170)
    zones_row(conn, "run", 190, lthr=175)
    found = resolve_thresholds(conn, END)["run"]
    assert (found["lthr"], found["source"]) == (175, "garmin_zones")
