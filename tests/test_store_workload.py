import sqlite3

import pytest
from workload_fakes import stored_event

from ai_coach.store.workload import (
    list_calendar_events,
    list_counters,
    replace_calendar_window,
    upsert_counter,
)

START = "2026-10-01"
END = "2026-10-31"


def ev(uid: str, day: str, hour: int = 10, **fields: object) -> dict[str, object]:
    return stored_event(
        uid=uid, start_at=f"{day}T{hour:02d}:00:00", end_at=f"{day}T{hour + 1:02d}:00:00", **fields
    )


def uids(conn: sqlite3.Connection, start: str = "2026-09-01", end: str = "2026-12-31") -> list[str]:
    return [e["uid"] for e in list_calendar_events(conn, start, end)]


def test_replace_writes_events(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, START, END, [ev("a", "2026-10-07")])
    found = list_calendar_events(conn, START, END)
    assert [(e["uid"], e["date"], e["category"], e["source"]) for e in found] == [
        ("a", "2026-10-07", "work", "apple_calendar")
    ]


def test_replace_twice_with_same_events_changes_nothing(conn: sqlite3.Connection) -> None:
    events = [ev("a", "2026-10-07"), ev("b", "2026-10-08")]
    replace_calendar_window(conn, START, END, events)
    first = list_calendar_events(conn, START, END)
    replace_calendar_window(conn, START, END, events)
    assert [e["uid"] for e in list_calendar_events(conn, START, END)] == ["a", "b"]
    assert len(first) == 2


def test_replace_removes_event_that_disappeared(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, START, END, [ev("a", "2026-10-07"), ev("b", "2026-10-08")])
    replace_calendar_window(conn, START, END, [ev("a", "2026-10-07")])
    assert uids(conn) == ["a"]


def test_replace_keeps_history_before_window(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, "2026-09-01", "2026-09-30", [ev("old", "2026-09-15")])
    replace_calendar_window(conn, START, END, [ev("new", "2026-10-07")])
    assert uids(conn) == ["old", "new"]


def test_replace_keeps_events_after_window(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, "2026-11-01", "2026-11-30", [ev("later", "2026-11-15")])
    replace_calendar_window(conn, START, END, [])
    assert uids(conn) == ["later"]


def test_replace_window_edges_are_inclusive(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, START, END, [ev("first", START), ev("last", END)])
    replace_calendar_window(conn, START, END, [])
    assert uids(conn) == []


def test_replace_with_empty_list_clears_only_window(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, START, END, [ev("a", "2026-10-07")])
    replace_calendar_window(conn, "2026-10-08", END, [])
    assert uids(conn) == ["a"]


def test_replace_keeps_recurring_instances_with_same_uid(conn: sqlite3.Connection) -> None:
    events = [ev("series", "2026-10-07"), ev("series", "2026-10-08")]
    replace_calendar_window(conn, START, END, events)
    assert [e["date"] for e in list_calendar_events(conn, START, END)] == [
        "2026-10-07",
        "2026-10-08",
    ]


def test_replace_updates_changed_event(conn: sqlite3.Connection) -> None:
    replace_calendar_window(conn, START, END, [ev("a", "2026-10-07", title="До")])
    replace_calendar_window(conn, START, END, [ev("a", "2026-10-07", title="После")])
    assert [e["title"] for e in list_calendar_events(conn, START, END)] == ["После"]


def test_list_events_period_is_inclusive_and_sorted(conn: sqlite3.Connection) -> None:
    events = [ev("c", "2026-10-09"), ev("a", "2026-10-07", 15), ev("b", "2026-10-07", 9)]
    replace_calendar_window(conn, START, END, events)
    assert uids(conn, "2026-10-07", "2026-10-09") == ["b", "a", "c"]
    assert uids(conn, "2026-10-08", "2026-10-08") == []


def test_list_events_keeps_all_day_flag_and_statuses(conn: sqlite3.Connection) -> None:
    replace_calendar_window(
        conn,
        START,
        END,
        [ev("a", "2026-10-07", all_day=True, status="tentative", my_status="declined")],
    )
    found = list_calendar_events(conn, START, END)[0]
    assert (found["all_day"], found["status"], found["my_status"]) == (1, "tentative", "declined")


def counter(day: str, kind: str, value: float, source: str = "todo") -> dict[str, object]:
    return {
        "date": day,
        "kind": kind,
        "value": value,
        "source": source,
        "raw_json": {},
        "synced_at": "2026-10-08T10:00:00",
    }


def test_upsert_counter_inserts(conn: sqlite3.Connection) -> None:
    upsert_counter(conn, counter("2026-10-07", "todo_closed", 2))
    found = list_counters(conn, "2026-10-07", "2026-10-07")
    assert [(c["date"], c["kind"], c["value"], c["source"]) for c in found] == [
        ("2026-10-07", "todo_closed", 2.0, "todo")
    ]


def test_upsert_counter_overwrites_same_date_and_kind(conn: sqlite3.Connection) -> None:
    upsert_counter(conn, counter("2026-10-07", "todo_open", 5))
    upsert_counter(conn, counter("2026-10-07", "todo_open", 3))
    found = list_counters(conn, "2026-10-07", "2026-10-07")
    assert [c["value"] for c in found] == [3.0]


def test_upsert_counter_other_kind_is_separate_row(conn: sqlite3.Connection) -> None:
    upsert_counter(conn, counter("2026-10-07", "todo_open", 5))
    upsert_counter(conn, counter("2026-10-07", "todo_closed", 1))
    assert len(list_counters(conn, "2026-10-07", "2026-10-07")) == 2


def test_upsert_counter_keeps_zero(conn: sqlite3.Connection) -> None:
    upsert_counter(conn, counter("2026-10-07", "grooming_done", 0))
    assert list_counters(conn, "2026-10-07", "2026-10-07")[0]["value"] == 0.0


def test_upsert_counter_unknown_kind_is_refused(conn: sqlite3.Connection) -> None:
    """Белый список kind - в Python (store/workload.py), не в схеме."""
    with pytest.raises(ValueError):
        upsert_counter(conn, counter("2026-10-07", "no_such_kind", 1))


@pytest.mark.parametrize("kind", ["todo_open", "todo_closed", "grooming_done", "grooming_pending"])
def test_upsert_counter_known_kinds_are_allowed(conn: sqlite3.Connection, kind: str) -> None:
    upsert_counter(conn, counter("2026-10-07", kind, 1, "manual"))


def test_list_counters_period_and_kind_filter(conn: sqlite3.Connection) -> None:
    for day in ("2026-10-06", "2026-10-07", "2026-10-08"):
        upsert_counter(conn, counter(day, "todo_closed", 1))
        upsert_counter(conn, counter(day, "todo_open", 4))
    found = list_counters(conn, "2026-10-07", "2026-10-08", "todo_closed")
    assert [(c["date"], c["kind"]) for c in found] == [
        ("2026-10-07", "todo_closed"),
        ("2026-10-08", "todo_closed"),
    ]


def test_list_counters_without_kind_is_sorted_by_date(conn: sqlite3.Connection) -> None:
    upsert_counter(conn, counter("2026-10-08", "todo_open", 1))
    upsert_counter(conn, counter("2026-10-07", "todo_open", 1))
    found = list_counters(conn, "2026-10-01", "2026-10-31")
    assert [c["date"] for c in found] == ["2026-10-07", "2026-10-08"]
