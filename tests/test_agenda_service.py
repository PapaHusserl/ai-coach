import sqlite3
from datetime import date
from typing import Any

import pytest
from workload_fakes import FakeCalendarWriter, FlakyCommitConn, coach_event

from ai_coach.agenda.service import (
    AHEAD_DAYS,
    MAX_HOURS,
    PAST_DAYS,
    AgendaError,
    agenda_rows,
    cancel_event,
    remove_event,
    validate_draft,
    write_event,
)
from ai_coach.store.agenda import add_event, get_event
from ai_coach.store.plans import add_planned_workout
from ai_coach.workload.calendar_eventkit import CalendarError

TODAY = date(2026, 10, 11)


def draft(conn: sqlite3.Connection, **fields: Any) -> dict[str, Any]:
    """Входные значения черновика (без служебных полей), как придут из MCP."""
    values = coach_event(**fields)
    values.pop("created_at")
    values.pop("all_day")
    values.pop("date")
    return values


def check(conn: sqlite3.Connection, **fields: Any) -> dict[str, Any]:
    return validate_draft(conn, draft(conn, **fields), today=TODAY)


def at(day: str, start: str = "10:00:00", end: str = "11:00:00") -> dict[str, str]:
    return {"start_at": f"{day}T{start}", "end_at": f"{day}T{end}"}


def stored(conn: sqlite3.Connection, **fields: Any) -> int:
    event_id = add_event(conn, coach_event(**fields))
    conn.commit()
    return event_id


def test_constants() -> None:
    assert (PAST_DAYS, AHEAD_DAYS, MAX_HOURS) == (30, 14, 24)


def test_valid_task_passes_and_gets_date_from_start(conn: sqlite3.Connection) -> None:
    result = check(conn, **at("2026-10-12"))
    assert result["date"] == "2026-10-12"
    assert result["kind"] == "task"
    assert result["category"] == "work"


def test_unknown_kind_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, kind="meeting")


def test_empty_title_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, title="  ")


def test_start_equal_end_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, start_at="2026-10-12T10:00:00", end_at="2026-10-12T10:00:00")


def test_start_after_end_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, start_at="2026-10-12T11:00:00", end_at="2026-10-12T10:00:00")


def test_one_minute_is_ok(conn: sqlite3.Connection) -> None:
    check(conn, **at("2026-10-12", "10:00:00", "10:01:00"))


def test_exactly_24_hours_is_ok(conn: sqlite3.Connection) -> None:
    check(conn, start_at="2026-10-12T10:00:00", end_at="2026-10-13T10:00:00")


def test_over_24_hours_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, start_at="2026-10-12T10:00:00", end_at="2026-10-13T10:01:00")


def test_30_days_back_is_ok(conn: sqlite3.Connection) -> None:
    check(conn, **at("2026-09-11"))


def test_31_days_back_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, **at("2026-09-10"))


def test_14_days_ahead_is_ok(conn: sqlite3.Connection) -> None:
    check(conn, **at("2026-10-25"))


def test_15_days_ahead_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, **at("2026-10-26"))


def test_today_is_ok(conn: sqlite3.Connection) -> None:
    check(conn, **at("2026-10-11"))


def test_unknown_category_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, category="coach")


@pytest.mark.parametrize("kind", ["training", "practice", "checkin"])
def test_uncounted_kinds_have_no_category(conn: sqlite3.Connection, kind: str) -> None:
    assert check(conn, kind=kind, category=None)["category"] is None


@pytest.mark.parametrize("kind", ["rest", "sleep"])
def test_rest_and_sleep_default_to_rest_category(conn: sqlite3.Connection, kind: str) -> None:
    assert check(conn, kind=kind, category=None)["category"] == "rest"


def test_task_without_category_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, category=None)


def test_task_keeps_given_category(conn: sqlite3.Connection) -> None:
    assert check(conn, category="hobby")["category"] == "hobby"


def test_checkin_daily_is_ok(conn: sqlite3.Connection) -> None:
    result = check(conn, kind="checkin", category=None, repeat="daily")
    assert result["repeat"] == "daily"


def test_repeat_weekly_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, kind="checkin", category=None, repeat="weekly")


def test_repeat_on_task_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, repeat="daily")


CHECKIN = {"kind": "checkin", "category": None, "repeat": "daily"}


@pytest.mark.parametrize("status", ["draft", "written"])
def test_repeating_checkin_at_same_time_is_error(conn: sqlite3.Connection, status: str) -> None:
    stored(conn, **CHECKIN, status=status, **at("2026-10-10", "11:00:00", "11:15:00"))
    with pytest.raises(AgendaError):
        check(conn, **CHECKIN, **at("2026-10-12", "11:00:00", "11:15:00"))


@pytest.mark.parametrize("status", ["draft", "written"])
def test_repeating_checkin_at_other_time_is_ok(conn: sqlite3.Connection, status: str) -> None:
    stored(conn, **CHECKIN, status=status, **at("2026-10-10", "11:00:00", "11:15:00"))
    result = check(conn, **CHECKIN, **at("2026-10-12", "15:00:00", "15:15:00"))
    assert result["repeat"] == "daily"


def test_repeating_checkin_one_minute_apart_is_ok(conn: sqlite3.Connection) -> None:
    stored(conn, **CHECKIN, **at("2026-10-10", "11:00:00", "11:15:00"))
    check(conn, **CHECKIN, **at("2026-10-12", "11:01:00", "11:15:00"))


def test_third_repeating_checkin_at_taken_time_is_error(conn: sqlite3.Connection) -> None:
    stored(conn, **CHECKIN, **at("2026-10-10", "11:00:00", "11:15:00"))
    stored(conn, **CHECKIN, **at("2026-10-10", "15:00:00", "15:15:00"))
    with pytest.raises(AgendaError, match="15:00"):
        check(conn, **CHECKIN, **at("2026-10-12", "15:00:00", "15:15:00"))


@pytest.mark.parametrize("status", ["cancelled", "removed"])
def test_repeating_checkin_after_inactive_one_is_ok(conn: sqlite3.Connection, status: str) -> None:
    stored(conn, **CHECKIN, status=status, **at("2026-10-10", "11:00:00", "11:15:00"))
    check(conn, **CHECKIN, **at("2026-10-12", "11:00:00", "11:15:00"))


def test_non_repeating_checkin_at_same_time_is_ok(conn: sqlite3.Connection) -> None:
    stored(conn, **CHECKIN, **at("2026-10-10", "11:00:00", "11:15:00"))
    check(conn, kind="checkin", category=None, **at("2026-10-12", "11:00:00", "11:15:00"))


def test_workout_id_must_exist(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, kind="training", category=None, workout_id=999)


def test_existing_workout_is_ok(conn: sqlite3.Connection) -> None:
    spec = {"date": "2026-10-12", "sport": "run", "name": "Бег", "workout_json": {}}
    workout = add_planned_workout(conn, spec)
    result = check(conn, kind="training", category=None, workout_id=workout)
    assert result["workout_id"] == workout


def test_cancelled_workout_is_error(conn: sqlite3.Connection) -> None:
    spec = {"date": "2026-10-12", "sport": "run", "name": "Бег", "workout_json": {}}
    workout = add_planned_workout(conn, spec | {"status": "cancelled"})
    with pytest.raises(AgendaError):
        check(conn, kind="training", category=None, workout_id=workout)


def test_practice_id_must_exist(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        check(conn, kind="practice", category=None, practice_id=999)


def test_deleted_practice_is_error(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO practice (id, name, kind, created_at, updated_at, deleted_at) "
        "VALUES (1, 'Синтетика', 'pause', '2026-10-01', '2026-10-01', '2026-10-02')"
    )
    with pytest.raises(AgendaError):
        check(conn, kind="practice", category=None, practice_id=1)


def test_validate_does_not_write(conn: sqlite3.Connection) -> None:
    check(conn)
    assert conn.execute("SELECT COUNT(*) FROM coach_events").fetchone()[0] == 0


def test_write_draft_sets_written_uid_and_time(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    writer = FakeCalendarWriter()
    write_event(conn, event_id, writer)
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["status"], row["calendar_uid"]) == ("written", "fake-uid-1")
    assert row["written_at"]


def test_write_passes_the_event_to_writer(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    writer = FakeCalendarWriter()
    write_event(conn, event_id, writer)
    assert writer.written[0]["id"] == event_id
    assert writer.written[0]["start_at"] == "2026-10-10T10:00:00"


@pytest.mark.parametrize("status", ["written", "cancelled", "removed"])
def test_write_only_from_draft(conn: sqlite3.Connection, status: str) -> None:
    event_id = stored(conn, status=status)
    writer = FakeCalendarWriter()
    with pytest.raises(AgendaError):
        write_event(conn, event_id, writer)
    assert writer.written == []


def test_repeated_write_does_not_create_second_event(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    writer = FakeCalendarWriter()
    write_event(conn, event_id, writer)
    with pytest.raises(AgendaError):
        write_event(conn, event_id, writer)
    assert len(writer.written) == 1


def test_write_missing_event_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        write_event(conn, 999, FakeCalendarWriter())


def test_calendar_error_leaves_database_unchanged(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    writer = FakeCalendarWriter(error=CalendarError("нет доступа"))
    with pytest.raises((AgendaError, CalendarError)):
        write_event(conn, event_id, writer)
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["status"], row["calendar_uid"], row["written_at"]) == ("draft", None, None)


def test_database_error_after_calendar_reports_uid(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    conn.execute(
        "CREATE TRIGGER boom BEFORE UPDATE ON coach_events BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    writer = FakeCalendarWriter()
    with pytest.raises(AgendaError, match="fake-uid-1"):
        write_event(conn, event_id, writer)


def test_remove_written_event(conn: sqlite3.Connection) -> None:
    event_id = stored(conn, status="written", calendar_uid="u1")
    writer = FakeCalendarWriter()
    remove_event(conn, event_id, writer)
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["status"], row["removed_by"]) == ("removed", "cli")
    assert row["removed_at"]
    assert writer.removed == [("u1", False)]


def test_remove_repeating_event_removes_future_occurrences(conn: sqlite3.Connection) -> None:
    fields = {"kind": "checkin", "category": None, "repeat": "daily"}
    event_id = stored(conn, status="written", calendar_uid="r1", **fields)
    writer = FakeCalendarWriter()
    remove_event(conn, event_id, writer)
    assert writer.removed == [("r1", True)]


@pytest.mark.parametrize("status", ["draft", "cancelled", "removed"])
def test_remove_only_from_written(conn: sqlite3.Connection, status: str) -> None:
    event_id = stored(conn, status=status)
    writer = FakeCalendarWriter()
    with pytest.raises(AgendaError):
        remove_event(conn, event_id, writer)
    assert writer.removed == []


def test_remove_foreign_uid_leaves_status(conn: sqlite3.Connection) -> None:
    event_id = stored(conn, status="written", calendar_uid="alien")
    writer = FakeCalendarWriter(foreign=("alien",))
    with pytest.raises((AgendaError, CalendarError)):
        remove_event(conn, event_id, writer)
    row = get_event(conn, event_id)
    assert row is not None
    assert row["status"] == "written"


def test_remove_database_error_reports_uid(conn: sqlite3.Connection) -> None:
    event_id = stored(conn, status="written", calendar_uid="u9")
    conn.execute(
        "CREATE TRIGGER boom BEFORE UPDATE ON coach_events BEGIN SELECT RAISE(ABORT, 'boom'); END"
    )
    with pytest.raises(AgendaError, match="u9"):
        remove_event(conn, event_id, FakeCalendarWriter())


def test_cancel_draft(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    cancel_event(conn, event_id)
    row = get_event(conn, event_id)
    assert row is not None
    assert row["status"] == "cancelled"


@pytest.mark.parametrize("status", ["written", "cancelled", "removed"])
def test_cancel_only_from_draft(conn: sqlite3.Connection, status: str) -> None:
    event_id = stored(conn, status=status)
    with pytest.raises(AgendaError):
        cancel_event(conn, event_id)
    row = get_event(conn, event_id)
    assert row is not None
    assert row["status"] == status


def test_cancel_missing_event_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        cancel_event(conn, 999)


def test_agenda_rows_put_all_earlier_repeats_first_by_start(conn: sqlite3.Connection) -> None:
    for clock, title in (("15:00:00", "поздний"), ("11:00:00", "ранний")):
        stored(
            conn, **CHECKIN, title=title, date="2026-10-01", **at("2026-10-01", clock, "16:00:00")
        )
    stored(conn, title="задача", **at("2026-10-12"), date="2026-10-12")
    rows = agenda_rows(conn, "2026-10-10", "2026-10-14")
    assert [r["title"] for r in rows] == ["ранний", "поздний", "задача"]


def test_agenda_rows_do_not_duplicate_repeats_inside_range(conn: sqlite3.Connection) -> None:
    stored(conn, **CHECKIN, title="внутри", date="2026-10-12", **at("2026-10-12", "11:00:00"))
    rows = agenda_rows(conn, "2026-10-10", "2026-10-14")
    assert [r["title"] for r in rows] == ["внутри"]


def test_agenda_rows_skip_inactive_repeats(conn: sqlite3.Connection) -> None:
    stored(conn, **CHECKIN, status="cancelled", date="2026-10-01", **at("2026-10-01"))
    assert agenda_rows(conn, "2026-10-10", "2026-10-14") == []


def test_commit_error_after_write_reports_uid(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    with pytest.raises(AgendaError, match="fake-uid-1"):
        write_event(FlakyCommitConn(conn), event_id, FakeCalendarWriter())  # type: ignore[arg-type]


def test_commit_error_after_remove_reports_uid(conn: sqlite3.Connection) -> None:
    event_id = stored(conn, status="written", calendar_uid="u7")
    with pytest.raises(AgendaError, match="u7"):
        remove_event(FlakyCommitConn(conn), event_id, FakeCalendarWriter())  # type: ignore[arg-type]
