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
from ai_coach.store.journal import evening_done, list_focus, list_slip, list_wellbeing
from ai_coach.store.workload import list_counters
from ai_coach.web.marks import MarkError, NoEvent, save_mark

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
    "extra", [{"thoughts": 6}, {"work": 25}, {"flow": 2}, {"flow": True}, {"mood": 0}]
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


@pytest.mark.parametrize("kind", ["meal", "training", "sleep"])
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
    script = (root / "static" / "marks.js").read_text(encoding="utf-8")
    block = script.split("const ITEM_ERRORS = [", 1)[1].split("];", 1)[0]
    prefixes = re.findall(r'"([^"]+)"', block)
    source = (root / "marks.py").read_text(encoding="utf-8")
    texts = re.findall(r'MarkError\(\s*f?"([^"]*)"', source)
    assert prefixes
    for prefix in prefixes:
        assert any(text.startswith(prefix) for text in texts), prefix
