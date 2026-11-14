"""Шаг П11, партия 3: WHO-5 из пульта — запись чек-ина с опросником who5 (web/who5.py)."""

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from typer.testing import CliRunner
from workload_fakes import coach_event

from ai_coach.cli import main
from ai_coach.load.who5 import who5_report
from ai_coach.store.agenda import add_event
from ai_coach.store.journal import add_who5, list_who5
from ai_coach.web.errors import MarkError
from ai_coach.web.marks import save_mark

D = "2026-11-08"
ANSWERS = {"q1": 5, "q2": 4, "q3": 3, "q4": 4, "q5": 5}
NO_SUCH_MARK = "У этого пункта нет такой отметки."
STATIC = Path(__file__).parent.parent / "src" / "ai_coach" / "web" / "static"
WHO5_HELP = Path(__file__).parent.parent / ".claude" / "agents" / "coach-help" / "who5.md"


def at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{D}T{hhmm}:00")


def checkin(conn: sqlite3.Connection, survey: str | None = "who5") -> int:
    values = coach_event(
        kind="checkin",
        category=None,
        survey=survey,
        date=D,
        start_at=f"{D}T20:00:00",
        end_at=f"{D}T20:15:00",
    )
    event_id = add_event(conn, values)
    conn.commit()
    return event_id


def payload(event_id: int, mark: str = "who5", /, **fields: Any) -> dict[str, Any]:
    return {"event_id": event_id, "date": D, "mark": mark, **fields}


def test_who5_is_written_with_score_date_and_time(conn: sqlite3.Connection) -> None:
    eid = checkin(conn)
    save_mark(conn, payload(eid, **ANSWERS, text="ок"), at("20:05"))
    [row] = list_who5(conn, D, D)
    assert (row["score"], row["date"], row["logged_at"], row["text"]) == (
        84,
        D,
        f"{D} 20:05:00",
        "ок",
    )
    assert [row[f"q{n}"] for n in range(1, 6)] == [5, 4, 3, 4, 5]


def test_who5_without_text_is_written(conn: sqlite3.Connection) -> None:
    eid = checkin(conn)
    save_mark(conn, payload(eid, **ANSWERS), at("20:05"))
    assert len(list_who5(conn, D, D)) == 1


def test_who5_of_past_item_is_logged_at_its_end(conn: sqlite3.Connection) -> None:
    eid = checkin(conn)
    save_mark(conn, payload(eid, **ANSWERS), at("23:00"))
    assert list_who5(conn, D, D)[0]["logged_at"] == f"{D} 20:15:00"


def test_who5_all_zeros_is_written_with_score_zero(conn: sqlite3.Connection) -> None:
    eid = checkin(conn)
    save_mark(conn, payload(eid, **dict.fromkeys(ANSWERS, 0)), at("20:05"))
    [row] = list_who5(conn, D, D)
    assert row["score"] == 0


BAD_ANSWERS: list[Any] = [6, -1, 2.5, True, "3", None]


@pytest.mark.parametrize("bad", BAD_ANSWERS)
def test_who5_bad_answer_is_rejected_and_nothing_written(
    conn: sqlite3.Connection, bad: Any
) -> None:
    eid = checkin(conn)
    with pytest.raises(MarkError) as error:
        save_mark(conn, payload(eid, **{**ANSWERS, "q3": bad}), at("20:05"))
    assert NO_SUCH_MARK not in str(error.value)
    assert list_who5(conn, D, D) == []


def test_who5_missing_answer_is_rejected(conn: sqlite3.Connection) -> None:
    eid = checkin(conn)
    answers = {k: v for k, v in ANSWERS.items() if k != "q3"}
    with pytest.raises(MarkError) as error:
        save_mark(conn, payload(eid, **answers), at("20:05"))
    assert NO_SUCH_MARK not in str(error.value)
    assert list_who5(conn, D, D) == []


def test_second_who5_of_the_day_is_refused(conn: sqlite3.Connection) -> None:
    eid = checkin(conn)
    save_mark(conn, payload(eid, **ANSWERS), at("20:05"))
    with pytest.raises(MarkError) as error:
        save_mark(conn, payload(eid, **dict.fromkeys(ANSWERS, 1)), at("20:10"))
    assert str(error.value) == "WHO-5 за день уже записан."
    assert [r["score"] for r in list_who5(conn, D, D)] == [84]


def test_who5_is_refused_when_day_has_measure_from_coach(conn: sqlite3.Connection) -> None:
    eid = checkin(conn)
    done = {**ANSWERS, "score": 84, "date": D, "logged_at": f"{D} 09:00:00", "text": None}
    add_who5(conn, done)
    conn.commit()
    with pytest.raises(MarkError) as error:
        save_mark(conn, payload(eid, **dict.fromkeys(ANSWERS, 1)), at("20:05"))
    assert str(error.value) == "WHO-5 за день уже записан."
    assert len(list_who5(conn, D, D)) == 1


def test_who5_mark_is_refused_for_feel_checkin(conn: sqlite3.Connection) -> None:
    eid = checkin(conn, "feel")
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, **ANSWERS), at("20:05"))
    assert list_who5(conn, D, D) == []


def test_checkin_mark_is_refused_for_who5_checkin(conn: sqlite3.Connection) -> None:
    eid = checkin(conn)
    with pytest.raises(MarkError):
        save_mark(conn, payload(eid, "checkin", score=4), at("20:05"))


def test_who5_report_after_pult_equals_report_after_cli(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eid = checkin(conn)
    save_mark(conn, payload(eid, **ANSWERS), at("20:05"))
    conn.commit()
    pult = who5_report(conn, D)
    monkeypatch.setenv("AI_COACH_DB", str(tmp_path / "other.db"))
    freeze(monkeypatch, f"{D} 12:00:00")
    result = CliRunner().invoke(main.app, ["who5", "5", "4", "3", "4", "5"])
    assert result.exit_code == 0, result.output
    other = sqlite3.connect(tmp_path / "other.db")
    other.row_factory = sqlite3.Row
    try:
        cli = who5_report(other, D)
    finally:
        other.close()
    assert (pult["score"], pult["last_date"]) == (cli["score"], cli["last_date"]) == (84, D)


def test_who5_view_is_none_without_measure(conn: sqlite3.Connection) -> None:
    from ai_coach.web.who5 import who5_view

    assert who5_view(conn, D) is None


def test_who5_view_gives_score_and_time(conn: sqlite3.Connection) -> None:
    from ai_coach.web.who5 import who5_view

    eid = checkin(conn)
    save_mark(conn, payload(eid, **ANSWERS), at("20:05"))
    view = who5_view(conn, D)
    assert view is not None
    assert (view["score"], view["logged_at"]) == (84, f"{D} 20:05:00")


def test_who5_view_ignores_other_day(conn: sqlite3.Connection) -> None:
    from ai_coach.web.who5 import who5_view

    eid = checkin(conn)
    save_mark(conn, payload(eid, **ANSWERS), at("20:05"))
    assert who5_view(conn, "2026-11-09") is None


def _js_list(name: str) -> list[str]:
    script = (STATIC / "marks-model.js").read_text(encoding="utf-8")
    block = script.split(f"const {name} = [", 1)[1].split("];", 1)[0]
    return re.findall(r'"((?:[^"\\]|\\.)*)"', block)


def test_who5_items_in_js_are_verbatim_in_help() -> None:
    text = WHO5_HELP.read_text(encoding="utf-8")
    items = _js_list("WHO5_ITEMS")
    assert len(items) == 5
    for number, item in enumerate(items, start=1):
        assert f"  {number}. {item}\n" in text, item


def test_marks_model_names_who5_license() -> None:
    script = (STATIC / "marks-model.js").read_text(encoding="utf-8")
    assert "CC BY-NC-SA 3.0 IGO" in script


def test_who5_labels_in_js_are_verbatim_in_help() -> None:
    text = WHO5_HELP.read_text(encoding="utf-8")
    labels = _js_list("WHO5_LABELS")
    assert len(labels) == 6
    for label in labels:
        assert label in text, label
