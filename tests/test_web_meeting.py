"""Чужие события в пульте: meeting_view и apply_meeting (шаг П5, партия 3)."""

import sqlite3
from datetime import date, datetime
from typing import Any

import pytest
from workload_fakes import FakeForeignEditor, coach_event, stored_event

from ai_coach.store.agenda import add_event
from ai_coach.store.workload import replace_calendar_window
from ai_coach.web.errors import MarkError, NoEvent
from ai_coach.workload import CalendarError

NOW = datetime(2026, 11, 9, 12, 0, 0)
DAY = date(2026, 11, 9)
START, END = "2026-11-09T15:00:00", "2026-11-09T16:00:00"


def put(conn: sqlite3.Connection, uid: str = "m1", **fields: Any) -> int:
    base: dict[str, Any] = {
        "my_status": None,
        "title": "Чужая встреча",
        "start_at": START,
        "end_at": END,
    }
    event = stored_event(uid=uid, **(base | fields))
    replace_calendar_window(conn, "2026-11-09", "2026-11-09", [event])
    conn.commit()
    return conn.execute("SELECT id FROM calendar_events WHERE uid = ?", (uid,)).fetchone()[0]


def row_of(conn: sqlite3.Connection, event_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,)).fetchone()
    return None if row is None else dict(row)


def view(conn: sqlite3.Connection, event_id: Any, editor: Any) -> dict[str, Any]:
    from ai_coach.web.meeting import meeting_view

    return meeting_view(conn, DAY, NOW, {"id": [str(event_id)]}, lambda: editor)


def apply(conn: sqlite3.Connection, payload: dict[str, Any], editor: Any) -> dict[str, Any]:
    from ai_coach.web.meeting import apply_meeting

    return apply_meeting(conn, payload, NOW, lambda: editor)


def update(event_id: int, **fields: Any) -> dict[str, Any]:
    return {"action": "update", "id": event_id} | fields


def test_view_gives_card_with_live_note_and_right_to_write(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    result = view(conn, event_id, FakeForeignEditor(note="из календаря"))
    assert result == {
        "id": event_id,
        "calendar": "Work",
        "title": "Чужая встреча",
        "note": "из календаря",
        "start_at": START,
        "end_at": END,
        "all_day": 0,
        "recurring": False,
        "editable": True,
        "reason": None,
    }


def test_view_recurring_comes_from_raw_json(conn: sqlite3.Connection) -> None:
    event_id = put(conn, raw_json={"recurring": True})
    assert view(conn, event_id, FakeForeignEditor())["recurring"] is True


def test_view_readonly_calendar_is_not_editable(conn: sqlite3.Connection) -> None:
    result = view(conn, put(conn), FakeForeignEditor(readonly=True))
    assert (result["editable"], result["reason"]) == (False, "календарь только для чтения")


def test_view_editor_error_is_text_with_open_window(conn: sqlite3.Connection) -> None:
    result = view(conn, put(conn), FakeForeignEditor(error=CalendarError("EventKit недоступен")))
    assert (result["note"], result["editable"], result["reason"]) == (
        None,
        False,
        "EventKit недоступен",
    )


def test_view_attendee_meeting_is_view_only(conn: sqlite3.Connection) -> None:
    result = view(conn, put(conn, my_status="accepted"), FakeForeignEditor())
    assert (result["editable"], result["reason"]) == (False, "встреча с участниками")


def test_view_coach_event_is_not_editable(conn: sqlite3.Connection) -> None:
    event_id = put(conn, uid="m1")
    add_event(conn, coach_event(status="written", calendar_uid="m1"))
    conn.commit()
    result = view(conn, event_id, FakeForeignEditor())
    assert (result["editable"], result["reason"]) == (False, "событие тренера")


def test_view_bad_id_is_mark_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError):
        view(conn, "abc", FakeForeignEditor())


def test_view_unknown_id_is_no_event(conn: sqlite3.Connection) -> None:
    with pytest.raises(NoEvent, match="обнови синк"):
        view(conn, 999, FakeForeignEditor())


def test_update_goes_to_calendar_then_row(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    editor = FakeForeignEditor()
    values = {
        "title": "Новое имя",
        "note": "описание",
        "start_at": "2026-11-10T09:00:00",
        "end_at": "2026-11-10T09:45:00",
    }
    result = apply(conn, update(event_id, **values), editor)
    assert result == {"start_at": "2026-11-10T09:00:00", "end_at": "2026-11-10T09:45:00"}
    assert editor.updated == [("m1", START, values)]
    row = row_of(conn, event_id)
    assert row is not None
    assert (row["title"], row["start_at"], row["end_at"], row["date"]) == (
        "Новое имя",
        "2026-11-10T09:00:00",
        "2026-11-10T09:45:00",
        "2026-11-10",
    )


def test_update_title_only_keeps_times(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    apply(conn, update(event_id, title="Только имя"), FakeForeignEditor())
    row = row_of(conn, event_id)
    assert row is not None
    assert (row["title"], row["start_at"], row["end_at"]) == ("Только имя", START, END)


def test_update_time_only_works_for_event_without_title(conn: sqlite3.Connection) -> None:
    event_id = put(conn, title=None)
    apply(conn, update(event_id, start_at="2026-11-09T15:30:00"), FakeForeignEditor())
    row = row_of(conn, event_id)
    assert row is not None
    assert (row["title"], row["start_at"]) == (None, "2026-11-09T15:30:00")


def test_update_title_only_works_for_multi_day_event(conn: sqlite3.Connection) -> None:
    event_id = put(conn, all_day=True, start_at="2026-11-09T00:00:00", end_at="2026-11-12T00:00:00")
    apply(conn, update(event_id, title="Отпуск"), FakeForeignEditor())
    row = row_of(conn, event_id)
    assert row is not None
    assert (row["title"], row["end_at"]) == ("Отпуск", "2026-11-12T00:00:00")


def test_update_normalizes_time_to_snapshot_format(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    editor = FakeForeignEditor()
    apply(conn, update(event_id, start_at="2026-11-09T15:30", end_at="2026-11-09T16:30"), editor)
    assert editor.updated[0][2] == {
        "start_at": "2026-11-09T15:30:00",
        "end_at": "2026-11-09T16:30:00",
    }
    row = row_of(conn, event_id)
    assert row is not None
    assert (row["start_at"], row["end_at"]) == ("2026-11-09T15:30:00", "2026-11-09T16:30:00")


def test_update_editor_error_keeps_row_and_gives_text(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    before = row_of(conn, event_id)
    with pytest.raises(MarkError, match="календарь сломан"):
        apply(
            conn,
            update(event_id, title="Новое"),
            FakeForeignEditor(CalendarError("календарь сломан")),
        )
    assert row_of(conn, event_id) == before


@pytest.mark.parametrize(
    ("start_at", "end_at"),
    [
        ("2026-11-09T15:00:00", "2026-11-09T15:00:00"),
        ("2026-11-09T15:00:00", "2026-11-09T14:00:00"),
        ("2026-11-09T15:00:00", "2026-11-10T15:00:01"),
    ],
)
def test_update_bad_span_is_mark_error(
    conn: sqlite3.Connection, start_at: str, end_at: str
) -> None:
    event_id = put(conn)
    editor = FakeForeignEditor()
    before = row_of(conn, event_id)
    with pytest.raises(MarkError):
        apply(conn, update(event_id, start_at=start_at, end_at=end_at), editor)
    assert (editor.updated, row_of(conn, event_id)) == ([], before)


def test_remove_deletes_occurrence_in_calendar_and_row(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    editor = FakeForeignEditor()
    assert apply(conn, {"action": "remove", "id": event_id}, editor) == {}
    assert editor.removed == [("m1", START)]
    assert row_of(conn, event_id) is None


def test_remove_editor_error_keeps_row(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    with pytest.raises(MarkError, match="снять нельзя"):
        apply(
            conn,
            {"action": "remove", "id": event_id},
            FakeForeignEditor(CalendarError("снять нельзя")),
        )
    assert row_of(conn, event_id) is not None


@pytest.mark.parametrize("action", ["update", "remove"])
def test_coach_row_is_refused_and_untouched(conn: sqlite3.Connection, action: str) -> None:
    event_id = put(conn, uid="m1")
    add_event(conn, coach_event(status="written", calendar_uid="m1"))
    conn.commit()
    editor = FakeForeignEditor()
    with pytest.raises(MarkError, match="событие тренера"):
        apply(conn, {"action": action, "id": event_id, "title": "Х"}, editor)
    assert (editor.updated, editor.removed) == ([], [])
    assert row_of(conn, event_id) is not None


@pytest.mark.parametrize("action", ["update", "remove"])
def test_attendee_meeting_is_refused_and_untouched(conn: sqlite3.Connection, action: str) -> None:
    event_id = put(conn, my_status="accepted")
    editor = FakeForeignEditor()
    with pytest.raises(MarkError, match="участник"):
        apply(conn, {"action": action, "id": event_id, "title": "Х"}, editor)
    assert (editor.updated, editor.removed) == ([], [])
    assert row_of(conn, event_id) is not None


@pytest.mark.parametrize("event_id", [2**63, True, "1", None])
def test_bad_id_is_mark_error(conn: sqlite3.Connection, event_id: Any) -> None:
    with pytest.raises(MarkError):
        apply(conn, {"action": "remove", "id": event_id}, FakeForeignEditor())


def test_unknown_id_is_no_event(conn: sqlite3.Connection) -> None:
    with pytest.raises(NoEvent, match="обнови синк"):
        apply(conn, {"action": "remove", "id": 999}, FakeForeignEditor())


def test_unknown_action_is_mark_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError):
        apply(conn, {"action": "create", "id": put(conn)}, FakeForeignEditor())


def message_of(call: Any) -> str:
    with pytest.raises((MarkError, NoEvent)) as raised:
        call()
    return str(raised.value)


def test_unknown_action_message(conn: sqlite3.Connection) -> None:
    text = message_of(
        lambda: apply(conn, {"action": "create", "id": put(conn)}, FakeForeignEditor())
    )
    assert text == "action: нужно одно из update, remove."


def test_bad_id_messages(conn: sqlite3.Connection) -> None:
    assert message_of(lambda: view(conn, "abc", FakeForeignEditor())) == "id: нужен номер встречи."
    assert (
        message_of(lambda: apply(conn, {"action": "remove", "id": "1"}, FakeForeignEditor()))
        == "id: нужен номер встречи."
    )


def test_unknown_id_message(conn: sqlite3.Connection) -> None:
    text = message_of(lambda: apply(conn, {"action": "remove", "id": 999}, FakeForeignEditor()))
    assert text == "Встречи нет — обнови синк."


def test_id_equal_to_max_id_is_looked_up_not_rejected(conn: sqlite3.Connection) -> None:
    from ai_coach.web.plan import MAX_ID

    with pytest.raises(NoEvent):
        apply(conn, {"action": "remove", "id": MAX_ID}, FakeForeignEditor())


def test_coach_row_message(conn: sqlite3.Connection) -> None:
    event_id = put(conn, uid="m1")
    add_event(conn, coach_event(status="written", calendar_uid="m1"))
    conn.commit()
    text = message_of(lambda: apply(conn, update(event_id, title="Х"), FakeForeignEditor()))
    assert text == "событие тренера — двигай его блок."


def test_attendee_message(conn: sqlite3.Connection) -> None:
    event_id = put(conn, my_status="accepted")
    text = message_of(lambda: apply(conn, update(event_id, title="Х"), FakeForeignEditor()))
    assert text == "Встреча с участниками — только просмотр."


class SpyEditor(FakeForeignEditor):
    def __init__(self) -> None:
        super().__init__()
        self.asked: list[tuple[str, str, str]] = []

    def note(self, uid: str, start_at: str) -> str:
        self.asked.append(("note", uid, start_at))
        return super().note(uid, start_at)

    def writable(self, uid: str, start_at: str) -> bool:
        self.asked.append(("writable", uid, start_at))
        return super().writable(uid, start_at)


def test_view_asks_editor_about_this_uid_and_start(conn: sqlite3.Connection) -> None:
    editor = SpyEditor()
    view(conn, put(conn), editor)
    assert editor.asked == [("note", "m1", START), ("writable", "m1", START)]


def test_view_note_is_none_when_editor_fails_on_writable(conn: sqlite3.Connection) -> None:
    class Failing(FakeForeignEditor):
        def writable(self, uid: str, start_at: str) -> bool:
            raise CalendarError("пропало")

    result = view(conn, put(conn), Failing())
    assert (result["note"], result["editable"], result["reason"]) == (None, False, "пропало")


def test_update_empty_payload_message(conn: sqlite3.Connection) -> None:
    text = message_of(lambda: apply(conn, update(put(conn)), FakeForeignEditor()))
    assert text == "Нечего менять: нужны title, note, start_at или end_at."


def test_update_non_string_message(conn: sqlite3.Connection) -> None:
    text = message_of(lambda: apply(conn, update(put(conn), title=5), FakeForeignEditor()))
    assert text == "title, note, start_at, end_at: нужны строки."


def test_update_empty_title_is_refused_with_message(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    editor = FakeForeignEditor()
    text = message_of(lambda: apply(conn, update(event_id, title=""), editor))
    assert text == "title: нужно название."
    assert editor.updated == []


def test_update_empty_note_is_allowed(conn: sqlite3.Connection) -> None:
    editor = FakeForeignEditor()
    apply(conn, update(put(conn), note=""), editor)
    assert editor.updated[0][2] == {"note": ""}


@pytest.mark.parametrize("key", ["start_at", "end_at"])
def test_update_bad_time_format_message(conn: sqlite3.Connection, key: str) -> None:
    editor = FakeForeignEditor()
    text = message_of(lambda: apply(conn, update(put(conn), **{key: "не время"}), editor))
    assert text == "start_at, end_at: нужно время YYYY-MM-DDTHH:MM:SS."
    assert editor.updated == []


def test_update_start_only_is_checked_against_stored_end(conn: sqlite3.Connection) -> None:
    editor = FakeForeignEditor()
    text = message_of(
        lambda: apply(conn, update(put(conn), start_at="2026-11-09T17:00:00"), editor)
    )
    assert text == "Конец должен быть позже начала, не больше суток."
    assert editor.updated == []


def test_update_end_only_is_checked_against_stored_start(conn: sqlite3.Connection) -> None:
    editor = FakeForeignEditor()
    text = message_of(lambda: apply(conn, update(put(conn), end_at="2026-11-09T14:00:00"), editor))
    assert text == "Конец должен быть позже начала, не больше суток."
    assert editor.updated == []


def test_update_exactly_24_hours_is_allowed(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    result = apply(conn, update(event_id, end_at="2026-11-10T15:00:00"), FakeForeignEditor())
    assert result["end_at"] == "2026-11-10T15:00:00"


def test_update_end_only_answers_with_stored_start(conn: sqlite3.Connection) -> None:
    result = apply(conn, update(put(conn), end_at="2026-11-09T17:00:00"), FakeForeignEditor())
    assert result == {"start_at": START, "end_at": "2026-11-09T17:00:00"}


def test_update_start_only_answers_with_stored_end(conn: sqlite3.Connection) -> None:
    result = apply(conn, update(put(conn), start_at="2026-11-09T15:30:00"), FakeForeignEditor())
    assert result == {"start_at": "2026-11-09T15:30:00", "end_at": END}


def test_update_moves_row_to_the_new_date(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    apply(
        conn,
        update(event_id, start_at="2026-11-10T09:00:00", end_at="2026-11-10T10:00:00"),
        FakeForeignEditor(),
    )
    row = row_of(conn, event_id)
    assert row is not None
    assert row["date"] == "2026-11-10"


def test_update_end_only_keeps_row_date(conn: sqlite3.Connection) -> None:
    event_id = put(conn)
    apply(conn, update(event_id, end_at="2026-11-09T17:00:00"), FakeForeignEditor())
    row = row_of(conn, event_id)
    assert row is not None
    assert row["date"] == "2026-11-09"
