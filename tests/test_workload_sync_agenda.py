"""sync_workload и календарь коуча: свои события по uid, чужие пропуск, пропавшие - removed."""

import sqlite3
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest
from workload_fakes import (
    FakeCalendar,
    coach_event,
    raw_event,
    todo_item,
    write_config,
    write_hb,
    write_todo,
)

from ai_coach.agenda.slots import busy_spans
from ai_coach.store.agenda import add_event, get_event
from ai_coach.store.workload import list_calendar_events
from ai_coach.sync.workload_sync import sync_workload
from ai_coach.workload.calendar_eventkit import CalendarError
from ai_coach.workload.config import WorkloadConfig, load_config
from ai_coach.workload.service import workload_day

TODAY = date(2026, 10, 8)
DAYS = 7
ALL = ("2000-01-01", "2100-01-01")
DAY = "2026-10-10"


@pytest.fixture
def config(tmp_path: Path) -> WorkloadConfig:
    todo = write_todo(tmp_path / "todo.json", [todo_item(1, "todo", "2026-10-01")])
    hb = write_hb(tmp_path / "hb", {}, {})
    text = (
        '[calendar]\nwork = ["Work"]\n[coach]\ncalendar = "Coach"\n'
        f'[paths]\ntodo = "{todo}"\nhb_watch = "{hb}"\n'
        f'claude_projects = "{tmp_path / "no-claude"}"\n'
    )
    return load_config(write_config(tmp_path / "w.toml", text))


def run(conn: sqlite3.Connection, config: WorkloadConfig, reader: FakeCalendar) -> str:
    return sync_workload(conn, reader=reader, config=config, days=DAYS, today=TODAY)


def own(conn: sqlite3.Connection, uid: str = "c1", **fields: object) -> int:
    values = coach_event(status="written", calendar_uid=uid, **fields)
    event_id = add_event(conn, values)
    conn.commit()
    return event_id


def coach_raw(uid: str = "c1", **fields: object) -> dict[str, object]:
    base = {
        "calendar": "Coach",
        "start_at": f"{DAY}T10:00:00",
        "end_at": f"{DAY}T12:00:00",
    }
    return raw_event(uid=uid, **(base | fields))


def add_workout(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO planned_workouts (id, date, sport, name, workout_json)"
        " VALUES (7, ?, 'run', 'Бег', '{}')",
        (DAY,),
    )
    conn.commit()


def status_of(conn: sqlite3.Connection, event_id: int) -> str:
    row = get_event(conn, event_id)
    assert row is not None
    return row["status"]


def test_own_work_event_counts_as_work_hours(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    own(conn, category="work")
    run(conn, config, FakeCalendar([coach_raw()]))
    found = list_calendar_events(conn, *ALL)
    assert [(e["uid"], e["category"]) for e in found] == [("c1", "work")]
    assert workload_day(conn, DAY)["work_hours"] == 2.0


def test_own_weekend_work_event_is_counted_on_weekend(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    saturday = "2026-10-10"
    own(conn, category="work", date=saturday)
    run(conn, config, FakeCalendar([coach_raw()]))
    day = workload_day(conn, saturday)
    assert day["weekend"] is True
    assert day["work_hours"] == 2.0


def test_own_hobby_event_counts_as_hobby(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    own(conn, category="hobby")
    run(conn, config, FakeCalendar([coach_raw()]))
    day = workload_day(conn, DAY)
    assert (day["hobby_hours"], day["work_hours"]) == (2.0, 0.0)


def test_own_events_get_demand(
    conn: sqlite3.Connection, config: WorkloadConfig, tmp_path: Path
) -> None:
    own(conn, "c1", category="work")
    own(conn, "c2", category="work")
    own(conn, "c3", category="hobby")
    raws = [
        coach_raw("c1", title="Созвон"),
        coach_raw("c2", title="Design review"),
        coach_raw("c3", title="Гитара"),
    ]
    text = (
        '[calendar]\nwork = ["Work"]\n[calendar.demand]\nchallenge = ["design"]\n'
        '[coach]\ncalendar = "Coach"\n'
    )
    ruled = load_config(write_config(tmp_path / "d.toml", text))
    run(conn, ruled, FakeCalendar(raws))
    found = {e["uid"]: e["demand"] for e in list_calendar_events(conn, *ALL)}
    assert found == {"c1": "hindrance", "c2": "challenge", "c3": None}


def test_own_event_without_category_is_not_stored(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    own(conn, kind="training", category=None)
    run(conn, config, FakeCalendar([coach_raw()]))
    assert list_calendar_events(conn, *ALL) == []


def test_foreign_event_in_coach_calendar_is_skipped(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    run(conn, config, FakeCalendar([coach_raw(uid="by-hand")]))
    assert list_calendar_events(conn, *ALL) == []


def test_foreign_event_is_not_added_to_coach_events(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    run(conn, config, FakeCalendar([coach_raw(uid="by-hand")]))
    assert conn.execute("SELECT COUNT(*) FROM coach_events").fetchone()[0] == 0


def test_other_calendars_still_work(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    run(conn, config, FakeCalendar([raw_event(uid="w")]))
    assert [e["category"] for e in list_calendar_events(conn, *ALL)] == ["work"]


def test_own_written_event_missing_in_calendar_is_removed_by_calendar(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = own(conn)
    run(conn, config, FakeCalendar([]))
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["status"], row["removed_by"]) == ("removed", "calendar")
    assert row["removed_at"]


def test_present_event_stays_written(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    event_id = own(conn)
    run(conn, config, FakeCalendar([coach_raw()]))
    assert status_of(conn, event_id) == "written"


def test_draft_is_not_touched_by_sync(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    event_id = add_event(conn, coach_event())
    conn.commit()
    run(conn, config, FakeCalendar([]))
    assert status_of(conn, event_id) == "draft"


def test_already_removed_event_is_not_changed(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = add_event(conn, coach_event(status="removed", removed_by="cli", calendar_uid="c1"))
    conn.commit()
    run(conn, config, FakeCalendar([]))
    row = get_event(conn, event_id)
    assert row is not None
    assert row["removed_by"] == "cli"


def test_written_event_outside_window_is_not_removed(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    old = "2026-08-01"
    event_id = own(conn, date=old, start_at=f"{old}T10:00:00", end_at=f"{old}T11:00:00")
    run(conn, config, FakeCalendar([]))
    assert status_of(conn, event_id) == "written"


def test_calendar_error_does_not_mark_removed(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = own(conn)
    message = run(conn, config, FakeCalendar(error=CalendarError("нет доступа")))
    assert status_of(conn, event_id) == "written"
    assert "нет доступа" in message


def test_repeating_checkin_with_shared_uid_stays_written(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = own(conn, "r1", kind="checkin", category=None, repeat="daily")
    days = ["2026-10-08", "2026-10-09", "2026-10-10"]
    occurrences = [coach_raw("r1", start_at=f"{d}T21:00:00", end_at=f"{d}T21:15:00") for d in days]
    run(conn, config, FakeCalendar(occurrences))
    assert status_of(conn, event_id) == "written"
    assert list_calendar_events(conn, *ALL) == []


def test_two_repeating_checkins_only_vanished_one_is_removed(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    kept = own(conn, "r1", kind="checkin", category=None, repeat="daily")
    gone = own(conn, "r2", kind="checkin", category=None, repeat="daily")
    days = ["2026-10-08", "2026-10-09", "2026-10-10"]
    occurrences = [coach_raw("r1", start_at=f"{d}T21:00:00", end_at=f"{d}T21:15:00") for d in days]
    run(conn, config, FakeCalendar(occurrences))
    assert status_of(conn, kept) == "written"
    row = get_event(conn, gone)
    assert row is not None
    assert (row["status"], row["removed_by"]) == ("removed", "calendar")


def test_two_repeating_checkins_present_in_calendar_stay_written(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    first = own(conn, "r1", kind="checkin", category=None, repeat="daily")
    second = own(conn, "r2", kind="checkin", category=None, repeat="daily")
    occurrences = [
        coach_raw("r1", start_at=f"{DAY}T11:00:00", end_at=f"{DAY}T11:15:00"),
        coach_raw("r2", start_at=f"{DAY}T15:00:00", end_at=f"{DAY}T15:15:00"),
    ]
    run(conn, config, FakeCalendar(occurrences))
    assert (status_of(conn, first), status_of(conn, second)) == ("written", "written")


def test_repeated_sync_changes_nothing(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    own(conn, "c1", category="work")
    own(conn, "c2", category="hobby", start_at="2026-10-10T14:00:00", end_at="2026-10-10T15:00:00")
    reader = FakeCalendar([coach_raw("c1"), coach_raw("by-hand")])
    run(conn, config, reader)
    first = (
        list_calendar_events(conn, *ALL),
        conn.execute("SELECT * FROM coach_events ORDER BY id").fetchall(),
    )
    run(conn, config, reader)
    second = (
        list_calendar_events(conn, *ALL),
        conn.execute("SELECT * FROM coach_events ORDER BY id").fetchall(),
    )
    assert [tuple(r) for r in first[1]] == [tuple(r) for r in second[1]]
    assert first[0] == second[0]


def test_second_sync_after_removal_keeps_removed_at(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = own(conn)
    run(conn, config, FakeCalendar([]))
    first = get_event(conn, event_id)
    run(conn, config, FakeCalendar([]))
    assert get_event(conn, event_id) == first


def test_without_coach_calendar_coach_events_are_not_touched(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = own(conn)
    no_coach = replace(config, coach_calendar=None)
    run(conn, no_coach, FakeCalendar([]))
    assert status_of(conn, event_id) == "written"


def test_moved_written_event_gets_new_time(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = own(conn)
    moved = coach_raw(start_at=f"{DAY}T14:00:00", end_at=f"{DAY}T15:00:00")
    message = run(conn, config, FakeCalendar([moved]))
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["start_at"], row["end_at"], row["date"]) == (
        f"{DAY}T14:00:00",
        f"{DAY}T15:00:00",
        DAY,
    )
    assert row["status"] == "written"
    assert "перенесено в календаре: 1" in message


def test_move_to_another_day_changes_date(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    event_id = own(conn)
    new_day = "2026-10-11"
    moved = coach_raw(start_at=f"{new_day}T10:00:00", end_at=f"{new_day}T12:00:00")
    run(conn, config, FakeCalendar([moved]))
    row = get_event(conn, event_id)
    assert row is not None
    assert row["date"] == new_day
    assert row["start_at"] == f"{new_day}T10:00:00"


def test_moved_event_gives_single_busy_span(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    own(conn)
    moved = coach_raw(start_at=f"{DAY}T14:00:00", end_at=f"{DAY}T15:00:00")
    run(conn, config, FakeCalendar([moved]))
    spans = busy_spans(conn, date.fromisoformat(DAY))
    # событие видно и как строка календаря, и как строка тренера: оба отрезка - новые, старого нет
    assert set(spans) == {(datetime(2026, 10, 10, 14), datetime(2026, 10, 10, 15))}


def test_unmoved_event_is_not_reported(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    own(conn)
    message = run(conn, config, FakeCalendar([coach_raw()]))
    assert "перенесено" not in message


def test_move_of_workout_event_to_other_day_warns(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    add_workout(conn)
    own(conn, workout_id=7)
    new_day = "2026-10-11"
    moved = coach_raw(start_at=f"{new_day}T10:00:00", end_at=f"{new_day}T12:00:00")
    message = run(conn, config, FakeCalendar([moved]))
    assert "тренировка 7 перенесена в календаре, на часах - старая дата" in message


def test_move_of_workout_event_within_same_day_does_not_warn(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    add_workout(conn)
    own(conn, workout_id=7)
    moved = coach_raw(start_at=f"{DAY}T14:00:00", end_at=f"{DAY}T15:00:00")
    message = run(conn, config, FakeCalendar([moved]))
    assert "перенесено в календаре: 1" in message
    assert "тренировка 7" not in message


def test_moved_repeating_event_is_not_changed(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = own(
        conn, "r1", kind="checkin", category=None, repeat="daily",
        start_at=f"{DAY}T21:00:00", end_at=f"{DAY}T21:15:00",
    )  # fmt: skip
    before = get_event(conn, event_id)
    shifted = coach_raw("r1", start_at=f"{DAY}T22:00:00", end_at=f"{DAY}T22:15:00")
    message = run(conn, config, FakeCalendar([shifted]))
    assert get_event(conn, event_id) == before
    assert "перенесено" not in message


def test_all_day_event_in_calendar_is_not_a_move(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    fields = {"all_day": 1, "start_at": f"{DAY}T00:00:00", "end_at": f"{DAY}T23:59:59"}
    own(conn, **fields)
    raw = coach_raw(all_day=True, start_at=f"{DAY}T00:00:00", end_at=f"{DAY}T23:59:59")
    message = run(conn, config, FakeCalendar([raw]))
    assert "перенесено" not in message


def test_all_day_event_shifted_to_next_day_is_a_move(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    fields = {"all_day": 1, "start_at": f"{DAY}T00:00:00", "end_at": f"{DAY}T23:59:59"}
    event_id = own(conn, **fields)
    raw = coach_raw(all_day=True, start_at="2026-10-11T00:00:00", end_at="2026-10-11T23:59:59")
    run(conn, config, FakeCalendar([raw]))
    row = get_event(conn, event_id)
    assert row is not None
    assert row["date"] == "2026-10-11"


def test_one_foreign_event_is_counted_in_notes(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    message = run(conn, config, FakeCalendar([coach_raw(uid="by-hand")]))
    assert "чужих событий в календаре коуча: 1" in message


def test_two_foreign_events_are_counted_in_notes(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    raws = [coach_raw(uid="h1"), coach_raw(uid="h2")]
    message = run(conn, config, FakeCalendar(raws))
    assert "чужих событий в календаре коуча: 2" in message


def test_no_foreign_events_gives_no_note(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    own(conn)
    message = run(conn, config, FakeCalendar([coach_raw()]))
    assert "чужих" not in message


def test_own_event_after_other_calendar_event_is_stored(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    own(conn)
    run(conn, config, FakeCalendar([raw_event(uid="w"), coach_raw()]))
    assert sorted(e["uid"] for e in list_calendar_events(conn, *ALL)) == ["c1", "w"]


def test_own_event_after_foreign_event_is_stored(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    own(conn)
    run(conn, config, FakeCalendar([coach_raw(uid="by-hand"), coach_raw()]))
    assert [e["uid"] for e in list_calendar_events(conn, *ALL)] == ["c1"]


def test_only_start_changed_is_a_move(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    event_id = own(conn)
    run(conn, config, FakeCalendar([coach_raw(start_at=f"{DAY}T09:00:00")]))
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["start_at"], row["end_at"]) == (f"{DAY}T09:00:00", f"{DAY}T12:00:00")


def test_only_end_changed_is_a_move(conn: sqlite3.Connection, config: WorkloadConfig) -> None:
    event_id = own(conn)
    run(conn, config, FakeCalendar([coach_raw(end_at=f"{DAY}T13:00:00")]))
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["start_at"], row["end_at"]) == (f"{DAY}T10:00:00", f"{DAY}T13:00:00")


def test_move_outside_sync_window_marks_removed_by_calendar(
    conn: sqlite3.Connection, config: WorkloadConfig
) -> None:
    event_id = own(conn)
    run(conn, config, FakeCalendar([]))  # событие перенесено за окно: читатель его не видит
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["status"], row["removed_by"]) == ("removed", "calendar")
