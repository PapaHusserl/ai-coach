"""Шаг П8, партия 2: блок «Добавки к приёму» в пульте — intake_view и save_intake."""

import sqlite3
from datetime import datetime
from typing import Any

import pytest

from ai_coach.store.intake import list_intake
from ai_coach.store.meds import add_med
from ai_coach.store.sport_nutrition import add_supplement

D = "2026-11-08"
NOW = datetime.fromisoformat(f"{D}T12:00:00")
STAMP = "2026-11-01 10:00:00"


def new_course(conn: sqlite3.Connection, name: str = "Витамин D", **fields: Any) -> int:
    base = {
        "name": name,
        "kind": "vitamin",
        "dose": 2000.0,
        "unit": "iu",
        "schedule": "daily",
        "time_note": "утром",
        "start_date": "2026-11-01",
        "created_at": STAMP,
        "updated_at": STAMP,
    }
    return add_med(conn, base | fields)


def new_supplement(conn: sqlite3.Connection, name: str = "Креатин", **fields: Any) -> int:
    base = {
        "name": name,
        "dose": 5.0,
        "unit": "g",
        "schedule": "daily",
        "created_at": STAMP,
        "updated_at": STAMP,
    }
    return add_supplement(conn, base | fields)


def payload(kind: str, item_id: int, taken: int, day: str = D) -> dict[str, Any]:
    return {"kind": kind, "item_id": item_id, "date": day, "taken": taken}


def lines(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    from ai_coach.web.intake import intake_view

    return {r["name"]: r for r in intake_view(conn, D)}


# --- intake_view ---


def test_view_has_course_and_supplement_rows(conn: sqlite3.Connection) -> None:
    course = new_course(conn)
    supplement = new_supplement(conn)
    found = lines(conn)
    assert found["Витамин D"] == {
        "kind": "med",
        "id": course,
        "name": "Витамин D",
        "dose": 2000.0,
        "unit": "iu",
        "time_note": "утром",
        "taken": False,
    }
    assert found["Креатин"] == {
        "kind": "supplement",
        "id": supplement,
        "name": "Креатин",
        "dose": 5.0,
        "unit": "g",
        "time_note": None,
        "taken": False,
    }


def test_view_day_without_courses_and_supplements_is_empty(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import intake_view

    assert intake_view(conn, D) == []


def test_view_course_out_of_period_is_not_shown(conn: sqlite3.Connection) -> None:
    new_course(conn, end_date="2026-11-07")
    assert lines(conn) == {}


def test_view_training_supplement_is_hidden_without_training(conn: sqlite3.Connection) -> None:
    new_supplement(conn, "Кофеин", schedule="before")
    assert lines(conn) == {}


def test_view_taken_follows_intake_of_own_kind(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    supplement = new_supplement(conn)
    save_intake(conn, payload("med", course, 1), NOW)
    found = lines(conn)
    assert (found["Витамин D"]["taken"], found["Креатин"]["taken"]) == (True, False)
    assert course == supplement  # одинаковые id разных видов не смешиваются


def test_view_taken_false_on_other_day(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import intake_view, save_intake

    save_intake(conn, payload("med", new_course(conn), 1, "2026-11-07"), NOW)
    assert intake_view(conn, D)[0]["taken"] is False


# --- save_intake ---


def test_taken_writes_row_of_own_kind_with_null_dose(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    save_intake(conn, payload("med", course, 1), NOW)
    [row] = list_intake(conn, D, D, "med")
    assert (row["item_id"], row["dose"], row["note"], row["date"]) == (course, None, None, D)
    assert list_intake(conn, D, D) == []


def test_taken_supplement_writes_supplement_kind(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    sid = new_supplement(conn)
    save_intake(conn, payload("supplement", sid, 1), NOW)
    [row] = list_intake(conn, D, D)
    assert (row["kind"], row["item_id"], row["dose"]) == ("supplement", sid, None)
    assert list_intake(conn, D, D, "med") == []


@pytest.mark.parametrize("taken", [1, 0])
def test_save_replies_with_taken(conn: sqlite3.Connection, taken: int) -> None:
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    assert save_intake(conn, payload("med", course, taken), NOW) == {"taken": taken}


def test_second_taken_does_not_create_second_row(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    save_intake(conn, payload("med", course, 1), NOW)
    save_intake(conn, payload("med", course, 1), NOW)
    assert len(list_intake(conn, D, D, "med")) == 1


def test_untaken_removes_all_live_intakes_of_the_day(conn: sqlite3.Connection) -> None:
    from ai_coach.store.intake import log_intake
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    for hour in ("08", "20"):
        log_intake(conn, {"item_id": course, "date": D, "taken_at": f"{D} {hour}:00:00"}, "med")
    save_intake(conn, payload("med", course, 0), NOW)
    assert list_intake(conn, D, D, "med") == []


def test_untaken_keeps_other_item_and_other_day(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    first = new_course(conn, "Первый")
    second = new_course(conn, "Второй")
    save_intake(conn, payload("med", first, 1), NOW)
    save_intake(conn, payload("med", second, 1), NOW)
    save_intake(conn, payload("med", first, 1, "2026-11-07"), NOW)
    save_intake(conn, payload("med", first, 0), NOW)
    assert [r["name"] for r in list_intake(conn, "2026-11-07", D, "med")] == ["Первый", "Второй"]


def test_untaken_does_not_touch_supplement_with_same_id(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    supplement = new_supplement(conn)
    save_intake(conn, payload("supplement", supplement, 1), NOW)
    save_intake(conn, payload("med", course, 0), NOW)
    assert len(list_intake(conn, D, D)) == 1


def test_taken_again_after_untaken_writes_new_row(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    save_intake(conn, payload("med", course, 1), NOW)
    save_intake(conn, payload("med", course, 0), NOW)
    save_intake(conn, payload("med", course, 1), NOW)
    assert len(list_intake(conn, D, D, "med")) == 1


def test_past_day_can_be_marked(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    save_intake(conn, payload("med", course, 1, "2026-11-05"), NOW)
    assert len(list_intake(conn, "2026-11-05", "2026-11-05", "med")) == 1


def test_today_before_any_item_started_can_be_marked(conn: sqlite3.Connection) -> None:
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    early = datetime.fromisoformat(f"{D}T06:00:00")
    save_intake(conn, payload("med", course, 1), early)
    assert len(list_intake(conn, D, D, "med")) == 1


def test_future_day_is_refused_and_nothing_written(conn: sqlite3.Connection) -> None:
    from ai_coach.web.errors import MarkError
    from ai_coach.web.intake import save_intake

    course = new_course(conn, start_date="2026-11-01")
    with pytest.raises(MarkError):
        save_intake(conn, payload("med", course, 1, "2026-11-09"), NOW)
    assert list_intake(conn, "2026-11-09", "2026-11-09", "med") == []


@pytest.mark.parametrize("kind", ["protocol", "", None, 5])
def test_foreign_kind_is_refused(conn: sqlite3.Connection, kind: Any) -> None:
    from ai_coach.web.errors import MarkError
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    with pytest.raises(MarkError):
        save_intake(conn, payload(kind, course, 1), NOW)
    assert list_intake(conn, D, D, "med") == []


@pytest.mark.parametrize("item_id", [999, 0, -1, "1", None, True])
def test_foreign_item_id_is_refused(conn: sqlite3.Connection, item_id: Any) -> None:
    from ai_coach.web.errors import MarkError
    from ai_coach.web.intake import save_intake

    new_course(conn)
    with pytest.raises(MarkError):
        save_intake(conn, payload("med", item_id, 1), NOW)
    assert list_intake(conn, D, D, "med") == []


def test_item_not_in_block_of_the_day_is_refused(conn: sqlite3.Connection) -> None:
    from ai_coach.web.errors import MarkError
    from ai_coach.web.intake import save_intake

    course = new_course(conn, end_date="2026-11-07")
    with pytest.raises(MarkError):
        save_intake(conn, payload("med", course, 1), NOW)
    assert list_intake(conn, D, D, "med") == []


@pytest.mark.parametrize("taken", [2, -1, "1", None, True])
def test_bad_taken_is_refused(conn: sqlite3.Connection, taken: Any) -> None:
    from ai_coach.web.errors import MarkError
    from ai_coach.web.intake import save_intake

    course = new_course(conn)
    with pytest.raises(MarkError):
        save_intake(conn, payload("med", course, taken), NOW)
    assert list_intake(conn, D, D, "med") == []
