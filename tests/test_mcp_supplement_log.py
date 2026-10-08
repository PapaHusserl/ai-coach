import sqlite3

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, rows, tool_names

from ai_coach.mcp_server.tools import MAX_CHARS, SNAPSHOT_CHARS
from ai_coach.store.intake import delete_intake, log_intake
from ai_coach.store.plans import add_planned_workout
from ai_coach.store.sport_nutrition import add_supplement, delete_supplement

DAY = "2026-10-08"
NOW = "2026-10-08 10:00:00"


def new_supplement(conn: sqlite3.Connection, name: str = "креатин", schedule: str = "daily") -> int:
    return add_supplement(
        conn,
        {
            "name": name,
            "dose": 5.0,
            "unit": "g",
            "schedule": schedule,
            "time_note": None,
            "note": None,
            "created_at": NOW,
            "updated_at": NOW,
        },
    )


def take(conn: sqlite3.Connection, item_id: int, day: str = DAY, **fields: object) -> int:
    values = {
        "kind": "supplement",
        "item_id": item_id,
        "date": day,
        "taken_at": f"{day} 09:00:00",
        "dose": None,
        "note": None,
    }
    return log_intake(conn, {**values, **fields})


def new_workout(conn: sqlite3.Connection) -> int:
    row = {"date": DAY, "sport": "run", "name": "т", "workout_json": {}, "status": "approved"}
    return add_planned_workout(conn, row)


def log(conn: sqlite3.Connection, start: str = DAY, end: str = DAY) -> dict:
    return call(conn, "get_supplement_log", date_from=start, date_to=end)


# --- get_supplement_log ---


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_supplement_log" in tool_names(conn)


def test_get_on_empty_database(conn: sqlite3.Connection) -> None:
    assert log(conn) == {"rows": [], "truncated": False}


def test_get_returns_row_with_name_and_fields(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    lid = take(conn, sid, dose=3.0, note="с водой")
    row = rows(conn, "get_supplement_log", date_from=DAY, date_to=DAY)[0]
    assert (row["id"], row["name"], row["date"]) == (lid, "креатин", DAY)
    assert (row["dose"], row["note"]) == (3.0, "с водой")


def test_get_range_is_inclusive(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    for day in ("2026-10-05", "2026-10-06", "2026-10-08", "2026-10-09"):
        take(conn, sid, day)
    found = rows(conn, "get_supplement_log", date_from="2026-10-06", date_to="2026-10-08")
    assert [r["date"] for r in found] == ["2026-10-06", "2026-10-08"]


def test_get_hides_deleted_intake(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    gone = take(conn, sid, note="лишний")
    take(conn, sid, note="нужный")
    delete_intake(conn, gone, "2026-10-08 12:00:00")
    assert [r["note"] for r in rows(conn, "get_supplement_log", date_from=DAY, date_to=DAY)] == [
        "нужный"
    ]


def test_get_shows_name_of_deleted_supplement(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn, "магний")
    take(conn, sid)
    delete_supplement(conn, sid, "2026-10-08 12:00:00")
    assert [r["name"] for r in rows(conn, "get_supplement_log", date_from=DAY, date_to=DAY)] == [
        "магний"
    ]


def test_get_several_intakes_per_day(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    take(conn, sid)
    take(conn, sid, taken_at=f"{DAY} 20:00:00")
    assert len(rows(conn, "get_supplement_log", date_from=DAY, date_to=DAY)) == 2


def test_get_has_no_service_fields(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn))
    text = call_text(conn, "get_supplement_log", date_from=DAY, date_to=DAY)
    assert "deleted_at" not in text
    assert "raw_json" not in text


@pytest.mark.parametrize("field", ["date_from", "date_to"])
def test_get_bad_date_is_refused(conn: sqlite3.Connection, field: str) -> None:
    args = {"date_from": DAY, "date_to": DAY} | {field: "08.10.2026"}
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        call(conn, "get_supplement_log", **args)


def test_get_is_capped_by_rows(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    for number in range(100):
        take(conn, sid, taken_at=f"{DAY} 09:{number % 60:02d}:00")
    result = log(conn)
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60


def test_get_is_capped_by_chars(conn: sqlite3.Connection) -> None:
    sid = new_supplement(conn)
    for _ in range(50):
        take(conn, sid, note="я" * 1000)
    result = log(conn)
    assert result["truncated"] is True
    assert len(call_text(conn, "get_supplement_log", date_from=DAY, date_to=DAY)) <= MAX_CHARS + 100


# --- taken in get_sport_nutrition_for ---


def for_day(conn: sqlite3.Connection) -> dict:
    return call(conn, "get_sport_nutrition_for", date=DAY)


def test_for_shows_taken_flags(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn, "креатин"))
    new_supplement(conn, "магний")
    found = {s["name"]: s["taken"] for s in for_day(conn)["supplements"]}
    assert found == {"креатин": True, "магний": False}


def test_for_taken_depends_on_date(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn), "2026-10-07")
    assert [s["taken"] for s in for_day(conn)["supplements"]] == [False]
    other = call(conn, "get_sport_nutrition_for", date="2026-10-07")
    assert [s["taken"] for s in other["supplements"]] == [True]


def test_for_deleted_intake_is_not_taken(conn: sqlite3.Connection) -> None:
    lid = take(conn, new_supplement(conn))
    delete_intake(conn, lid, "2026-10-08 12:00:00")
    assert [s["taken"] for s in for_day(conn)["supplements"]] == [False]


def test_for_training_day_taken_flag_of_training_supplement(conn: sqlite3.Connection) -> None:
    new_workout(conn)
    take(conn, new_supplement(conn, "магний", "training_day"))
    assert [s["taken"] for s in for_day(conn)["supplements"]] == [True]


# --- snapshot ---


def snapshot(conn: sqlite3.Connection) -> dict:
    return call(conn, "get_morning_snapshot", date=DAY)


def supplements_line(conn: sqlite3.Connection) -> str:
    return snapshot(conn)["sport_nutrition_today"]["supplements"]


def part(text: str, name: str) -> str:
    return next(p for p in text.split("; ") if p.startswith(name))


def test_snapshot_marks_taken_supplement(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn, "креатин"))
    new_supplement(conn, "магний")
    line = supplements_line(conn)
    assert "принят" in part(line, "креатин")
    assert "принят" not in part(line, "магний")


def test_snapshot_does_not_mark_other_date_intake(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn, "креатин"), "2026-10-07")
    assert "принят" not in supplements_line(conn)


def test_snapshot_does_not_mark_deleted_intake(conn: sqlite3.Connection) -> None:
    lid = take(conn, new_supplement(conn, "креатин"))
    delete_intake(conn, lid, "2026-10-08 12:00:00")
    assert "принят" not in supplements_line(conn)


def test_snapshot_has_no_log_notes(conn: sqlite3.Connection) -> None:
    take(conn, new_supplement(conn), note="SECRET_LOG_NOTE")
    assert "SECRET_LOG_NOTE" not in str(snapshot(conn))


def test_snapshot_without_supplements_and_workout_has_no_key(conn: sqlite3.Connection) -> None:
    assert "sport_nutrition_today" not in snapshot(conn)


def test_snapshot_line_is_not_cut_with_many_taken(conn: sqlite3.Connection) -> None:
    new_workout(conn)
    for number in range(30):
        take(conn, new_supplement(conn, f"добавка номер {number}"))
    line = supplements_line(conn)
    for number in range(30):
        assert "принят" in part(line, f"добавка номер {number}")


def test_snapshot_nutrition_part_fits_char_limit(conn: sqlite3.Connection) -> None:
    new_workout(conn)
    for number in range(12):
        take(conn, new_supplement(conn, f"добавка {number}"))
    part_text = str(snapshot(conn)["sport_nutrition_today"])
    assert len(part_text) <= SNAPSHOT_CHARS


# --- период ---


def test_get_end_before_start_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="Конец периода раньше начала."):
        call(conn, "get_supplement_log", date_from="2026-10-08", date_to="2026-10-07")


def test_get_period_of_92_days_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="Период не больше 92 дней."):
        call(conn, "get_supplement_log", date_from="2026-07-01", date_to="2026-10-01")


def test_get_period_of_92_days_inclusive_is_allowed(conn: sqlite3.Connection) -> None:
    assert log(conn, "2026-07-08", "2026-10-07") == {"rows": [], "truncated": False}


def test_get_same_day_period_is_allowed(conn: sqlite3.Connection) -> None:
    assert log(conn, DAY, DAY) == {"rows": [], "truncated": False}
