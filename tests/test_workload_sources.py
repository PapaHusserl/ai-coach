import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from workload_fakes import todo_item, tree_state, write_hb, write_todo

from ai_coach.workload.grooming import read_grooming
from ai_coach.workload.todo import TodoError, read_todo

START = date(2026, 10, 5)
TODAY = date(2026, 10, 8)


def value(counters: list[dict[str, Any]], day: str, kind: str) -> Any:
    found = [c["value"] for c in counters if c["date"] == day and c["kind"] == kind]
    return found[0] if found else None


# --- todo ---


def test_todo_open_is_snapshot_of_today(tmp_path: Path) -> None:
    path = write_todo(
        tmp_path / "todo.json",
        [
            todo_item(1, "todo", "2026-10-01"),
            todo_item(2, "doing", "2026-10-02"),
            todo_item(3, "done", "2026-10-06"),
        ],
    )
    counters = read_todo(path, START, TODAY, TODAY)
    assert value(counters, "2026-10-08", "todo_open") == 2
    assert value(counters, "2026-10-07", "todo_open") is None


def test_todo_closed_counts_done_and_dropped_by_updated_day(tmp_path: Path) -> None:
    path = write_todo(
        tmp_path / "todo.json",
        [
            todo_item(1, "done", "2026-10-06"),
            todo_item(2, "dropped", "2026-10-06"),
            todo_item(3, "done", "2026-10-07"),
            todo_item(4, "todo", "2026-10-06"),
        ],
    )
    counters = read_todo(path, START, TODAY, TODAY)
    assert value(counters, "2026-10-06", "todo_closed") == 2
    assert value(counters, "2026-10-07", "todo_closed") == 1


def test_todo_closed_is_written_for_every_day_of_window_including_zero(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "todo.json", [todo_item(1, "done", "2026-10-06")])
    counters = read_todo(path, START, TODAY, TODAY)
    days = [c["date"] for c in counters if c["kind"] == "todo_closed"]
    assert days == ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]
    assert value(counters, "2026-10-05", "todo_closed") == 0


def test_todo_closed_outside_window_is_ignored(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "todo.json", [todo_item(1, "done", "2026-09-01")])
    counters = read_todo(path, START, TODAY, TODAY)
    assert sum(c["value"] for c in counters if c["kind"] == "todo_closed") == 0


def test_todo_empty_list_gives_zeros(tmp_path: Path) -> None:
    counters = read_todo(write_todo(tmp_path / "todo.json", []), START, TODAY, TODAY)
    assert value(counters, "2026-10-08", "todo_open") == 0
    assert value(counters, "2026-10-06", "todo_closed") == 0


def test_todo_missing_file_gives_no_counters(tmp_path: Path) -> None:
    assert read_todo(tmp_path / "nope.json", START, TODAY, TODAY) == []


def test_todo_broken_json_is_error(tmp_path: Path) -> None:
    path = tmp_path / "todo.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(TodoError):
        read_todo(path, START, TODAY, TODAY)


def test_todo_counters_have_no_titles(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "todo.json", [todo_item(1, "todo", "2026-10-01")])
    assert "Синтетическая" not in json.dumps(read_todo(path, START, TODAY, TODAY))


def test_todo_file_is_not_modified(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "todo.json", [todo_item(1, "done", "2026-10-06")])
    before = tree_state(path)
    read_todo(path, START, TODAY, TODAY)
    assert tree_state(path) == before


# --- grooming ---


def test_grooming_done_counts_files_by_mtime_day(tmp_path: Path) -> None:
    root = write_hb(
        tmp_path / "hb",
        {"a.md": "2026-10-06 09:00", "b.md": "2026-10-06 23:30", "c.md": "2026-10-07 00:10"},
        {},
    )
    counters = read_grooming(root, START, TODAY, TODAY)
    assert value(counters, "2026-10-06", "grooming_done") == 2
    assert value(counters, "2026-10-07", "grooming_done") == 1


def test_grooming_done_is_written_for_every_day_including_zero(tmp_path: Path) -> None:
    root = write_hb(tmp_path / "hb", {"a.md": "2026-10-06 09:00"}, {})
    counters = read_grooming(root, START, TODAY, TODAY)
    days = [c["date"] for c in counters if c["kind"] == "grooming_done"]
    assert days == ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]
    assert value(counters, "2026-10-05", "grooming_done") == 0


def test_grooming_done_outside_window_is_ignored(tmp_path: Path) -> None:
    root = write_hb(tmp_path / "hb", {"old.md": "2026-08-01 09:00"}, {})
    counters = read_grooming(root, START, TODAY, TODAY)
    assert sum(c["value"] for c in counters if c["kind"] == "grooming_done") == 0


def test_grooming_pending_is_snapshot_of_today(tmp_path: Path) -> None:
    root = write_hb(tmp_path / "hb", {}, {"p1.md": "2026-10-01 09:00", "p2.md": "2026-10-02 09:00"})
    counters = read_grooming(root, START, TODAY, TODAY)
    assert value(counters, "2026-10-08", "grooming_pending") == 2
    assert value(counters, "2026-10-07", "grooming_pending") is None


def test_grooming_counts_all_files_not_only_with_pr(tmp_path: Path) -> None:
    root = write_hb(tmp_path / "hb", {"a.md": "2026-10-06 09:00"}, {})
    no_pr = root / "done" / "no_pr.md"
    no_pr.write_text("без pr\n", encoding="utf-8")
    moment = datetime(2026, 10, 6, 10, 0).timestamp()
    os.utime(no_pr, (moment, moment))
    counters = read_grooming(root, START, TODAY, TODAY)
    assert value(counters, "2026-10-06", "grooming_done") == 2


def test_grooming_empty_dirs_give_zeros(tmp_path: Path) -> None:
    root = write_hb(tmp_path / "hb", {}, {})
    counters = read_grooming(root, START, TODAY, TODAY)
    assert value(counters, "2026-10-08", "grooming_pending") == 0
    assert value(counters, "2026-10-06", "grooming_done") == 0


def test_grooming_missing_root_gives_no_counters(tmp_path: Path) -> None:
    assert read_grooming(tmp_path / "nope", START, TODAY, TODAY) == []


def test_grooming_counters_have_no_file_names(tmp_path: Path) -> None:
    root = write_hb(
        tmp_path / "hb",
        {"secret-name-done.md": "2026-10-06 09:00"},
        {"secret-name-pending.md": "2026-10-06 09:00"},
    )
    assert "secret-name" not in json.dumps(read_grooming(root, START, TODAY, TODAY))


def test_grooming_files_are_not_modified(tmp_path: Path) -> None:
    root = write_hb(tmp_path / "hb", {"a.md": "2026-10-06 09:00"}, {"b.md": "2026-10-06 09:00"})
    before = tree_state(root)
    read_grooming(root, START, TODAY, TODAY)
    assert tree_state(root) == before
