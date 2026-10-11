"""sync_workload и календарь коуча: свои события по uid, чужие пропуск, пропавшие - removed."""

import sqlite3
from dataclasses import replace
from datetime import date
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
