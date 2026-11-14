"""Правка плана из пульта: apply_event (шаг П4, партия 1)."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from workload_fakes import FakeCalendarWriter, coach_event

from ai_coach.store.agenda import add_event, get_event, list_events
from ai_coach.web.errors import MarkError, NoEvent
from ai_coach.workload import CalendarError, WorkloadConfigError

NOW = datetime(2026, 10, 11, 12, 0, 0)
DAY = "2026-10-10"


def apply(conn: sqlite3.Connection, payload: dict[str, Any], writer: Any = None) -> Any:
    from ai_coach.web.plan import apply_event

    def factory() -> Any:
        if writer is None:
            raise AssertionError("писатель не должен вызываться")
        return writer

    return apply_event(conn, payload, NOW, factory)


def stored(conn: sqlite3.Connection, **fields: Any) -> int:
    event_id = add_event(conn, coach_event(**fields))
    conn.commit()
    return event_id


def move(event_id: int, start_at: str) -> dict[str, Any]:
    return {"action": "move", "id": event_id, "date": DAY, "start_at": start_at}


def resize(event_id: int, end_at: str) -> dict[str, Any]:
    return {"action": "resize", "id": event_id, "date": DAY, "end_at": end_at}


def create(**fields: Any) -> dict[str, Any]:
    return {
        "action": "create",
        "kind": "task",
        "title": "Новый пункт",
        "start_at": "2026-10-11T15:00:00",
        "end_at": "2026-10-11T15:30:00",
        "category": "work",
    } | fields


def test_move_draft_updates_row_without_writer(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    result = apply(conn, move(event_id, "2026-10-11T15:30:00"))
    assert result == {
        "start_at": "2026-10-11T15:30:00",
        "end_at": "2026-10-11T17:30:00",
        "date": "2026-10-11",
    }
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["start_at"], row["date"]) == ("2026-10-11T15:30:00", "2026-10-11")


def test_move_written_goes_to_calendar_then_database(conn: sqlite3.Connection) -> None:
    event_id = stored(conn, status="written", calendar_uid="u1")
    writer = FakeCalendarWriter()
    apply(conn, move(event_id, "2026-10-11T15:30:00"), writer)
    assert writer.moved == [("u1", "2026-10-11T15:30:00", "2026-10-11T17:30:00")]
    row = get_event(conn, event_id)
    assert row is not None
    assert row["start_at"] == "2026-10-11T15:30:00"


def test_move_written_writer_error_keeps_database_and_gives_text(
    conn: sqlite3.Connection,
) -> None:
    event_id = stored(conn, status="written", calendar_uid="u1")
    before = get_event(conn, event_id)
    with pytest.raises(MarkError, match="календарь сломан"):
        apply(
            conn,
            move(event_id, "2026-10-11T15:30:00"),
            FakeCalendarWriter(CalendarError("календарь сломан")),
        )
    assert get_event(conn, event_id) == before


def test_move_written_without_calendar_config_is_mark_error(conn: sqlite3.Connection) -> None:
    from ai_coach.web.plan import apply_event

    event_id = stored(conn, status="written", calendar_uid="u1")

    def factory() -> Any:
        raise WorkloadConfigError("Календарь коуча не задан.")

    with pytest.raises(MarkError, match="Календарь коуча не задан"):
        apply_event(conn, move(event_id, "2026-10-11T15:30:00"), NOW, factory)


def test_move_repeating_is_mark_error(conn: sqlite3.Connection) -> None:
    event_id = stored(conn, kind="checkin", category=None, repeat="daily")
    with pytest.raises(MarkError, match="повторяющееся"):
        apply(conn, move(event_id, "2026-10-11T15:30:00"))


def test_move_unknown_event_is_no_event(conn: sqlite3.Connection) -> None:
    with pytest.raises(NoEvent):
        apply(conn, move(999, "2026-10-11T15:30:00"))


@pytest.mark.parametrize("status", ["cancelled", "removed"])
def test_move_inactive_event_is_mark_error(conn: sqlite3.Connection, status: str) -> None:
    event_id = stored(conn, status=status, calendar_uid="u1")
    with pytest.raises(MarkError):
        apply(conn, move(event_id, "2026-10-11T15:30:00"))


def test_resize_draft_changes_only_end(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    result = apply(conn, resize(event_id, "2026-10-10T13:00:00"))
    assert result == {
        "start_at": "2026-10-10T10:00:00",
        "end_at": "2026-10-10T13:00:00",
        "date": DAY,
    }
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["start_at"], row["end_at"]) == ("2026-10-10T10:00:00", "2026-10-10T13:00:00")


def test_resize_written_gives_calendar_new_end(conn: sqlite3.Connection) -> None:
    event_id = stored(conn, status="written", calendar_uid="u2")
    writer = FakeCalendarWriter()
    apply(conn, resize(event_id, "2026-10-10T11:00:00"), writer)
    assert writer.moved == [("u2", "2026-10-10T10:00:00", "2026-10-10T11:00:00")]
    row = get_event(conn, event_id)
    assert row is not None
    assert row["end_at"] == "2026-10-10T11:00:00"


@pytest.mark.parametrize("end_at", ["2026-10-10T10:00:00", "2026-10-10T09:00:00"])
def test_resize_end_not_after_start_is_mark_error(conn: sqlite3.Connection, end_at: str) -> None:
    event_id = stored(conn)
    before = get_event(conn, event_id)
    with pytest.raises(MarkError):
        apply(conn, resize(event_id, end_at))
    assert get_event(conn, event_id) == before


def test_resize_repeating_is_mark_error(conn: sqlite3.Connection) -> None:
    event_id = stored(conn, kind="checkin", category=None, repeat="daily")
    with pytest.raises(MarkError, match="повторяющееся"):
        apply(conn, resize(event_id, "2026-10-10T13:00:00"))


def test_create_writes_draft_to_calendar_and_marks_written(conn: sqlite3.Connection) -> None:
    writer = FakeCalendarWriter()
    result = apply(conn, create(), writer)
    assert result["status"] == "written"
    row = get_event(conn, result["id"])
    assert row is not None
    assert (row["status"], row["calendar_uid"], row["title"]) == (
        "written",
        "fake-uid-1",
        "Новый пункт",
    )
    assert len(writer.written) == 1


def test_create_calendar_error_leaves_draft_with_text(conn: sqlite3.Connection) -> None:
    result = apply(conn, create(), FakeCalendarWriter(CalendarError("календарь сломан")))
    assert result["status"] == "draft"
    assert "календарь сломан" in result["error"]
    row = get_event(conn, result["id"])
    assert row is not None
    assert (row["status"], row["calendar_uid"]) == ("draft", None)


def test_create_without_calendar_config_leaves_draft_with_text(
    conn: sqlite3.Connection,
) -> None:
    from ai_coach.web.plan import apply_event

    def factory() -> Any:
        raise WorkloadConfigError("Календарь коуча не задан.")

    result = apply_event(conn, create(), NOW, factory)
    assert result["status"] == "draft"
    assert "Календарь коуча не задан" in result["error"]
    row = get_event(conn, result["id"])
    assert row is not None
    assert row["status"] == "draft"


@pytest.mark.parametrize("kind", ["training", "practice"])
def test_create_kind_outside_pult_list_is_mark_error(conn: sqlite3.Connection, kind: str) -> None:
    with pytest.raises(MarkError, match="kind: .*чек-ин"):
        apply(conn, create(kind=kind, category=None), FakeCalendarWriter())
    assert list_events(conn, "2026-01-01", "2027-12-31") == []


@pytest.mark.parametrize("title", [5, ["a"]])
def test_create_non_string_title_is_mark_error(conn: sqlite3.Connection, title: Any) -> None:
    with pytest.raises(MarkError, match="title: нужна строка."):
        apply(conn, create(title=title), FakeCalendarWriter())
    assert list_events(conn, "2026-01-01", "2027-12-31") == []


def test_default_writer_without_coach_calendar_is_config_error() -> None:
    from ai_coach.web.plan import default_writer

    with pytest.raises(WorkloadConfigError, match="Календарь коуча не задан"):
        default_writer()


def test_default_writer_uses_coach_calendar_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach.web import plan

    config = tmp_path / "coach-calendar.toml"
    config.write_text('[coach]\ncalendar = "Коуч"\n', encoding="utf-8")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))
    names: list[str] = []

    class Spy:
        def __init__(self, name: str) -> None:
            names.append(name)

    monkeypatch.setattr(plan, "CalendarWriter", Spy)
    assert isinstance(plan.default_writer(), Spy)
    assert names == ["Коуч"]


def test_create_invalid_is_mark_error_and_adds_nothing(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError):
        apply(conn, create(title="  "), FakeCalendarWriter())
    assert list_events(conn, "2026-01-01", "2027-12-31") == []


def test_create_end_not_after_start_is_mark_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError):
        apply(conn, create(end_at="2026-10-11T15:00:00"), FakeCalendarWriter())


def test_resize_without_end_at_is_mark_error_and_keeps_row(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    before = get_event(conn, event_id)
    with pytest.raises(MarkError):
        apply(conn, {"action": "resize", "id": event_id, "date": DAY})
    assert get_event(conn, event_id) == before


def test_huge_id_is_mark_error_with_text(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError, match="id: нужен номер события.") as raised:
        apply(conn, move(2**70, "2026-10-11T15:30:00"))
    assert type(raised.value) is MarkError


@pytest.mark.parametrize("bad_id", ["1", "7", True])
def test_non_integer_id_is_plain_mark_error_not_no_event(
    conn: sqlite3.Connection, bad_id: Any
) -> None:
    event_id = stored(conn)
    before = get_event(conn, event_id)
    with pytest.raises(MarkError) as raised:
        apply(conn, move(bad_id, "2026-10-11T15:30:00"))
    assert type(raised.value) is MarkError
    assert event_id == 1
    assert get_event(conn, 1) == before


def test_default_writer_config_error_has_exact_text() -> None:
    from ai_coach.web.plan import default_writer

    with pytest.raises(WorkloadConfigError) as raised:
        default_writer()
    assert str(raised.value) == "Календарь коуча не задан: добавь [coach] calendar в workload.toml."


def test_id_equal_to_sqlite_limit_is_no_event_not_mark_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(NoEvent):
        apply(conn, move(2**63 - 1, "2026-10-11T15:30:00"))


def test_huge_id_mark_error_text_is_exact(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError) as raised:
        apply(conn, move(2**70, "2026-10-11T15:30:00"))
    assert str(raised.value) == "id: нужен номер события."


def test_move_ignores_end_at_from_payload(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    before = get_event(conn, event_id)
    assert before is not None
    length = datetime.fromisoformat(before["end_at"]) - datetime.fromisoformat(before["start_at"])
    payload = move(event_id, "2026-10-11T15:30:00") | {"end_at": "2026-10-11T23:00:00"}
    apply(conn, payload)
    row = get_event(conn, event_id)
    assert row is not None
    assert datetime.fromisoformat(row["end_at"]) == datetime(2026, 10, 11, 15, 30) + length


def test_move_without_start_at_reports_empty_value(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    with pytest.raises(MarkError) as raised:
        apply(conn, {"action": "move", "id": event_id, "date": DAY})
    assert str(raised.value) == "start_at: нужно YYYY-MM-DDTHH:MM, получено: ''"


def test_resize_without_end_at_mark_error_text_is_exact(conn: sqlite3.Connection) -> None:
    event_id = stored(conn)
    with pytest.raises(MarkError) as raised:
        apply(conn, {"action": "resize", "id": event_id, "date": DAY})
    assert str(raised.value) == "end_at: нужно время конца."


def test_create_bad_kind_mark_error_text_is_exact(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError) as raised:
        apply(conn, create(kind="training", category=None), FakeCalendarWriter())
    assert str(raised.value) == "kind: задача, фокус, отдых, еда или чек-ин."


def test_create_checkin_with_survey_writes_event_with_survey(conn: sqlite3.Connection) -> None:
    writer = FakeCalendarWriter()
    result = apply(conn, create(kind="checkin", survey="feel", category=None), writer)
    assert result["status"] == "written"
    row = get_event(conn, result["id"])
    assert row is not None
    assert (row["kind"], row["survey"]) == ("checkin", "feel")
    assert len(writer.written) == 1


def test_create_checkin_without_survey_is_mark_error_and_adds_nothing(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(MarkError, match="survey"):
        apply(conn, create(kind="checkin", category=None), FakeCalendarWriter())
    assert list_events(conn, "2026-01-01", "2027-12-31") == []


def test_create_checkin_with_unknown_survey_is_mark_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError, match="survey"):
        apply(conn, create(kind="checkin", survey="мусор", category=None), FakeCalendarWriter())
    assert list_events(conn, "2026-01-01", "2027-12-31") == []


def test_create_task_with_survey_is_mark_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError, match="survey только у checkin"):
        apply(conn, create(survey="feel"), FakeCalendarWriter())
    assert list_events(conn, "2026-01-01", "2027-12-31") == []


def test_create_bad_title_mark_error_text_is_exact(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError) as raised:
        apply(conn, create(title=5), FakeCalendarWriter())
    assert str(raised.value) == "title: нужна строка."


def test_create_checks_date_window_against_now_not_real_today(conn: sqlite3.Connection) -> None:
    payload = create(start_at="2026-09-20T15:00:00", end_at="2026-09-20T15:30:00")
    apply(conn, payload, FakeCalendarWriter())
    assert len(list_events(conn, "2026-01-01", "2027-12-31")) == 1


def test_unknown_action_mark_error_text_is_exact(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError) as raised:
        apply(conn, {"action": "delete", "id": 1, "date": DAY})
    assert str(raised.value) == "action: move, resize или create."
