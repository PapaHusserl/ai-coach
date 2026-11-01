import sqlite3

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, call_text, rows, tool_names
from workload_fakes import stored_event

from ai_coach.mcp_server.server import TOOLS
from ai_coach.store.workload import replace_calendar_window, upsert_counter

DAY = "2026-10-07"
TITLE = "Секретное название встречи"
RAW = "SECRET_RAW_PAYLOAD"


def put(conn: sqlite3.Connection, day: str, start: str, end: str, **fields: object) -> None:
    event = stored_event(
        uid=f"u-{day}-{start}",
        start_at=f"{day}T{start}:00",
        end_at=f"{day}T{end}:00",
        title=TITLE,
        raw_json={"secret": RAW},
        **fields,
    )
    replace_calendar_window(conn, day, day, [event])


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_workload" in tool_names(conn)


def test_workload_has_rows_and_truncated(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_workload", date_from=DAY, date_to=DAY)
    assert set(answer) == {"rows", "truncated"}
    assert answer["truncated"] is False


def test_workload_returns_row_per_day_inclusive(conn: sqlite3.Connection) -> None:
    found = rows(conn, "get_workload", date_from="2026-10-06", date_to=DAY)
    assert [r["date"] for r in found] == ["2026-10-06", DAY]


def test_workload_row_has_hours_and_counters(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    upsert_counter(
        conn,
        {
            "date": DAY,
            "kind": "todo_closed",
            "value": 2,
            "source": "x",
            "raw_json": {},
            "synced_at": "2026-10-08T10:00:00",
        },
    )
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert row["work_hours"] == pytest.approx(2.0)
    assert row["todo_closed"] == 2


def test_workload_rows_have_calendar_demand_hours(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00", demand="challenge")
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert row["challenge_hours"] == pytest.approx(2.0)
    assert row["hindrance_hours"] == 0


def test_workload_events_have_demand(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00", demand="hindrance")
    answer = call(conn, "get_workload", date_from=DAY, date_to=DAY, events=True)
    assert [e["demand"] for e in answer["rows"][0]["events"]] == ["hindrance"]


def test_workload_description_mentions_calendar_demand() -> None:
    text = TOOLS["get_workload"][1]
    assert "challenge/hindrance_hours - вызов и помехи внутри work_hours" in text
    assert "рабочая встреча без правила - помеха" in text


SCREEN_KINDS = (
    "screen_work_hours",
    "screen_hobby_hours",
    "screen_browser_hours",
    "screen_evening_hours",
)


def screen(conn: sqlite3.Connection, day: str, kind: str, value: float) -> None:
    upsert_counter(
        conn,
        {
            "date": day,
            "kind": kind,
            "value": value,
            "source": "screen",
            "raw_json": None,
            "synced_at": "2026-10-08T10:00:00",
        },
    )


def test_workload_row_has_screen_hours(conn: sqlite3.Connection) -> None:
    for number, kind in enumerate(SCREEN_KINDS):
        screen(conn, DAY, kind, 1.25 + number)
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert [row[k] for k in SCREEN_KINDS] == [1.25, 2.25, 3.25, 4.25]


def test_workload_screen_fields_are_none_without_data(conn: sqlite3.Connection) -> None:
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert all(row[k] is None for k in SCREEN_KINDS)


def test_workload_screen_zero_stays_zero(conn: sqlite3.Connection) -> None:
    screen(conn, DAY, "screen_work_hours", 0)
    assert rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]["screen_work_hours"] == 0


def test_workload_with_events_true_still_has_screen_hours_and_no_app_names(
    conn: sqlite3.Connection,
) -> None:
    screen(conn, DAY, "screen_work_hours", 2.5)
    text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=True)
    assert "2.5" in text
    assert "raw_json" not in text


def test_workload_range_of_92_days_is_allowed(conn: sqlite3.Connection) -> None:
    call(conn, "get_workload", date_from="2026-07-08", date_to="2026-10-07")


def test_workload_range_over_92_days_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_workload", date_from="2026-07-07", date_to="2026-10-07")


def test_workload_bad_date_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_workload", date_from="07.10.2026", date_to=DAY)


def test_workload_end_before_start_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_workload", date_from=DAY, date_to="2026-10-01")


def test_workload_without_events_has_no_titles(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    assert TITLE not in call_text(conn, "get_workload", date_from=DAY, date_to=DAY)


def test_workload_events_false_has_no_titles(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=False)
    assert TITLE not in text


def test_workload_events_on_one_day_has_titles(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=True)
    assert TITLE in text


def test_workload_events_on_range_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "get_workload", date_from="2026-10-06", date_to=DAY, events=True)


def test_workload_never_returns_raw_json(conn: sqlite3.Connection) -> None:
    put(conn, DAY, "10:00", "12:00")
    for events in (False, True):
        text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY, events=events)
        assert RAW not in text
        assert "raw_json" not in text


REPOS = [{"repo": "alpha-repo", "prompts": 5}, {"repo": "beta-repo", "prompts": 2}]


def put_claude(
    conn: sqlite3.Connection, day: str, kind: str, value: int, raw: object = None
) -> None:
    upsert_counter(
        conn,
        {
            "date": day,
            "kind": kind,
            "value": value,
            "source": "claude",
            "raw_json": raw,
            "synced_at": "2026-10-08T10:00:00",
        },
    )


def put_claude_day(conn: sqlite3.Connection, day: str) -> None:
    put_claude(conn, day, "claude_prompts", 7)
    put_claude(conn, day, "claude_prompts_evening", 3)
    put_claude(conn, day, "claude_decisions", 4)
    put_claude(conn, day, "claude_repos", 2, {"repos": REPOS})
    put_claude(conn, day, "claude_switches", 1)


def test_workload_claude_counters_are_integers(conn: sqlite3.Connection) -> None:
    put_claude_day(conn, DAY)
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert row["claude_prompts"] == 7
    assert row["claude_prompts_evening"] == 3
    assert row["claude_decisions"] == 4
    assert row["claude_repos"] == 2
    assert row["claude_switches"] == 1
    for kind in ("claude_prompts", "claude_decisions", "claude_repos"):
        assert type(row[kind]) is int


def test_workload_claude_counters_without_data_are_none(conn: sqlite3.Connection) -> None:
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY)[0]
    assert row["claude_prompts"] is None
    assert row["claude_switches"] is None


def test_workload_without_events_has_no_claude_repo_names(conn: sqlite3.Connection) -> None:
    put_claude_day(conn, DAY)
    text = call_text(conn, "get_workload", date_from=DAY, date_to=DAY)
    assert "claude_repos_names" not in text
    assert "alpha-repo" not in text


def test_workload_range_has_no_claude_repo_names(conn: sqlite3.Connection) -> None:
    put_claude_day(conn, DAY)
    text = call_text(conn, "get_workload", date_from="2026-10-06", date_to=DAY)
    assert "claude_repos_names" not in text
    assert "alpha-repo" not in text


def test_workload_events_on_one_day_has_claude_repo_names(conn: sqlite3.Connection) -> None:
    put_claude_day(conn, DAY)
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY, events=True)[0]
    assert row["claude_repos_names"] == REPOS


def test_workload_events_without_claude_data_has_none_names(conn: sqlite3.Connection) -> None:
    row = rows(conn, "get_workload", date_from=DAY, date_to=DAY, events=True)[0]
    assert row["claude_repos_names"] is None


def test_get_workload_description_mentions_claude() -> None:
    description = TOOLS["get_workload"][1]
    for name in ("claude_prompts", "claude_decisions", "claude_repos_names"):
        assert name in description
