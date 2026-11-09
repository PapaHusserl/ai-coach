import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner
from workload_fakes import coach_event

from ai_coach.cli import main
from ai_coach.load.deviations import main_wellbeing
from ai_coach.store.agenda import add_event, list_done, mark_done, unmark_done, update_event
from ai_coach.store.journal import (
    add_food,
    evening_done,
    list_focus,
    list_food,
    list_food_pending,
    list_slip,
    list_wellbeing,
)
from ai_coach.store.workload import list_counters
from ai_coach.web.errors import MarkError, NoEvent
from ai_coach.web.marks import marks_for_day, save_mark

D = "2026-11-08"


def at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{D}T{hhmm}:00")


def event(
    conn: sqlite3.Connection,
    kind: str = "task",
    start: str = "10:00",
    end: str = "11:30",
    **fields: Any,
) -> int:
    values = coach_event(
        kind=kind, date=D, start_at=f"{D}T{start}:00", end_at=f"{D}T{end}:00", **fields
    )
    event_id = add_event(conn, values)
    conn.commit()
    return event_id


def payload(event_id: int, mark: str, **fields: Any) -> dict[str, Any]:
    return {"event_id": event_id, "date": D, "mark": mark, **fields}


RATING = {"focus": 4, "fatigue": 2, "effort": 3}


def test_rating_goes_to_focus_log_with_event_id_and_now(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    row_id = save_mark(conn, payload(eid, "rating", **RATING, text="ок"), at("10:30"))
    [row] = list_focus(conn, D, D)
    assert row["id"] == row_id
    assert (row["event_id"], row["date"], row["logged_at"]) == (eid, D, f"{D} 10:30:00")
    assert (row["focus"], row["fatigue"], row["effort"], row["text"]) == (4, 2, 3, "ок")


def test_coach_log_focus_shows_rating_from_pult(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eid = event(conn)
    save_mark(conn, payload(eid, "rating", **RATING), at("15:00"))
    conn.commit()
    monkeypatch.setenv("AI_COACH_DB", str(tmp_path / "coach.db"))
    result = CliRunner().invoke(main.app, ["log", "focus", "--date", D])
    assert f"{D} 11:30:00  4/2/3" in result.output


def test_past_item_is_logged_at_its_end(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    save_mark(conn, payload(eid, "rating", **RATING), at("15:00"))
    assert list_focus(conn, D, D)[0]["logged_at"] == f"{D} 11:30:00"


def test_rating_is_append_only(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    save_mark(conn, payload(eid, "rating", **RATING), at("10:30"))
    save_mark(conn, payload(eid, "rating", **RATING), at("10:40"))
    assert len(list_focus(conn, D, D)) == 2


def test_feel_has_no_mood_and_stress(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    save_mark(conn, payload(eid, "feel", score=4, text=" текст "), at("10:30"))
    [row] = list_wellbeing(conn, D, D)
    assert (row["event_id"], row["score"], row["text"]) == (eid, 4, "текст")
    assert (row["mood"], row["stress"]) == (None, None)
    assert not evening_done(conn, D)


def test_slip_for_rest_is_saved(conn: sqlite3.Connection) -> None:
    eid = event(conn, "rest")
    save_mark(conn, payload(eid, "slip", text="бесит"), at("10:30"))
    [row] = list_slip(conn, D, D)
    assert (row["event_id"], row["text"]) == (eid, "бесит")


@pytest.mark.parametrize("text", [None, "", "  "])
def test_slip_with_empty_text_is_rejected(conn: sqlite3.Connection, text: str | None) -> None:
    eid = event(conn)
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "slip", text=text), at("10:30"))


def test_rating_for_rest_is_rejected(conn: sqlite3.Connection) -> None:
    eid = event(conn, "rest")
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "rating", **RATING), at("10:30"))


def test_done_upserts_and_unmarks(conn: sqlite3.Connection) -> None:
    eid = event(conn, "practice")
    assert save_mark(conn, payload(eid, "done", done=1), at("10:30")) is None
    save_mark(conn, payload(eid, "done", done=0), at("10:40"))
    [row] = list_done(conn, D, D)
    assert (row["event_id"], row["done"], row["logged_at"]) == (eid, 0, f"{D} 10:40:00")
    save_mark(conn, payload(eid, "done", done=None), at("10:50"))
    assert list_done(conn, D, D) == []


@pytest.mark.parametrize("done", [2, True, "1"])
def test_done_bad_value_is_rejected(conn: sqlite3.Connection, done: Any) -> None:
    eid = event(conn, "practice")
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "done", done=done), at("10:30"))


def test_done_for_task_is_rejected(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "done", done=1), at("10:30"))


def test_checkin_writes_wellbeing_and_hours(conn: sqlite3.Connection) -> None:
    eid = event(conn, "checkin", "20:00", "20:15")
    fields = {"score": 4, "mood": 3, "stress": 2, "work": 6, "thoughts": 2, "flow": 1}
    save_mark(conn, payload(eid, "checkin", **fields), at("20:05"))
    [row] = list_wellbeing(conn, D, D)
    assert (row["mood"], row["stress"], row["work_thoughts"], row["flow"]) == (3, 2, 2, 1)
    assert row["event_id"] == eid
    [counter] = list_counters(conn, D, D, "work_hours")
    assert (counter["value"], counter["source"]) == (6, "manual")
    assert evening_done(conn, D)


@pytest.mark.parametrize(
    "extra",
    [
        {"thoughts": 6},
        {"work": 25},
        {"work": "6"},
        {"work": True},
        {"flow": 2},
        {"flow": True},
        {"mood": 0},
    ],
)
def test_checkin_bad_values_are_rejected(conn: sqlite3.Connection, extra: dict[str, Any]) -> None:
    eid = event(conn, "checkin", "20:00", "20:15")
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "checkin", score=4, **extra), at("20:05"))
    assert list_wellbeing(conn, D, D) == []


def test_checkin_for_task_is_rejected(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "checkin", score=4), at("10:30"))


@pytest.mark.parametrize("score", [0, 6, None, "4", True])
def test_score_out_of_range_is_rejected(conn: sqlite3.Connection, score: Any) -> None:
    eid = event(conn)
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "feel", score=score), at("10:30"))


@pytest.mark.parametrize("status", ["cancelled", "removed"])
def test_inactive_event_is_not_found(conn: sqlite3.Connection, status: str) -> None:
    eid = event(conn)
    update_event(conn, eid, {"status": status})
    with pytest.raises(NoEvent):
        save_mark(conn, payload(eid, "feel", score=3), at("10:30"))


def test_missing_event_is_not_found(conn: sqlite3.Connection) -> None:
    with pytest.raises(NoEvent):
        save_mark(conn, payload(999, "feel", score=3), at("10:30"))


def test_event_id_must_be_int(conn: sqlite3.Connection) -> None:
    with pytest.raises(NoEvent):
        save_mark(conn, payload("1", "feel", score=3), at("10:30"))  # type: ignore[arg-type]


def test_date_must_be_a_date(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    bad = {**payload(eid, "feel", score=3), "date": "вчера"}
    with pytest.raises(MarkError):
        save_mark(conn, bad, at("10:30"))


def test_repeat_is_marked_only_on_its_day(conn: sqlite3.Connection) -> None:
    eid = event(conn, "checkin", "20:00", "20:15", repeat="weekly")
    off_day = {**payload(eid, "checkin", score=3), "date": "2026-11-10"}
    with pytest.raises(MarkError):
        save_mark(conn, off_day, datetime.fromisoformat("2026-11-10T20:05:00"))
    next_week = {**payload(eid, "checkin", score=3), "date": "2026-11-15"}
    save_mark(conn, next_week, datetime.fromisoformat("2026-11-15T21:00:00"))
    [row] = list_wellbeing(conn, "2026-11-15", "2026-11-15")
    assert row["logged_at"] == "2026-11-15 20:15:00"


def test_future_item_is_rejected(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    with pytest.raises(MarkError, match="не начался"):
        save_mark(conn, payload(eid, "feel", score=3), at("09:59"))


def test_training_done_upserts_and_unmarks(conn: sqlite3.Connection) -> None:
    eid = event(conn, "training", "09:00", "09:40")
    assert save_mark(conn, payload(eid, "done", done=1), at("09:50")) is None
    save_mark(conn, payload(eid, "done", done=0), at("09:55"))
    [row] = list_done(conn, D, D)
    assert (row["event_id"], row["done"]) == (eid, 0)
    save_mark(conn, payload(eid, "done", done=None), at("10:00"))
    assert list_done(conn, D, D) == []


@pytest.mark.parametrize(
    ("mark", "fields"), [("feel", {"score": 4}), ("slip", {"text": "пропустил из-за дождя"})]
)
def test_training_feel_and_slip_are_saved_with_event_id(
    conn: sqlite3.Connection, mark: str, fields: dict[str, Any]
) -> None:
    eid = event(conn, "training", "09:00", "09:40")
    save_mark(conn, payload(eid, mark, **fields), at("09:50"))
    rows = list_wellbeing(conn, D, D) if mark == "feel" else list_slip(conn, D, D)
    assert [r["event_id"] for r in rows] == [eid]


@pytest.mark.parametrize(
    ("mark", "fields"), [("food", {"text": "суп"}), ("rating", RATING), ("checkin", {"score": 3})]
)
def test_training_other_marks_are_rejected(
    conn: sqlite3.Connection, mark: str, fields: dict[str, Any]
) -> None:
    eid = event(conn, "training", "09:00", "09:40")
    with pytest.raises(MarkError) as error:
        save_mark(conn, payload(eid, mark, **fields), at("09:50"))
    assert str(error.value) == "У этого пункта нет такой отметки."


def test_future_training_done_is_rejected(conn: sqlite3.Connection) -> None:
    eid = event(conn, "training", "09:00", "09:40")
    with pytest.raises(MarkError, match="не начался"):
        save_mark(conn, payload(eid, "done", done=1), at("08:59"))


def test_marks_for_day_training_done_has_value_and_time(conn: sqlite3.Connection) -> None:
    eid = event(conn, "training", "09:00", "09:40")
    save_mark(conn, payload(eid, "done", done=1), at("09:50"))
    assert marks_for_day(conn, D)[eid]["done"] == {"done": 1, "logged_at": f"{D} 09:40:00"}


@pytest.mark.parametrize("kind", ["sleep"])
def test_kinds_without_window_are_rejected(conn: sqlite3.Connection, kind: str) -> None:
    eid = event(conn, kind)
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "feel", score=3), at("10:30"))


def test_morning_feel_is_not_main_after_evening_checkin(conn: sqlite3.Connection) -> None:
    feel = event(conn)
    checkin = event(conn, "checkin", "20:00", "20:15")
    save_mark(conn, payload(feel, "feel", score=2), at("10:30"))
    save_mark(conn, payload(checkin, "checkin", score=4, mood=3), at("20:05"))
    assert main_wellbeing(list_wellbeing(conn, D, D))["event_id"] == checkin  # type: ignore[index]


def test_unmark_done_removes_only_its_day_and_reports(conn: sqlite3.Connection) -> None:
    mark_done(conn, 1, D, 1, "x")
    mark_done(conn, 1, "2026-11-09", 1, "x")
    assert unmark_done(conn, 1, D) is True
    assert unmark_done(conn, 1, D) is False
    assert [r["date"] for r in list_done(conn, D, "2026-11-09")] == ["2026-11-09"]


def test_unknown_mark_is_rejected(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "bogus"), at("10:30"))


def test_item_error_prefixes_of_pult_js_match_mark_errors() -> None:
    root = Path(__file__).parent.parent / "src" / "ai_coach" / "web"
    script = (root / "static" / "marks-model.js").read_text(encoding="utf-8")
    block = script.split("const ITEM_ERRORS = [", 1)[1].split("];", 1)[0]
    prefixes = re.findall(r'"([^"]+)"', block)
    source = (root / "marks.py").read_text(encoding="utf-8")
    texts = re.findall(r'MarkError\(\s*f?"([^"]*)"', source)
    assert prefixes
    for prefix in prefixes:
        assert any(text.startswith(prefix) for text in texts), prefix


REFUSALS = [
    ("task", {"mark": "feel", "score": 9}, "score: от 1 до 5."),
    ("task", {"mark": "rating", "focus": 9, "fatigue": 2, "effort": 3}, "focus: от 1 до 5."),
    ("checkin", {"mark": "checkin"}, "score: от 1 до 5."),
    ("checkin", {"mark": "checkin", "score": 4, "mood": 0}, "mood: от 1 до 5."),
    (
        "checkin",
        {"mark": "checkin", "score": 4, "work": 25},
        "Часы (work) должны быть числом от 0 до 24.",
    ),
    ("checkin", {"mark": "checkin", "score": 4, "flow": 2}, "flow: 0 или 1."),
    ("practice", {"mark": "done", "done": 2}, "done: 1, 0 или null."),
    ("sleep", {"mark": "feel", "score": 3}, "У этого пункта пока нет окна отметок."),
    ("meal", {"mark": "food"}, "Текст не может быть пустым."),
    ("meal", {"mark": "done", "done": 1}, "У этого пункта нет такой отметки."),
    ("task", {"mark": "food", "text": "суп"}, "У этого пункта нет такой отметки."),
    ("task", {"mark": "done", "done": 1}, "У этого пункта нет такой отметки."),
    ("task", {"mark": "feel", "score": 3, "date": "вчера"}, "date: нужна дата YYYY-MM-DD."),
]


@pytest.mark.parametrize(("kind", "fields", "message"), REFUSALS)
def test_refusal_text_is_exact(
    conn: sqlite3.Connection, kind: str, fields: dict[str, Any], message: str
) -> None:
    eid = event(conn, kind)
    with pytest.raises(MarkError) as error:
        save_mark(conn, {"event_id": eid, "date": D, **fields}, at("10:30"))
    assert str(error.value) == message


def test_missing_event_text_is_exact(conn: sqlite3.Connection) -> None:
    with pytest.raises(NoEvent) as error:
        save_mark(conn, payload(999, "feel", score=3), at("10:30"))
    assert str(error.value) == "Пункта нет."


def test_off_day_text_is_exact(conn: sqlite3.Connection) -> None:
    eid = event(conn, "checkin", "20:00", "20:15", repeat="weekly")
    off_day = {**payload(eid, "checkin", score=3), "date": "2026-11-10"}
    with pytest.raises(MarkError) as error:
        save_mark(conn, off_day, datetime.fromisoformat("2026-11-10T20:05:00"))
    assert str(error.value) == "Пункта в этот день нет."


def test_not_started_text_is_exact(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    with pytest.raises(MarkError) as error:
        save_mark(conn, payload(eid, "feel", score=3), at("09:59"))
    assert str(error.value) == "Пункт ещё не начался."


def test_string_event_id_is_not_found_even_if_such_event_exists(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    with pytest.raises(NoEvent):
        save_mark(conn, payload(str(eid), "feel", score=3), at("10:30"))  # type: ignore[arg-type]


def test_item_can_be_marked_at_its_start_moment(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    save_mark(conn, payload(eid, "feel", score=3), at("10:00"))
    assert list_wellbeing(conn, D, D)[0]["logged_at"] == f"{D} 10:00:00"


def test_logged_at_drops_fractions_of_second(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    save_mark(conn, payload(eid, "feel", score=3), at("10:30").replace(microsecond=500000))
    assert list_wellbeing(conn, D, D)[0]["logged_at"] == f"{D} 10:30:00"


def test_checkin_flow_zero_is_saved(conn: sqlite3.Connection) -> None:
    eid = event(conn, "checkin", "20:00", "20:15")
    save_mark(conn, payload(eid, "checkin", score=4, flow=0), at("20:05"))
    assert list_wellbeing(conn, D, D)[0]["flow"] == 0


def test_checkin_hours_accept_zero_and_limit(conn: sqlite3.Connection) -> None:
    eid = event(conn, "checkin", "20:00", "20:15")
    save_mark(conn, payload(eid, "checkin", score=4, work=0, hobby=24), at("20:05"))
    [work] = list_counters(conn, D, D, "work_hours")
    [hobby] = list_counters(conn, D, D, "hobby_hours")
    assert (work["value"], hobby["value"]) == (0, 24)


def test_second_checkin_with_hours_same_day_replaces_counter(conn: sqlite3.Connection) -> None:
    first = event(conn, "checkin", "12:00", "12:15")
    second = event(conn, "checkin", "20:00", "20:15")
    save_mark(conn, payload(first, "checkin", score=4, work=6), at("12:05"))
    save_mark(conn, payload(second, "checkin", score=4, work=7), at("20:05"))
    [counter] = list_counters(conn, D, D, "work_hours")
    assert (counter["value"], counter["source"], counter["synced_at"]) == (
        7,
        "manual",
        f"{D} 20:05:00",
    )


def test_second_checkin_with_same_hours_keeps_counter_untouched(conn: sqlite3.Connection) -> None:
    first = event(conn, "checkin", "12:00", "12:15")
    second = event(conn, "checkin", "20:00", "20:15")
    save_mark(conn, payload(first, "checkin", score=4, work=6), at("12:05"))
    save_mark(conn, payload(second, "checkin", score=4, work=6), at("20:05"))
    [counter] = list_counters(conn, D, D, "work_hours")
    assert (counter["value"], counter["synced_at"]) == (6, f"{D} 12:05:00")


def test_feel_ignores_checkin_only_fields(conn: sqlite3.Connection) -> None:
    eid = event(conn)
    save_mark(conn, payload(eid, "feel", score=4, mood=3, stress=2, work=5, flow=1), at("10:30"))
    [row] = list_wellbeing(conn, D, D)
    assert (row["mood"], row["stress"], row["flow"]) == (None, None, None)
    assert list_counters(conn, D, D, "work_hours") == []


def test_marks_for_day_done_has_value_and_time(conn: sqlite3.Connection) -> None:
    eid = event(conn, "practice")
    save_mark(conn, payload(eid, "done", done=1), at("10:30"))
    assert marks_for_day(conn, D)[eid]["done"] == {"done": 1, "logged_at": f"{D} 10:30:00"}


def test_food_goes_to_food_log_with_event_id_and_now(conn: sqlite3.Connection) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    row_id = save_mark(conn, payload(eid, "food", text=" омлет "), at("08:30"))
    [row] = list_food(conn, D, D)
    assert row["id"] == row_id
    assert (row["event_id"], row["logged_at"], row["text"]) == (eid, f"{D} 08:30:00", "омлет")
    assert row["kcal"] is None


def test_past_meal_is_logged_at_its_end(conn: sqlite3.Connection) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    save_mark(conn, payload(eid, "food", text="омлет"), at("15:00"))
    assert list_food(conn, D, D)[0]["logged_at"] == f"{D} 09:00:00"


def test_coach_log_food_shows_entry_from_pult(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    save_mark(conn, payload(eid, "food", text="омлет"), at("08:30"))
    conn.commit()
    monkeypatch.setenv("AI_COACH_DB", str(tmp_path / "coach.db"))
    result = CliRunner().invoke(main.app, ["log", "food", "--date", D])
    assert f"{D} 08:30:00  омлет  [КБЖУ не посчитано]" in result.output


def test_food_entry_from_pult_waits_in_pending(conn: sqlite3.Connection) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    save_mark(conn, payload(eid, "food", text="омлет"), at("08:30"))
    assert [r["text"] for r in list_food_pending(conn)] == ["омлет"]


@pytest.mark.parametrize("text", [None, "", "  "])
def test_food_with_empty_text_is_rejected(conn: sqlite3.Connection, text: str | None) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "food", text=text), at("08:30"))
    assert list_food(conn, D, D) == []


def test_food_is_append_only(conn: sqlite3.Connection) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    save_mark(conn, payload(eid, "food", text="омлет"), at("08:30"))
    save_mark(conn, payload(eid, "food", text="кофе"), at("08:40"))
    assert [r["text"] for r in list_food(conn, D, D)] == ["омлет", "кофе"]


@pytest.mark.parametrize("kind", ["practice", "rest", "focus", "checkin"])
def test_food_for_other_kinds_is_rejected(conn: sqlite3.Connection, kind: str) -> None:
    eid = event(conn, kind)
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "food", text="суп"), at("10:30"))
    assert list_food(conn, D, D) == []


def test_future_meal_food_is_rejected(conn: sqlite3.Connection) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    with pytest.raises(MarkError, match="не начался"):
        save_mark(conn, payload(eid, "food", text="омлет"), at("07:59"))


@pytest.mark.parametrize(
    ("mark", "fields"), [("feel", {"score": 4}), ("slip", {"text": "объелся"})]
)
def test_feel_and_slip_for_meal_are_saved_with_event_id(
    conn: sqlite3.Connection, mark: str, fields: dict[str, Any]
) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    save_mark(conn, payload(eid, mark, **fields), at("08:30"))
    rows = list_wellbeing(conn, D, D) if mark == "feel" else list_slip(conn, D, D)
    assert [r["event_id"] for r in rows] == [eid]


@pytest.mark.parametrize(
    ("mark", "fields"), [("food", {"text": "суп"}), ("feel", {"score": 4}), ("slip", {"text": "х"})]
)
def test_cooking_has_no_window_and_writes_nothing(
    conn: sqlite3.Connection, mark: str, fields: dict[str, Any]
) -> None:
    eid = event(conn, "meal", "08:00", "09:00", title="Готовка")
    with pytest.raises(MarkError) as error:
        save_mark(conn, payload(eid, mark, **fields), at("08:30"))
    assert str(error.value) == "У этого пункта пока нет окна отметок."
    assert list_food(conn, D, D) == []
    assert list_wellbeing(conn, D, D) == []
    assert list_slip(conn, D, D) == []


def test_meal_done_is_rejected(conn: sqlite3.Connection) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "done", done=1), at("08:30"))


def test_marks_for_day_has_food_of_own_item_and_day(conn: sqlite3.Connection) -> None:
    mine = event(conn, "meal", "08:00", "09:00")
    other = event(conn, "meal", "13:00", "14:00")
    first = save_mark(conn, payload(mine, "food", text="омлет"), at("08:30"))
    save_mark(conn, payload(mine, "food", text="кофе"), at("08:40"))
    save_mark(conn, payload(other, "food", text="суп"), at("13:30"))
    add_food(conn, {"logged_at": f"{D} 08:50:00", "text": "из CLI"})
    add_food(
        conn,
        {"logged_at": "2026-11-07 08:30:00", "text": "вчера", "event_id": mine},
    )
    found = marks_for_day(conn, D)
    assert first is not None
    assert found[mine]["food"] == [
        {"id": first, "text": "омлет", "kcal": None, "logged_at": f"{D} 08:30:00"},
        {"id": first + 1, "text": "кофе", "kcal": None, "logged_at": f"{D} 08:40:00"},
    ]
    assert [f["text"] for f in found[other]["food"]] == ["суп"]


def test_marks_for_day_food_keeps_kcal_of_ready_entry(conn: sqlite3.Connection) -> None:
    eid = event(conn, "meal", "08:00", "09:00")
    add_food(
        conn,
        {
            "logged_at": f"{D} 08:30:00",
            "text": "вариант",
            "kcal": 450,
            "protein_g": 30,
            "fat_g": 10,
            "carbs_g": 50,
            "event_id": eid,
        },
    )
    assert marks_for_day(conn, D)[eid]["food"][0]["kcal"] == 450


def test_other_marks_have_empty_food(conn: sqlite3.Connection) -> None:
    eid = event(conn, "practice")
    save_mark(conn, payload(eid, "done", done=1), at("10:30"))
    assert marks_for_day(conn, D)[eid]["food"] == []
