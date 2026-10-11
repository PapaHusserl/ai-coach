"""coach event list/write/remove/cancel: запись тренера в календарь коуча (шаг v2.6)."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner
from workload_fakes import FakeCalendarWriter, FlakyCommitConn, coach_event, write_config

from ai_coach.cli import agenda as agenda_cli
from ai_coach.cli import main
from ai_coach.store.agenda import add_event, get_event
from ai_coach.store.db import open_db

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("event не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_network)
    return db


@pytest.fixture
def writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeCalendarWriter:
    """Конфиг с [coach] и подменённый писатель; созданные писатели - в writer.made."""
    config = write_config(tmp_path / "coach.toml", '[coach]\ncalendar = "Coach"\n')
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))
    fake = FakeCalendarWriter()
    fake.made = []  # type: ignore[attr-defined]

    def make(*args: Any, **kwargs: Any) -> FakeCalendarWriter:
        fake.made.append((args, kwargs))  # type: ignore[attr-defined]
        return fake

    monkeypatch.setattr(agenda_cli, "CalendarWriter", make)
    return fake


def seed(db: Path, **fields: Any) -> int:
    conn = open_db(db)
    try:
        event_id = add_event(conn, coach_event(**fields))
        conn.commit()
        return event_id
    finally:
        conn.close()


def state(db: Path, event_id: int) -> dict[str, Any]:
    conn = open_db(db)
    try:
        row = get_event(conn, event_id)
        assert row is not None
        return row
    finally:
        conn.close()


def run(*args: str) -> Any:
    return runner.invoke(main.app, ["event", *args])


def test_write_makes_event_written(isolated: Path, writer: FakeCalendarWriter) -> None:
    event_id = seed(isolated)
    result = run("write", str(event_id))
    assert result.exit_code == 0, result.output
    row = state(isolated, event_id)
    assert (row["status"], row["calendar_uid"]) == ("written", "fake-uid-1")


def test_write_uses_calendar_from_config(isolated: Path, writer: FakeCalendarWriter) -> None:
    run("write", str(seed(isolated)))
    args, kwargs = writer.made[0]  # type: ignore[attr-defined]
    assert "Coach" in [*args, *kwargs.values()]


def test_write_several_ids(isolated: Path, writer: FakeCalendarWriter) -> None:
    ids = [seed(isolated), seed(isolated), seed(isolated)]
    result = run("write", *map(str, ids))
    assert result.exit_code == 0, result.output
    assert [state(isolated, i)["status"] for i in ids] == ["written"] * 3
    assert len(writer.written) == 3


def test_write_with_bad_id_in_middle_keeps_first_written(
    isolated: Path, writer: FakeCalendarWriter
) -> None:
    first, bad, last = seed(isolated), seed(isolated, status="cancelled"), seed(isolated)
    result = run("write", str(first), str(bad), str(last))
    assert result.exit_code != 0
    assert state(isolated, first)["status"] == "written"
    assert state(isolated, bad)["status"] == "cancelled"


def test_write_missing_id_fails(isolated: Path, writer: FakeCalendarWriter) -> None:
    result = run("write", "999")
    assert result.exit_code != 0
    assert writer.written == []


def test_write_already_written_does_not_duplicate(
    isolated: Path, writer: FakeCalendarWriter
) -> None:
    event_id = seed(isolated)
    run("write", str(event_id))
    result = run("write", str(event_id))
    assert result.exit_code != 0
    assert len(writer.written) == 1


def test_calendar_error_keeps_draft(
    isolated: Path, writer: FakeCalendarWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach.workload.calendar_eventkit import CalendarError

    writer.error = CalendarError("нет доступа")
    event_id = seed(isolated)
    result = run("write", str(event_id))
    assert result.exit_code != 0
    assert state(isolated, event_id)["status"] == "draft"


def test_write_without_coach_section_fails_before_eventkit(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("писатель не должен создаваться без [coach]")

    monkeypatch.setattr(agenda_cli, "CalendarWriter", forbidden)
    event_id = seed(isolated)
    result = run("write", str(event_id))
    assert result.exit_code != 0
    assert state(isolated, event_id)["status"] == "draft"


def test_remove_without_coach_section_fails_before_eventkit(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("писатель не должен создаваться без [coach]")

    monkeypatch.setattr(agenda_cli, "CalendarWriter", forbidden)
    event_id = seed(isolated, status="written", calendar_uid="u1")
    result = run("remove", str(event_id))
    assert result.exit_code != 0
    assert state(isolated, event_id)["status"] == "written"


def test_remove_written_event(isolated: Path, writer: FakeCalendarWriter) -> None:
    event_id = seed(isolated, status="written", calendar_uid="u1")
    result = run("remove", str(event_id))
    assert result.exit_code == 0, result.output
    row = state(isolated, event_id)
    assert (row["status"], row["removed_by"]) == ("removed", "cli")
    assert writer.removed == [("u1", False)]


def test_remove_foreign_uid_fails_and_keeps_status(
    isolated: Path, writer: FakeCalendarWriter
) -> None:
    writer.foreign = ("alien",)
    event_id = seed(isolated, status="written", calendar_uid="alien")
    result = run("remove", str(event_id))
    assert result.exit_code != 0
    assert state(isolated, event_id)["status"] == "written"


def test_remove_draft_fails(isolated: Path, writer: FakeCalendarWriter) -> None:
    event_id = seed(isolated)
    result = run("remove", str(event_id))
    assert result.exit_code != 0
    assert writer.removed == []


def test_cancel_draft_needs_no_calendar(isolated: Path) -> None:
    event_id = seed(isolated)
    result = run("cancel", str(event_id))
    assert result.exit_code == 0, result.output
    assert state(isolated, event_id)["status"] == "cancelled"


def test_cancel_written_fails(isolated: Path) -> None:
    event_id = seed(isolated, status="written", calendar_uid="u1")
    result = run("cancel", str(event_id))
    assert result.exit_code != 0
    assert state(isolated, event_id)["status"] == "written"


def test_list_shows_events_with_ids_and_statuses(isolated: Path) -> None:
    first = seed(isolated, title="Первая синтетика")
    second = seed(isolated, title="Вторая синтетика", status="written", calendar_uid="u1")
    result = run("list")
    assert result.exit_code == 0, result.output
    assert "Первая синтетика" in result.output
    assert "Вторая синтетика" in result.output
    assert "draft" in result.output
    assert "written" in result.output
    assert str(first) in result.output
    assert str(second) in result.output


def test_list_works_without_coach_section_and_does_not_touch_calendar(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("list не трогает календарь")

    monkeypatch.setattr(agenda_cli, "CalendarWriter", forbidden)
    seed(isolated)
    assert run("list").exit_code == 0


def test_list_on_empty_database(isolated: Path) -> None:
    assert run("list").exit_code == 0


def test_write_commits_each_event_before_next(isolated: Path, writer: FakeCalendarWriter) -> None:
    first, bad = seed(isolated), seed(isolated, status="removed")
    run("write", str(first), str(bad))
    conn = sqlite3.connect(isolated)
    try:
        sql = "SELECT status FROM coach_events WHERE id = ?"
        assert conn.execute(sql, (first,)).fetchone()[0] == "written"
    finally:
        conn.close()


def test_commit_error_for_one_id_does_not_stop_next(
    isolated: Path, writer: FakeCalendarWriter, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = seed(isolated), seed(isolated)
    real_open = agenda_cli.open_db
    flaky: list[FlakyCommitConn] = []

    def open_flaky() -> Any:
        flaky.append(FlakyCommitConn(real_open(), fail=1))
        return flaky[0]

    monkeypatch.setattr(agenda_cli, "open_db", open_flaky)
    result = run("write", str(first), str(second))
    assert result.exit_code == 1
    assert state(isolated, first)["status"] == "draft"
    assert state(isolated, second)["status"] == "written"
