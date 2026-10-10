import sqlite3
from datetime import date
from pathlib import Path

import pytest
from workload_fakes import (
    FakeCalendar,
    raw_event,
    stored_event,
    todo_item,
    tree_state,
    write_config,
    write_hb,
    write_todo,
)

from ai_coach.store.journal import add_sync_log, sync_runs_on
from ai_coach.store.workload import list_calendar_events, list_counters, replace_calendar_window
from ai_coach.sync.workload_sync import sync_workload
from ai_coach.workload.calendar_eventkit import CalendarError
from ai_coach.workload.config import load_config

TODAY = date(2026, 10, 8)
DAYS = 7
ALL = ("2000-01-01", "2100-01-01")


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.todo = write_todo(
            tmp_path / "todo.json",
            [todo_item(1, "done", "2026-10-07"), todo_item(2, "todo", "2026-10-01")],
        )
        self.hb = write_hb(
            tmp_path / "hb",
            {"secret-done.md": "2026-10-06 10:00"},
            {"secret-pend.md": "2026-10-02 10:00"},
        )
        self.config = load_config(
            write_config(
                tmp_path / "w.toml",
                f'[calendar]\nwork = ["Work"]\npersonal = ["Home"]\nignore = ["Skip"]\n'
                f'[paths]\ntodo = "{self.todo}"\nhb_watch = "{self.hb}"\n',
            )
        )


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


def run(conn: sqlite3.Connection, env: Env, reader: FakeCalendar | None) -> str:
    return sync_workload(conn, reader=reader, config=env.config, days=DAYS, today=TODAY)


def kinds(conn: sqlite3.Connection) -> dict[str, float]:
    found = list_counters(conn, "2026-10-08", "2026-10-08")
    return {c["kind"]: c["value"] for c in found}


def log_rows(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    sql = "SELECT kind, status FROM sync_log ORDER BY id"
    return [(r["kind"], r["status"]) for r in conn.execute(sql).fetchall()]


def test_sync_writes_calendar_events_with_categories(conn: sqlite3.Connection, env: Env) -> None:
    reader = FakeCalendar([raw_event(uid="w"), raw_event(uid="h", calendar="Home")])
    run(conn, env, reader)
    found = {e["uid"]: e["category"] for e in list_calendar_events(conn, *ALL)}
    assert found == {"w": "work", "h": "personal"}


def test_sync_asks_reader_for_window_today_minus_days_to_plus_14(
    conn: sqlite3.Connection, env: Env
) -> None:
    reader = FakeCalendar()
    run(conn, env, reader)
    assert reader.calls == [(date(2026, 10, 1), date(2026, 10, 22))]


def test_sync_skips_ignored_calendar(conn: sqlite3.Connection, env: Env) -> None:
    run(conn, env, FakeCalendar([raw_event(uid="s", calendar="Skip")]))
    assert list_calendar_events(conn, *ALL) == []


def test_sync_stores_unmarked_calendar_as_unknown_and_reports_it(
    conn: sqlite3.Connection, env: Env
) -> None:
    message = run(conn, env, FakeCalendar([raw_event(uid="m", calendar="Mystery")]))
    assert [e["category"] for e in list_calendar_events(conn, *ALL)] == ["unknown"]
    assert "Mystery" in message


def test_sync_strips_calendar_name_when_marking(conn: sqlite3.Connection, env: Env) -> None:
    run(conn, env, FakeCalendar([raw_event(uid="w", calendar="Work ")]))
    assert [e["category"] for e in list_calendar_events(conn, *ALL)] == ["work"]


def test_sync_raw_json_has_no_attendees_or_addresses(conn: sqlite3.Connection, env: Env) -> None:
    run(conn, env, FakeCalendar([raw_event(uid="w")]))
    raw = conn.execute("SELECT raw_json FROM calendar_events").fetchone()[0]
    for word in ("attendee", "organizer", "mailto", "@"):
        assert word not in raw


def test_sync_writes_todo_and_grooming_counters(conn: sqlite3.Connection, env: Env) -> None:
    run(conn, env, FakeCalendar())
    assert kinds(conn) == {
        "todo_open": 1,
        "todo_closed": 0,
        "grooming_done": 0,
        "grooming_pending": 1,
    }
    day = list_counters(conn, "2026-10-07", "2026-10-07", "todo_closed")
    assert [c["value"] for c in day] == [1]
    day = list_counters(conn, "2026-10-06", "2026-10-06", "grooming_done")
    assert [c["value"] for c in day] == [1]


def test_sync_does_not_store_file_names_or_titles(conn: sqlite3.Connection, env: Env) -> None:
    run(conn, env, FakeCalendar())
    dump = "\n".join(conn.iterdump())
    assert "secret-done" not in dump
    assert "secret-pend" not in dump
    assert "Синтетическая задача" not in dump


def test_repeated_sync_does_not_change_data(conn: sqlite3.Connection, env: Env) -> None:
    reader = FakeCalendar([raw_event(uid="w"), raw_event(uid="h", calendar="Home")])
    run(conn, env, reader)
    first = (list_calendar_events(conn, *ALL), list_counters(conn, *ALL))
    run(conn, env, reader)
    assert (list_calendar_events(conn, *ALL), list_counters(conn, *ALL)) == first


def test_sync_keeps_events_before_window(conn: sqlite3.Connection, env: Env) -> None:
    old = stored_event(uid="old", start_at="2026-09-01T10:00:00", end_at="2026-09-01T11:00:00")
    replace_calendar_window(conn, "2026-09-01", "2026-09-01", [old])
    run(conn, env, FakeCalendar([raw_event(uid="new")]))
    assert [e["uid"] for e in list_calendar_events(conn, *ALL)] == ["old", "new"]


def test_sync_removes_event_that_disappeared_from_calendar(
    conn: sqlite3.Connection, env: Env
) -> None:
    run(conn, env, FakeCalendar([raw_event(uid="a"), raw_event(uid="b")]))
    run(conn, env, FakeCalendar([raw_event(uid="a")]))
    assert [e["uid"] for e in list_calendar_events(conn, *ALL)] == ["a"]


def test_sync_writes_workload_log_ok(conn: sqlite3.Connection, env: Env) -> None:
    run(conn, env, FakeCalendar())
    assert log_rows(conn) == [("workload", "ok")]


def test_calendar_error_is_logged_as_error_but_counters_are_written(
    conn: sqlite3.Connection, env: Env
) -> None:
    reader = FakeCalendar(error=CalendarError("нет доступа к календарю"))
    message = run(conn, env, reader)
    assert log_rows(conn) == [("workload", "error")]
    assert kinds(conn)["todo_open"] == 1
    assert kinds(conn)["grooming_pending"] == 1
    assert "нет доступа к календарю" in message


def test_calendar_error_keeps_previous_events(conn: sqlite3.Connection, env: Env) -> None:
    run(conn, env, FakeCalendar([raw_event(uid="a")]))
    run(conn, env, FakeCalendar(error=CalendarError("нет доступа")))
    assert [e["uid"] for e in list_calendar_events(conn, *ALL)] == ["a"]


def test_broken_todo_is_note_other_sources_are_written(conn: sqlite3.Connection, env: Env) -> None:
    env.todo.write_text("{broken", encoding="utf-8")
    run(conn, env, FakeCalendar([raw_event(uid="a")]))
    assert [e["uid"] for e in list_calendar_events(conn, *ALL)] == ["a"]
    assert kinds(conn)["grooming_pending"] == 1
    assert "todo_open" not in kinds(conn)
    assert log_rows(conn) == [("workload", "error")]


def test_missing_hb_watch_does_not_block_calendar_and_todo(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    for p in sorted(env.hb.rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    env.hb.rmdir()
    run(conn, env, FakeCalendar([raw_event(uid="a")]))
    assert [e["uid"] for e in list_calendar_events(conn, *ALL)] == ["a"]
    assert kinds(conn)["todo_open"] == 1


def test_no_calendar_config_skips_calendar_but_reads_todo(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    paths = f'[paths]\ntodo = "{env.todo}"\nhb_watch = "{env.hb}"\n'
    config = load_config(write_config(tmp_path / "nocal.toml", paths))
    reader = FakeCalendar([raw_event(uid="a")])
    sync_workload(conn, reader=reader, config=config, days=DAYS, today=TODAY)
    assert reader.calls == []
    assert list_calendar_events(conn, *ALL) == []
    assert kinds(conn)["todo_open"] == 1


def test_workload_log_does_not_change_first_run_today(conn: sqlite3.Connection, env: Env) -> None:
    run(conn, env, FakeCalendar())
    run(conn, env, FakeCalendar())
    assert sync_runs_on(conn, date.today().isoformat()) == 0


def test_workload_logs_do_not_count_with_one_garmin_sync(
    conn: sqlite3.Connection, env: Env
) -> None:
    today = date.today().isoformat()
    add_sync_log(conn, {"started_at": f"{today} 08:00:00", "kind": "sync", "status": "ok"})
    run(conn, env, FakeCalendar())
    run(conn, env, FakeCalendar())
    assert sync_runs_on(conn, today) == 1


def test_sync_does_not_touch_todo_and_hb_watch(conn: sqlite3.Connection, env: Env) -> None:
    before = tree_state(env.todo, env.hb)
    run(conn, env, FakeCalendar([raw_event(uid="a")]))
    run(conn, env, FakeCalendar([raw_event(uid="a")]))
    assert tree_state(env.todo, env.hb) == before
