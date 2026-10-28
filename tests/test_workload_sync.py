import json
import os
import sqlite3
import urllib.request
from datetime import date
from pathlib import Path

import pytest
from workload_fakes import (
    FakeAw,
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
from ai_coach.sync.workload_sync import read_counters, resolve_config, sync_workload
from ai_coach.workload.calendar_eventkit import CalendarError
from ai_coach.workload.config import WorkloadConfig, default_config, load_config
from ai_coach.workload.screen import AwReader, ScreenError

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


HOUR = 3600
SCREEN_TITLE = "СЕКРЕТНЫЙ_ЗАГОЛОВОК_ОКНА"


def with_screen(env: Env, tmp_path: Path) -> WorkloadConfig:
    text = (
        f'[calendar]\nwork = ["Work"]\n[paths]\ntodo = "{env.todo}"\nhb_watch = "{env.hb}"\n'
        '[screen]\nwork = ["Alpha Editor"]\nhobby = ["BetaGame"]\n'
    )
    return load_config(write_config(tmp_path / "screen.toml", text))


ScreenDays = dict[str, tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]]


def screen_day() -> ScreenDays:
    whole: dict[tuple[str, str], float] = {("alpha editor", ""): 3 * HOUR, ("betagame", ""): HOUR}
    return {"2026-10-08": (whole, {("alpha editor", ""): HOUR}), "2026-10-07": (whole, {})}


def screen_counters(conn: sqlite3.Connection) -> list[tuple[str, str, float, str]]:
    found = list_counters(conn, *ALL)
    return [
        (c["date"], c["kind"], c["value"], c["source"])
        for c in found
        if c["kind"].startswith("screen_")
    ]


def run_screen(
    conn: sqlite3.Connection, config: WorkloadConfig, aw: FakeAw | AwReader | None
) -> str:
    return sync_workload(
        conn, reader=FakeCalendar(), config=config, days=DAYS, today=TODAY, screen=aw
    )


def test_sync_writes_screen_counters_with_source_screen(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    run_screen(conn, with_screen(env, tmp_path), FakeAw(screen_day()))
    found = screen_counters(conn)
    assert ("2026-10-08", "screen_work_hours", 3.0, "screen") in found
    assert ("2026-10-08", "screen_hobby_hours", 1.0, "screen") in found
    assert ("2026-10-08", "screen_evening_hours", 1.0, "screen") in found
    assert ("2026-10-07", "screen_work_hours", 3.0, "screen") in found
    assert len(found) == 8


def test_sync_asks_screen_for_days_first_to_today(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    aw = FakeAw()
    run_screen(conn, with_screen(env, tmp_path), aw)
    assert len(aw.calls) == 1
    periods = aw.calls[0]
    assert len(periods) == 2 * (DAYS + 1)
    assert periods[0][0].date() == date(2026, 10, 1)
    assert periods[-1][1].date() == date(2026, 10, 9)


def test_sync_screen_counters_are_counted_in_summary(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    config = with_screen(env, tmp_path)
    plain = run_screen(conn, config, FakeAw())
    with_aw = run_screen(conn, config, FakeAw(screen_day()))
    assert plain.split(";")[0] != with_aw.split(";")[0]


def test_sync_screen_error_is_noted_other_sources_are_written(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    aw = FakeAw(error=ScreenError("aw-server не отвечает"))
    reader = FakeCalendar([raw_event(uid="a")])
    message = sync_workload(
        conn, reader=reader, config=with_screen(env, tmp_path), days=DAYS, today=TODAY, screen=aw
    )
    assert "экран: aw-server не отвечает" in message
    assert log_rows(conn) == [("workload", "error")]
    assert [e["uid"] for e in list_calendar_events(conn, *ALL)] == ["a"]
    assert kinds(conn)["todo_open"] == 1
    assert kinds(conn)["grooming_pending"] == 1
    assert screen_counters(conn) == []


def test_sync_screen_error_keeps_previous_screen_counters(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    config = with_screen(env, tmp_path)
    run_screen(conn, config, FakeAw(screen_day()))
    before = screen_counters(conn)
    run_screen(conn, config, FakeAw(error=ScreenError("нет")))
    assert screen_counters(conn) == before


def test_calendar_error_does_not_stop_screen(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    reader = FakeCalendar(error=CalendarError("нет доступа"))
    sync_workload(
        conn,
        reader=reader,
        config=with_screen(env, tmp_path),
        days=DAYS,
        today=TODAY,
        screen=FakeAw(screen_day()),
    )
    assert len(screen_counters(conn)) == 8


def test_no_screen_section_says_screen_is_not_configured(
    conn: sqlite3.Connection, env: Env
) -> None:
    aw = FakeAw(screen_day())
    message = run_screen(conn, env.config, aw)
    assert "экран не настроен" in message
    assert aw.calls == []
    assert screen_counters(conn) == []
    assert log_rows(conn) == [("workload", "ok")]


def test_screen_unmarked_note_goes_to_message(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    day: ScreenDays = {
        "2026-10-08": ({("zeta tool", ""): 2 * HOUR, ("alpha editor", ""): 8 * HOUR}, {})
    }
    message = run_screen(conn, with_screen(env, tmp_path), FakeAw(day))
    assert "неразмеченное" in message
    assert "zeta" not in message
    assert log_rows(conn) == [("workload", "ok")]


def test_repeated_sync_replaces_screen_values(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    config = with_screen(env, tmp_path)
    run_screen(conn, config, FakeAw(screen_day()))
    smaller: ScreenDays = {"2026-10-08": ({("alpha editor", ""): HOUR}, {})}
    run_screen(conn, config, FakeAw(smaller))
    found = {(d, k): v for d, k, v, _ in screen_counters(conn)}
    assert found[("2026-10-08", "screen_work_hours")] == 1.0
    assert len([1 for d, _ in found if d == "2026-10-08"]) == 4


def test_screen_sync_writes_one_workload_log_row(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    run_screen(conn, with_screen(env, tmp_path), FakeAw(screen_day()))
    assert log_rows(conn) == [("workload", "ok")]


def test_sync_with_screen_does_not_touch_todo_and_hb_watch(
    conn: sqlite3.Connection, env: Env, tmp_path: Path
) -> None:
    before = tree_state(env.todo, env.hb)
    config = with_screen(env, tmp_path)
    run_screen(conn, config, FakeAw(screen_day()))
    run_screen(conn, config, FakeAw(screen_day()))
    assert tree_state(env.todo, env.hb) == before


def test_sync_through_aw_reader_stores_no_window_titles(
    conn: sqlite3.Connection, env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        def read(self) -> bytes:
            events = [
                {
                    "duration": 3600,
                    "data": {"app": "Alpha Editor", "title": SCREEN_TITLE, "$category": ["work"]},
                }
            ]
            return json.dumps([events] * 2 * (DAYS + 1)).encode("utf-8")

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Response())
    config = with_screen(env, tmp_path)
    assert config.screen is not None
    message = run_screen(conn, config, AwReader(config.screen))
    assert screen_counters(conn)
    assert SCREEN_TITLE not in "\n".join(conn.iterdump())
    assert SCREEN_TITLE not in message


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


@pytest.mark.skipif(os.geteuid() == 0, reason="под root chmod(0) не запрещает чтение")
def test_all_sources_failing_keep_notes_then_errors_in_order(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    todo = tmp_path / "todo.json"
    todo.write_text("{broken", encoding="utf-8")
    hb = write_hb(tmp_path / "hb", {"a.md": "2026-10-06 10:00"}, {})
    text = f'[paths]\ntodo = "{todo}"\nhb_watch = "{hb}"\n[screen]\nwork = ["Alpha Editor"]\n'
    config = load_config(write_config(tmp_path / "w.toml", text))
    (hb / "done").chmod(0)
    try:
        message = sync_workload(
            conn,
            reader=FakeCalendar(),
            config=config,
            days=DAYS,
            today=TODAY,
            screen=FakeAw(error=ScreenError("aw-server не отвечает")),
        )
    finally:
        (hb / "done").chmod(0o755)
    assert message == (
        "событий 0, счётчиков 0; календарь не настроен; "
        "туду: todo не читается: не JSON; "
        "груминг: hb-watch не читается: PermissionError; "
        "экран: aw-server не отвечает"
    )
    assert log_rows(conn) == [("workload", "error")]


def test_broken_config_file_is_last_error_calendar_skipped_default_paths_read(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    write_todo(home / ".claude" / "todo.json", [todo_item(1, "todo", "2026-10-01")])
    write_hb(home / "bin" / "hb-watch", {}, {"p.md": "2026-10-02 10:00"})
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv(
        "AI_COACH_WORKLOAD_CONFIG", str(write_config(tmp_path / "bad.toml", "[calendar\nwork = "))
    )
    reader = FakeCalendar([raw_event(uid="a")])
    message = sync_workload(conn, days=DAYS, today=TODAY, reader=reader)
    parts = message.split("; ")
    assert parts[1:3] == ["календарь не настроен", "экран не настроен"]
    assert parts[3].startswith("Конфиг нагрузки не читается (bad.toml)")
    assert len(parts) == 4
    assert reader.calls == []
    assert kinds(conn)["todo_open"] == 1
    assert kinds(conn)["grooming_pending"] == 1
    assert log_rows(conn) == [("workload", "error")]


def test_resolve_config_returns_given_config_as_is(env: Env) -> None:
    errors: list[str] = []
    assert resolve_config(env.config, errors) is env.config
    assert errors == []


def test_resolve_config_none_loads_file_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_config(tmp_path / "ok.toml", '[calendar]\nwork = ["Work"]\n')
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(path))
    errors: list[str] = []
    assert resolve_config(None, errors).category("Work") == "work"
    assert errors == []


def test_resolve_config_broken_file_gives_default_and_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_config(tmp_path / "bad.toml", "[calendar\nwork = ")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(path))
    errors: list[str] = []
    config = resolve_config(None, errors)
    assert config == default_config()
    assert len(errors) == 1
    assert errors[0].startswith("Конфиг нагрузки не читается (bad.toml)")


def test_read_counters_no_screen_section_notes_it_and_reads_other_sources(env: Env) -> None:
    notes: list[str] = []
    errors: list[str] = []
    found = read_counters(env.config, None, date(2026, 10, 1), TODAY, notes, errors)
    assert notes == ["экран не настроен"]
    assert errors == []
    assert {c["kind"] for c in found} == {
        "todo_closed",
        "todo_open",
        "grooming_done",
        "grooming_pending",
    }


def test_read_counters_screen_error_goes_to_errors_other_counters_stay(
    env: Env, tmp_path: Path
) -> None:
    notes: list[str] = []
    errors: list[str] = []
    aw = FakeAw(error=ScreenError("нет связи"))
    found = read_counters(with_screen(env, tmp_path), aw, date(2026, 10, 1), TODAY, notes, errors)
    assert errors == ["экран: нет связи"]
    assert notes == []
    assert "todo_open" in {c["kind"] for c in found}


def test_read_counters_appends_to_existing_lists(env: Env) -> None:
    notes = ["раньше"]
    errors = ["календарь: x"]
    read_counters(env.config, None, date(2026, 10, 1), TODAY, notes, errors)
    assert notes == ["раньше", "экран не настроен"]
    assert errors == ["календарь: x"]
