"""Шаг П12, партия 3: форма под пунктом любого вида в пульте — запись, отказы, «красное», день."""

import json
import sqlite3
from datetime import date, datetime
from typing import Any

import pytest
from workload_fakes import coach_event

from ai_coach.store.agenda import add_event
from ai_coach.store.forms import add_form, archive_form, list_form_log
from ai_coach.store.journal import evening_done, list_wellbeing
from ai_coach.web.day import day_view
from ai_coach.web.day_marks import due, empty_marks, marks_for_day
from ai_coach.web.errors import MarkError
from ai_coach.web.marks import save_mark

D = "2026-11-08"
SCORE = {"key": "score", "type": "scale", "label": "Самочувствие"}
TEMPERATURE = {
    "key": "temperature",
    "type": "number",
    "label": "Температура",
    "unit": "°C",
    "min": 34,
    "max": 43,
}
STOOL = {
    "key": "stool",
    "type": "choice",
    "label": "Стул",
    "options": ["норма", "жидкий", "твёрдый"],
    "required": False,
}
RPE = {"key": "rpe", "type": "scale", "label": "Тяжесть", "low": "легко", "high": "тяжело"}
NO_SUCH_MARK = "У этого пункта нет такой отметки."
NO_WINDOW = "У этого пункта пока нет окна отметок."


def at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{D}T{hhmm}:00")


def put_form(conn: sqlite3.Connection, name: str, *fields: dict[str, Any]) -> None:
    values = {
        "name": name,
        "title": "Температура",
        "fields_json": json.dumps(list(fields), ensure_ascii=False),
        "created_at": "2026-11-08 08:00:00",
    }
    add_form(conn, values)
    conn.commit()


def event(
    conn: sqlite3.Connection,
    kind: str = "checkin",
    survey: str | None = "form:temp",
    start: str = "20:00",
    end: str = "20:15",
    **fields: Any,
) -> int:
    category = None if kind == "checkin" else fields.pop("category", "work")
    values = coach_event(
        kind=kind,
        date=D,
        start_at=f"{D}T{start}:00",
        end_at=f"{D}T{end}:00",
        survey=survey,
        category=category,
        **fields,
    )
    event_id = add_event(conn, values)
    conn.commit()
    return event_id


def answer(event_id: int, **fields: Any) -> dict[str, Any]:
    values = {"score": 4, "temperature": 37.2}
    body: dict[str, Any] = {"values": values, "text": "кашель"} | fields
    return {"event_id": event_id, "date": D, "mark": "form", **body}


def form_rows(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM form_log").fetchone()[0]


def test_form_answer_writes_wellbeing_and_form_log(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    save_mark(conn, answer(eid), at("20:05"))
    [well] = list_wellbeing(conn, D, D)
    assert (well["score"], well["text"], well["event_id"]) == (4, "кашель", eid)
    assert (well["mood"], well["stress"]) == (None, None)
    assert well["logged_at"] == f"{D} 20:05:00"
    assert not evening_done(conn, D)
    [row] = list_form_log(conn, D, D)
    assert (row["form"], row["event_id"], row["date"], row["time"]) == ("temp", eid, D, "20:05:00")
    assert json.loads(row["values_json"]) == {"temperature": 37.2}
    assert row["wellbeing_id"] == well["id"]


def test_form_answer_of_past_item_is_logged_at_its_end(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    save_mark(conn, answer(eid), at("23:00"))
    assert list_form_log(conn, D, D)[0]["time"] == "20:15:00"


def test_form_without_score_keeps_text_in_form_log(conn: sqlite3.Connection) -> None:
    put_form(conn, "rpe", RPE)
    eid = event(conn, "training", "form:rpe", "09:00", "09:40")
    save_mark(conn, answer(eid, values={"rpe": 3}, text="тяжело"), at("09:50"))
    assert list_wellbeing(conn, D, D) == []
    [row] = list_form_log(conn, D, D)
    assert (row["text"], row["wellbeing_id"], row["score"]) == ("тяжело", None, None)
    assert json.loads(row["values_json"]) == {"rpe": 3}


def test_optional_field_may_be_skipped(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE, STOOL)
    eid = event(conn)
    save_mark(conn, answer(eid), at("20:05"))
    assert "stool" not in json.loads(list_form_log(conn, D, D)[0]["values_json"])


def test_choice_is_stored_as_option_text(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE, STOOL)
    eid = event(conn)
    values = {"score": 4, "temperature": 37, "stool": "жидкий"}
    save_mark(conn, answer(eid, values=values), at("20:05"))
    stored = json.loads(list_form_log(conn, D, D)[0]["values_json"])
    assert stored == {"temperature": 37, "stool": "жидкий"}


@pytest.mark.parametrize(
    "values",
    [
        {"score": 4, "temperature": "37.2"},
        {"score": 4, "temperature": True},
        {"score": 4, "temperature": 50},
        {"score": 4, "temperature": 30},
        {"score": 4},
        {"temperature": 37.2},
        {"score": 4, "temperature": 37.2, "лишний": 1},
        {"score": 9, "temperature": 37.2},
        {"score": 4, "temperature": 37.2, "stool": "нет такого"},
        {"score": 4, "temperature": 37.2, "stool": 1},
        {"score": 4, "temperature": 37.2, "stool": ["норма", "жидкий"]},
    ],
)
def test_bad_answers_are_rejected_and_write_nothing(
    conn: sqlite3.Connection, values: dict[str, Any]
) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE, STOOL)
    eid = event(conn)
    with pytest.raises(MarkError) as error:
        save_mark(conn, answer(eid, values=values), at("20:05"))
    assert str(error.value) != NO_SUCH_MARK
    assert form_rows(conn) == 0
    assert list_wellbeing(conn, D, D) == []


PULSE_MIN = {"key": "pulse", "type": "number", "label": "Пульс", "min": 40}
PULSE_MAX = {"key": "pulse", "type": "number", "label": "Пульс", "max": 200}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (TEMPERATURE, 50, "Ответ формы не принят: Температура — от 34 до 43."),
        (TEMPERATURE, 30, "Ответ формы не принят: Температура — от 34 до 43."),
        (PULSE_MIN, 30, "Ответ формы не принят: Пульс — не меньше 40."),
        (PULSE_MAX, 250, "Ответ формы не принят: Пульс — не больше 200."),
    ],
)
def test_number_out_of_bounds_gives_readable_refusal(
    conn: sqlite3.Connection, field: dict[str, Any], value: float, message: str
) -> None:
    put_form(conn, "temp", field)
    eid = event(conn)
    with pytest.raises(MarkError) as error:
        save_mark(conn, answer(eid, values={field["key"]: value}), at("20:05"))
    assert str(error.value) == message
    assert form_rows(conn) == 0


@pytest.mark.parametrize("value", [34, 43, 34.0, 43.0])
def test_number_exactly_on_bound_is_accepted(conn: sqlite3.Connection, value: float) -> None:
    put_form(conn, "temp", TEMPERATURE)
    eid = event(conn)
    save_mark(conn, answer(eid, values={"temperature": value}), at("20:05"))
    assert form_rows(conn) == 1


@pytest.mark.parametrize(("field", "value"), [(PULSE_MIN, 40), (PULSE_MAX, 200)])
def test_number_exactly_on_single_bound_is_accepted(
    conn: sqlite3.Connection, field: dict[str, Any], value: float
) -> None:
    put_form(conn, "temp", field)
    eid = event(conn)
    save_mark(conn, answer(eid, values={"pulse": value}), at("20:05"))
    assert form_rows(conn) == 1


@pytest.mark.parametrize(
    ("low", "high", "tail"),
    [(34.0, 43.0, "от 34 до 43."), (34.5, 43.0, "от 34.5 до 43.")],
)
def test_refusal_text_prints_whole_bounds_without_zero(
    conn: sqlite3.Connection, low: float, high: float, tail: str
) -> None:
    field = {**TEMPERATURE, "min": low, "max": high}
    put_form(conn, "temp", field)
    eid = event(conn)
    with pytest.raises(MarkError) as error:
        save_mark(conn, answer(eid, values={"temperature": 50}), at("20:05"))
    assert str(error.value) == f"Ответ формы не принят: Температура — {tail}"


@pytest.mark.parametrize("kind", ["checkin", "task", "sleep"])
def test_day_view_item_with_missing_form_is_due_without_form_key(
    conn: sqlite3.Connection, kind: str
) -> None:
    eid = event(conn, kind, "form:нет", "06:00", "07:00")
    item = _item(conn, eid, "20:30")
    assert item["due"] is True
    assert "form" not in item


@pytest.mark.parametrize("values", [None, "37", [1], 5])
def test_values_must_be_an_object(conn: sqlite3.Connection, values: Any) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    with pytest.raises(MarkError) as error:
        save_mark(conn, answer(eid, values=values), at("20:05"))
    assert str(error.value) != NO_SUCH_MARK
    assert form_rows(conn) == 0


def test_bad_answer_text_starts_with_form_refusal_prefix(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    with pytest.raises(MarkError, match="^Ответ формы не принят"):
        save_mark(conn, answer(eid, values={"score": 4, "temperature": "x"}), at("20:05"))


def test_form_missing_in_base_is_refused_as_no_such_mark(conn: sqlite3.Connection) -> None:
    eid = event(conn, survey="form:нет")
    with pytest.raises(MarkError) as error:
        save_mark(conn, answer(eid), at("20:05"))
    assert str(error.value) == NO_SUCH_MARK


def test_second_answer_adds_second_row(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    save_mark(conn, answer(eid), at("20:05"))
    save_mark(conn, answer(eid, values={"score": 3, "temperature": 38}), at("20:10"))
    assert form_rows(conn) == 2
    assert marks_for_day(conn, D)[eid]["forms"][-1]["values"] == {"temperature": 38}


def test_answer_after_form_is_archived_still_passes(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    archive_form(conn, "temp", "2026-11-08 12:00:00")
    conn.commit()
    save_mark(conn, answer(eid), at("20:05"))
    assert form_rows(conn) == 1
    assert _item(conn, eid, "20:10")["form"]["title"] == "Температура"


@pytest.mark.parametrize("mark", ["feel", "checkin", "rating", "done"])
def test_checkin_with_form_refuses_other_marks(conn: sqlite3.Connection, mark: str) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    with pytest.raises(MarkError) as error:
        save_mark(conn, {"event_id": eid, "date": D, "mark": mark, "score": 4}, at("20:05"))
    assert str(error.value) == NO_SUCH_MARK


def test_form_mark_at_checkin_with_feel_survey_is_refused(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn, survey="feel")
    with pytest.raises(MarkError) as error:
        save_mark(conn, answer(eid), at("20:05"))
    assert str(error.value) == NO_SUCH_MARK


@pytest.mark.parametrize("kind", ["task", "training", "rest", "practice"])
def test_form_mark_without_form_is_refused(conn: sqlite3.Connection, kind: str) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn, kind, None)
    with pytest.raises(MarkError) as error:
        save_mark(conn, answer(eid), at("20:05"))
    assert str(error.value) == NO_SUCH_MARK


@pytest.mark.parametrize(
    ("kind", "mark", "fields"),
    [
        ("task", "form", {}),
        ("task", "rating", {"focus": 4, "fatigue": 2, "effort": 3}),
        ("task", "feel", {"score": 4}),
        ("task", "slip", {"text": "бесит"}),
        ("training", "form", {}),
        ("training", "done", {"done": 1}),
        ("training", "feel", {"score": 4}),
        ("training", "slip", {"text": "бесит"}),
        ("rest", "form", {}),
        ("practice", "form", {}),
    ],
)
def test_item_with_form_accepts_own_marks_and_form(
    conn: sqlite3.Connection, kind: str, mark: str, fields: dict[str, Any]
) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn, kind, "form:temp", "09:00", "09:40")
    body = answer(eid) if mark == "form" else {"event_id": eid, "date": D, "mark": mark, **fields}
    save_mark(conn, body, at("09:50"))


def test_sleep_with_form_takes_only_form(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn, "sleep", "form:temp", "00:00", "07:00")
    save_mark(conn, answer(eid), at("08:00"))
    assert form_rows(conn) == 1
    with pytest.raises(MarkError) as error:
        save_mark(conn, {"event_id": eid, "date": D, "mark": "feel", "score": 3}, at("08:00"))
    assert str(error.value) == NO_SUCH_MARK


def test_sleep_without_form_has_no_window(conn: sqlite3.Connection) -> None:
    eid = event(conn, "sleep", None, "00:00", "07:00")
    with pytest.raises(MarkError) as error:
        save_mark(conn, {"event_id": eid, "date": D, "mark": "form", "values": {}}, at("08:00"))
    assert str(error.value) == NO_WINDOW


def test_cooking_with_form_has_no_window(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn, "meal", "form:temp", "10:00", "11:00", title="Готовка")
    with pytest.raises(MarkError) as error:
        save_mark(conn, answer(eid), at("10:30"))
    assert str(error.value) == NO_WINDOW
    assert form_rows(conn) == 0


def test_form_answer_of_future_item_is_rejected(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    with pytest.raises(MarkError, match="не начался"):
        save_mark(conn, answer(eid), at("19:00"))


def test_empty_marks_have_forms() -> None:
    assert empty_marks()["forms"] == []


def test_marks_for_day_lists_form_answers_of_item(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    other = event(conn, "task", None, "10:00", "11:00")
    save_mark(conn, answer(eid), at("20:05"))
    found = marks_for_day(conn, D)
    [entry] = found[eid]["forms"]
    assert entry["values"] == {"temperature": 37.2}
    assert (entry["score"], entry["text"], entry["logged_at"]) == (4, "кашель", f"{D} 20:05:00")
    assert other not in found


def test_form_score_is_not_duplicated_in_feel(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn, "task", "form:temp", "10:00", "11:00")
    save_mark(conn, answer(eid), at("10:30"))
    marks = marks_for_day(conn, D)[eid]
    assert marks["feel"] == []
    assert len(marks["forms"]) == 1


def test_separate_feel_mark_is_not_in_forms(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn, "task", "form:temp", "10:00", "11:00")
    save_mark(conn, answer(eid), at("10:30"))
    before = marks_for_day(conn, D)[eid]["forms"]
    save_mark(conn, {"event_id": eid, "date": D, "mark": "feel", "score": 2}, at("10:40"))
    marks = marks_for_day(conn, D)[eid]
    assert [r["score"] for r in marks["feel"]] == [2]
    assert marks["forms"] == before


def test_form_log_after_answer_has_event_values_score_and_text(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    save_mark(conn, answer(eid), at("20:05"))
    [row] = list_form_log(conn, D, D)
    assert (row["form"], row["event_id"], row["score"], row["text"]) == ("temp", eid, 4, "кашель")


def marks_with(**fields: Any) -> dict[str, Any]:
    return empty_marks() | {"forms": []} | fields


FORM_ENTRY = {"values": {"temperature": 37.2}, "score": None, "text": None, "logged_at": "x"}
RATED = {"focus": 4, "fatigue": 2, "effort": 3, "text": None, "logged_at": "x"}
DONE = {"done": 1, "logged_at": "x"}


def test_past_checkin_with_form_is_due_without_answer() -> None:
    assert due("checkin", marks_with(), True, True, survey="form:temp") is True


def test_past_checkin_with_form_is_not_due_with_answer() -> None:
    assert due("checkin", marks_with(forms=[FORM_ENTRY]), False, True, survey="form:temp") is False


def test_future_checkin_with_form_is_not_due() -> None:
    assert due("checkin", marks_with(), False, False, survey="form:temp") is False


def test_task_with_form_is_due_with_rating_but_without_answer() -> None:
    marks = marks_with(ratings=[RATED])
    assert due("task", marks, False, True, survey="form:temp") is True


def test_task_with_form_is_due_with_answer_but_without_rating() -> None:
    marks = marks_with(forms=[FORM_ENTRY])
    assert due("task", marks, False, True, survey="form:temp") is True


def test_task_with_form_is_not_due_with_both() -> None:
    marks = marks_with(ratings=[RATED], forms=[FORM_ENTRY])
    assert due("task", marks, False, True, survey="form:temp") is False


def test_training_with_garmin_fact_is_due_without_form_answer() -> None:
    fact = {"kind": "done"}
    assert due("training", marks_with(), False, True, fact=fact, survey="form:rpe") is True


def test_training_with_fact_and_answer_is_not_due() -> None:
    fact = {"kind": "done"}
    marks = marks_with(forms=[FORM_ENTRY])
    assert due("training", marks, False, True, fact=fact, survey="form:rpe") is False


def test_sleep_with_form_is_due_without_answer() -> None:
    assert due("sleep", marks_with(), False, True, survey="form:temp") is True
    assert due("sleep", marks_with(forms=[FORM_ENTRY]), False, True, survey="form:temp") is False


def test_sleep_without_form_is_not_due() -> None:
    assert due("sleep", marks_with(), False, True) is False


def test_cooking_with_form_is_not_due() -> None:
    assert due("meal", marks_with(), False, True, title="Готовка", survey="form:temp") is False


def test_item_without_form_keeps_old_due() -> None:
    assert due("task", marks_with(), False, True) is True
    assert due("task", marks_with(ratings=[RATED]), False, True) is False


def _item(conn: sqlite3.Connection, event_id: int, now: str, day: str = D) -> dict[str, Any]:
    result = day_view(conn, date.fromisoformat(day), datetime.fromisoformat(f"{day}T{now}:00"))
    return next(r for r in result["items"] if r["id"] == event_id)


def test_day_view_checkin_with_form_is_due_then_cleared(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn)
    assert _item(conn, eid, "20:30")["due"] is True
    save_mark(conn, answer(eid), at("20:30"))
    conn.commit()
    item = _item(conn, eid, "20:30")
    assert item["due"] is False
    assert len(item["marks"]["forms"]) == 1


def test_day_view_answer_of_one_day_does_not_clear_another(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE)
    eid = event(conn, repeat="daily")
    save_mark(conn, answer(eid), at("20:30"))
    conn.commit()
    assert _item(conn, eid, "20:30", "2026-11-09")["due"] is True


def test_day_view_item_with_form_has_definition(conn: sqlite3.Connection) -> None:
    put_form(conn, "temp", SCORE, TEMPERATURE, STOOL)
    eid = event(conn)
    form = _item(conn, eid, "20:05")["form"]
    assert (form["name"], form["title"]) == ("temp", "Температура")
    assert [f["key"] for f in form["fields"]] == ["score", "temperature", "stool"]
    assert form["fields"][1]["unit"] == "°C"


@pytest.mark.parametrize(("kind", "survey"), [("checkin", "feel"), ("task", None)])
def test_day_view_item_without_form_has_no_form_key(
    conn: sqlite3.Connection, kind: str, survey: str | None
) -> None:
    eid = event(conn, kind, survey)
    assert "form" not in _item(conn, eid, "20:05")
