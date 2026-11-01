import json
import os
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from workload_fakes import todo_item, tree_state, write_hb, write_todo

from ai_coach.workload.claude import (
    CLAUDE_COUNTERS,
    ClaudeError,
    _repo_name,
    read_claude,
    scan_claude,
)
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


# --- claude ---

TZ5 = timezone(timedelta(hours=5))
CSTART = date(2026, 10, 5)
CEND = date(2026, 10, 8)
NOON = "2026-10-07T10:00:00Z"
ALPHA = "/synthetic/home/alpha"
BETA = "/synthetic/home/beta"
SECRET_TEXT = "синтетический-секрет-реплики"


def record(kind: str, ts: str, **fields: Any) -> dict[str, Any]:
    return {"type": kind, "timestamp": ts, **fields}


def write_session(folder: Path, session_id: str, records: list[dict[str, Any] | str]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    lines = [
        r if isinstance(r, str) else json.dumps(r, separators=(",", ":"), ensure_ascii=False)
        for r in records
    ]
    path = folder / f"{session_id}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def says(ts: str, text: Any = "синтетическая реплика", cwd: str = ALPHA, **fields: Any) -> Any:
    message = {"role": "user", "content": text}
    return record("user", ts, message=message, cwd=cwd, sessionId="sess-1234", **fields)


def asks(ts: str, count: int) -> dict[str, Any]:
    block = {"type": "tool_use", "name": "AskUserQuestion", "input": {"questions": [{}] * count}}
    return record("assistant", ts, message={"role": "assistant", "content": [block]})


def agent(name: str) -> dict[str, Any]:
    return {"type": "agent-setting", "agentSetting": name}


def claude_rows(root: Path) -> list[dict[str, Any]]:
    return read_claude(root, CSTART, CEND, TZ5)


def one(root: Path, records: list[dict[str, Any] | str], kind: str, day: str = "2026-10-07") -> Any:
    write_session(root / "-alpha", "s1", records)
    return value(claude_rows(root), day, kind)


def repos_of(rows: list[dict[str, Any]], day: str) -> Any:
    found = [c["raw_json"] for c in rows if c["date"] == day and c["kind"] == "claude_repos"]
    return found[0]


def system_zone(name: str) -> Iterator[None]:
    old = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


@pytest.fixture
def tz7() -> Iterator[None]:
    """Системный пояс +07 (Etc/GMT-7) на время теста."""
    yield from system_zone("Etc/GMT-7")


@pytest.fixture
def tz_new_york() -> Iterator[None]:
    """Системный пояс с переходом на зимнее время (America/New_York)."""
    yield from system_zone("America/New_York")


@pytest.mark.parametrize(
    "text", ["синтетическая реплика", [{"type": "text", "text": "синтетическая реплика"}]]
)
def test_claude_prompt_is_counted_for_string_and_text_blocks(tmp_path: Path, text: Any) -> None:
    assert one(tmp_path, [says(NOON, text)], "claude_prompts") == 1


@pytest.mark.parametrize(
    ("text", "extra"),
    [
        ([{"type": "tool_result", "content": "x"}], {}),
        ("синтетическая реплика", {"isMeta": True}),
        ("синтетическая реплика", {"isCompactSummary": True}),
        ("<command-name>/x</command-name>", {}),
        ("<local-command-stdout>x</local-command-stdout>", {}),
        ("<task-notification>x</task-notification>", {}),
        ("<bash-input>x</bash-input>", {}),
        ("<system-reminder>x</system-reminder>", {}),
        ("[Request interrupted by user]", {}),
        ("синтетическая реплика", {"entrypoint": "sdk-cli"}),
    ],
)
def test_claude_service_records_are_not_prompts(
    tmp_path: Path, text: Any, extra: dict[str, Any]
) -> None:
    assert one(tmp_path, [says(NOON, text, **extra)], "claude_prompts") == 0


def test_claude_subagent_file_is_not_counted(tmp_path: Path) -> None:
    sub = tmp_path / "-alpha" / "s1" / "subagents"
    write_session(sub, "agent-1", [says(NOON), asks(NOON, 2)])
    rows = claude_rows(tmp_path)
    assert value(rows, "2026-10-07", "claude_prompts") == 0
    assert value(rows, "2026-10-07", "claude_decisions") == 0
    assert value(rows, "2026-10-07", "claude_repos") == 0


def test_claude_late_evening_utc_goes_to_previous_day_at_plus_five(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says("2026-10-06T22:30:00Z")])
    rows = claude_rows(tmp_path)
    assert value(rows, "2026-10-06", "claude_prompts") == 1
    assert value(rows, "2026-10-07", "claude_prompts") == 0


def test_claude_exactly_0400_local_goes_to_today(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says("2026-10-06T23:00:00Z")])
    rows = claude_rows(tmp_path)
    assert value(rows, "2026-10-07", "claude_prompts") == 1
    assert value(rows, "2026-10-06", "claude_prompts") == 0


@pytest.mark.usefixtures("tz7")
def test_claude_default_zone_is_the_system_one(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says("2026-10-07T21:00:00Z")])
    rows = read_claude(tmp_path, CSTART, CEND)
    assert value(rows, "2026-10-08", "claude_prompts") == 1
    assert value(rows, "2026-10-07", "claude_prompts") == 0


def test_claude_day_follows_the_offset_of_each_record_across_dst(tmp_path: Path) -> None:
    """Нью-Йорк: 2026-11-01 в 02:00 EDT (-4) переходит на EST (-5)."""
    zone = ZoneInfo("America/New_York")
    before = says("2026-11-01T08:30:00Z")  # EST: 03:30 -> день 10-31
    after = says("2026-11-01T09:30:00Z")  # EST: 04:30 -> день 11-01
    write_session(tmp_path / "-alpha", "s1", [before, after])
    rows = read_claude(tmp_path, date(2026, 10, 30), date(2026, 11, 1), zone)
    assert value(rows, "2026-10-31", "claude_prompts") == 1
    assert value(rows, "2026-11-01", "claude_prompts") == 1


@pytest.mark.usefixtures("tz_new_york")
def test_claude_system_zone_across_dst_gives_day_by_offset_of_each_record(tmp_path: Path) -> None:
    before = says("2026-11-01T08:30:00Z")  # EST: 03:30 -> день 10-31
    after = says("2026-11-01T09:30:00Z")  # EST: 04:30 -> день 11-01
    summer = says("2026-11-01T04:30:00Z")  # EDT: 00:30 -> день 10-31, вечер
    early = says("2026-10-31T08:30:00Z")  # EDT: 04:30 -> день 10-31 (при -5 был бы 10-30)
    dusk = says("2026-10-31T23:15:00Z")  # EDT: 19:15 -> вечер (при -5 был бы 18:15, не вечер)
    write_session(tmp_path / "-alpha", "s1", [early, dusk, summer, before, after])
    rows = read_claude(tmp_path, date(2026, 10, 30), date(2026, 11, 1))
    assert value(rows, "2026-10-30", "claude_prompts") == 0
    assert value(rows, "2026-10-31", "claude_prompts") == 4
    assert value(rows, "2026-10-31", "claude_prompts_evening") == 3
    assert value(rows, "2026-11-01", "claude_prompts") == 1


def test_claude_records_on_both_sides_of_dst_change_keep_their_own_offset(tmp_path: Path) -> None:
    zone = ZoneInfo("America/New_York")
    summer = says("2026-11-01T04:30:00Z")  # EDT: 00:30 -> день 10-31, вечер
    winter = says("2026-11-01T23:30:00Z")  # EST: 18:30 -> день 11-01, не вечер
    write_session(tmp_path / "-alpha", "s1", [summer, winter])
    rows = read_claude(tmp_path, date(2026, 10, 30), date(2026, 11, 1), zone)
    assert value(rows, "2026-10-31", "claude_prompts_evening") == 1
    assert value(rows, "2026-11-01", "claude_prompts") == 1
    assert value(rows, "2026-11-01", "claude_prompts_evening") == 0


@pytest.mark.parametrize(
    ("ts", "evening"),
    [
        ("2026-10-07T13:59:00Z", 0),
        ("2026-10-07T14:00:00Z", 1),
        ("2026-10-07T22:59:00Z", 1),
    ],
)
def test_claude_evening_is_from_1900_to_0400_local(tmp_path: Path, ts: str, evening: int) -> None:
    got = one(tmp_path, [says(ts)], "claude_prompts_evening")
    assert got == evening


def test_claude_night_prompt_is_evening_of_previous_wellbeing_day(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says("2026-10-07T22:59:00Z")])
    rows = claude_rows(tmp_path)
    assert value(rows, "2026-10-07", "claude_prompts_evening") == 1
    assert value(rows, "2026-10-08", "claude_prompts_evening") == 0


def test_claude_has_row_for_every_day_and_kind_including_zero(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says(NOON)])
    rows = claude_rows(tmp_path)
    assert len(rows) == 4 * len(CLAUDE_COUNTERS)
    assert {(c["date"], c["kind"]) for c in rows} == {
        (f"2026-10-0{d}", k) for d in (5, 6, 7, 8) for k in CLAUDE_COUNTERS
    }
    assert value(rows, "2026-10-06", "claude_prompts") == 0
    assert {c["source"] for c in rows} == {"claude"}


def test_claude_prompts_outside_window_are_ignored(tmp_path: Path) -> None:
    write_session(
        tmp_path / "-alpha", "s1", [says("2026-10-04T10:00:00Z"), says("2026-10-09T10:00:00Z")]
    )
    rows = claude_rows(tmp_path)
    assert sum(c["value"] for c in rows) == 0
    assert {c["date"] for c in rows} == {"2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"}


@pytest.mark.skipif(os.geteuid() == 0, reason="root читает и закрытые файлы")
def test_claude_file_older_than_window_is_not_opened(tmp_path: Path) -> None:
    path = write_session(tmp_path / "-alpha", "s1", [says(NOON)])
    old = datetime(2020, 1, 1).timestamp()
    os.utime(path, (old, old))
    path.chmod(0)
    try:
        rows = claude_rows(tmp_path)
    finally:
        path.chmod(0o644)
    assert value(rows, "2026-10-07", "claude_prompts") == 0


def test_claude_coach_session_is_excluded_from_every_counter(tmp_path: Path) -> None:
    coach = [agent("coach"), says(NOON, cwd="/synthetic/home/gamma"), asks(NOON, 2)]
    write_session(tmp_path / "-gamma", "s1", coach)
    write_session(tmp_path / "-alpha", "s2", [says(NOON)])
    rows = claude_rows(tmp_path)
    assert value(rows, "2026-10-07", "claude_prompts") == 1
    assert value(rows, "2026-10-07", "claude_decisions") == 0
    assert value(rows, "2026-10-07", "claude_repos") == 1
    assert value(rows, "2026-10-07", "claude_switches") == 0
    assert "gamma" not in json.dumps(rows)


def test_claude_session_of_other_agent_is_counted(tmp_path: Path) -> None:
    got = one(tmp_path, [agent("reviewer"), says(NOON), asks(NOON, 2)], "claude_prompts")
    assert got == 1
    assert value(claude_rows(tmp_path), "2026-10-07", "claude_decisions") == 2


def test_claude_decisions_count_questions_of_the_tool_call(tmp_path: Path) -> None:
    assert one(tmp_path, [asks(NOON, 3)], "claude_decisions") == 3


def test_claude_tool_call_without_questions_gives_zero_and_does_not_fail(tmp_path: Path) -> None:
    block = {"type": "tool_use", "name": "AskUserQuestion", "input": {}}
    bare = record("assistant", NOON, message={"role": "assistant", "content": [block]})
    assert one(tmp_path, [bare], "claude_decisions") == 0


def test_claude_other_tool_calls_are_not_decisions(tmp_path: Path) -> None:
    block = {"type": "tool_use", "name": "Bash", "input": {"questions": [{}, {}]}}
    other = record("assistant", NOON, message={"role": "assistant", "content": [block]})
    assert one(tmp_path, [other], "claude_decisions") == 0


def test_claude_repos_are_counted_per_folder_with_names(tmp_path: Path) -> None:
    write_session(tmp_path / "-a", "s1", [says(NOON), says("2026-10-07T10:01:00Z")])
    write_session(tmp_path / "-b", "s2", [says("2026-10-07T10:02:00Z", cwd=BETA)])
    rows = claude_rows(tmp_path)
    assert value(rows, "2026-10-07", "claude_repos") == 2
    assert repos_of(rows, "2026-10-07") == {
        "repos": [{"repo": "alpha", "prompts": 2}, {"repo": "beta", "prompts": 1}]
    }


def test_claude_day_without_prompts_has_no_repos(tmp_path: Path) -> None:
    write_session(tmp_path / "-a", "s1", [says(NOON)])
    rows = claude_rows(tmp_path)
    assert value(rows, "2026-10-06", "claude_repos") == 0
    assert repos_of(rows, "2026-10-06") == {"repos": []}


def test_claude_repos_sorted_by_prompts_descending(tmp_path: Path) -> None:
    write_session(tmp_path / "-a", "s1", [says(NOON, cwd=BETA)])
    write_session(
        tmp_path / "-b", "s2", [says("2026-10-07T10:01:00Z"), says("2026-10-07T10:02:00Z")]
    )
    names = [r["repo"] for r in repos_of(claude_rows(tmp_path), "2026-10-07")["repos"]]
    assert names == ["alpha", "beta"]


def test_claude_folder_name_comes_from_the_shortest_cwd(tmp_path: Path) -> None:
    deeper = says(NOON, cwd=f"{ALPHA}/sub/dir")
    write_session(tmp_path / "-a", "s1", [deeper, says("2026-10-07T10:01:00Z")])
    assert repos_of(claude_rows(tmp_path), "2026-10-07") == {
        "repos": [{"repo": "alpha", "prompts": 2}]
    }


def test_claude_worktree_cwd_gives_the_project_name(tmp_path: Path) -> None:
    write_session(tmp_path / "-a", "s1", [says(NOON, cwd=f"{ALPHA}/.claude/worktrees/feat")])
    assert repos_of(claude_rows(tmp_path), "2026-10-07") == {
        "repos": [{"repo": "alpha", "prompts": 1}]
    }


def test_claude_folders_with_same_project_name_merge(tmp_path: Path) -> None:
    write_session(tmp_path / "-a", "s1", [says(NOON, cwd="/synthetic/one/alpha")])
    write_session(tmp_path / "-b", "s2", [says(NOON, cwd="/synthetic/two/alpha")])
    rows = claude_rows(tmp_path)
    assert value(rows, "2026-10-07", "claude_repos") == 1
    assert repos_of(rows, "2026-10-07") == {"repos": [{"repo": "alpha", "prompts": 2}]}


def test_claude_folder_without_cwd_is_unknown(tmp_path: Path) -> None:
    write_session(tmp_path / "-a", "s1", [says(NOON, cwd="")])
    assert repos_of(claude_rows(tmp_path), "2026-10-07") == {
        "repos": [{"repo": "unknown", "prompts": 1}]
    }


@pytest.mark.parametrize(
    ("cwd", "name"),
    [
        ("/synthetic/home/alpha", "alpha"),
        ("/synthetic/home/alpha/", "alpha"),
        ("/synthetic/home/alpha/.claude/worktrees/feat", "alpha"),
        ("", "unknown"),
        ("/", "unknown"),
    ],
)
def test_claude_repo_name(cwd: str, name: str) -> None:
    assert _repo_name(cwd) == name


def test_claude_switches_a_b_a_is_two_across_files_by_time(tmp_path: Path) -> None:
    write_session(
        tmp_path / "-a", "s1", [says("2026-10-07T10:00:00Z"), says("2026-10-07T10:02:00Z")]
    )
    write_session(tmp_path / "-b", "s2", [says("2026-10-07T10:01:00Z", cwd=BETA)])
    assert value(claude_rows(tmp_path), "2026-10-07", "claude_switches") == 2


def test_claude_switches_a_a_b_is_one(tmp_path: Path) -> None:
    write_session(
        tmp_path / "-a", "s1", [says("2026-10-07T10:00:00Z"), says("2026-10-07T10:01:00Z")]
    )
    write_session(tmp_path / "-b", "s2", [says("2026-10-07T10:02:00Z", cwd=BETA)])
    assert value(claude_rows(tmp_path), "2026-10-07", "claude_switches") == 1


def test_claude_one_folder_has_no_switches(tmp_path: Path) -> None:
    got = one(tmp_path, [says(NOON), says("2026-10-07T10:01:00Z")], "claude_switches")
    assert got == 0


def test_claude_missing_root_gives_no_counters(tmp_path: Path) -> None:
    assert claude_rows(tmp_path / "missing") == []


def test_claude_empty_root_gives_zeros(tmp_path: Path) -> None:
    rows, files, seen = scan_claude(tmp_path, CSTART, CEND, TZ5)
    assert len(rows) == 4 * len(CLAUDE_COUNTERS)
    assert sum(c["value"] for c in rows) == 0
    assert (files, seen) == (0, 0)


def test_claude_broken_line_is_skipped(tmp_path: Path) -> None:
    broken = '{"type":"user", broken'
    assert one(tmp_path, [broken, says(NOON)], "claude_prompts") == 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root читает и закрытые файлы")
def test_claude_unreadable_file_is_error(tmp_path: Path) -> None:
    path = write_session(tmp_path / "-alpha", "s1", [says(NOON)])
    path.chmod(0)
    try:
        with pytest.raises(ClaudeError):
            claude_rows(tmp_path)
    finally:
        path.chmod(0o644)


@pytest.mark.skipif(os.geteuid() == 0, reason="root читает и закрытые файлы")
def test_claude_unreadable_root_is_error(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    root.mkdir()
    root.chmod(0)
    try:
        with pytest.raises(ClaudeError):
            claude_rows(root)
    finally:
        root.chmod(0o755)


def test_claude_files_without_recognized_records_give_zeros_files_and_no_seen(
    tmp_path: Path,
) -> None:
    other = record("summary", NOON, text="синтетика")
    write_session(tmp_path / "-alpha", "s1", [other, "не json"])
    rows, files, seen = scan_claude(tmp_path, CSTART, CEND, TZ5)
    assert sum(c["value"] for c in rows) == 0
    assert (files, seen) == (1, 0)


def test_claude_recognized_records_are_seen(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says(NOON), asks(NOON, 1)])
    _, files, seen = scan_claude(tmp_path, CSTART, CEND, TZ5)
    assert (files, seen) == (1, 2)


def test_claude_records_outside_window_are_not_seen(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says("2026-10-04T10:00:00Z")])
    _, files, seen = scan_claude(tmp_path, CSTART, CEND, TZ5)
    assert (files, seen) == (1, 0)


def test_claude_coach_only_window_is_seen_but_gives_zeros(tmp_path: Path) -> None:
    write_session(tmp_path / "-gamma", "s1", [agent("coach"), says(NOON), asks(NOON, 2)])
    rows, files, seen = scan_claude(tmp_path, CSTART, CEND, TZ5)
    assert sum(c["value"] for c in rows) == 0
    assert files == 1
    assert seen > 0


def test_claude_missing_root_gives_no_rows_and_no_files(tmp_path: Path) -> None:
    assert scan_claude(tmp_path / "missing", CSTART, CEND, TZ5) == ([], 0, 0)


def test_claude_read_is_the_rows_of_scan(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says(NOON)])
    assert claude_rows(tmp_path) == scan_claude(tmp_path, CSTART, CEND, TZ5)[0]


def test_claude_counters_have_no_text_or_paths(tmp_path: Path) -> None:
    write_session(tmp_path / "-synthetic-home-alpha", "sess-1234", [says(NOON, SECRET_TEXT)])
    rows = claude_rows(tmp_path)
    dump = json.dumps(rows, ensure_ascii=False)
    for forbidden in (SECRET_TEXT, "/synthetic", "sess-1234", "-synthetic-home"):
        assert forbidden not in dump
    plain = [c for c in rows if c["kind"] != "claude_repos"]
    assert "alpha" not in json.dumps(plain)
    assert "alpha" in json.dumps(repos_of(rows, "2026-10-07"))


def test_claude_files_are_not_modified(tmp_path: Path) -> None:
    write_session(tmp_path / "-alpha", "s1", [says(NOON), asks(NOON, 1)])
    write_session(tmp_path / "-alpha" / "s1" / "subagents", "agent-1", [says(NOON)])
    before = tree_state(tmp_path)
    claude_rows(tmp_path)
    assert tree_state(tmp_path) == before
