"""Шаг П12, партия 2: store/forms.py поверх forms и form_log."""

import json
import sqlite3
from typing import Any

from ai_coach.store.forms import (
    add_form,
    add_form_entry,
    archive_form,
    get_form,
    list_form_log,
    list_forms,
)
from workload_fakes import coach_event

from ai_coach.store.agenda import add_event

CREATED = "2026-11-15 10:00:00"
ARCHIVED = "2026-11-16 09:00:00"
FIELDS = [{"key": "temperature", "type": "number", "label": "Температура", "unit": "°C"}]


def put(conn: sqlite3.Connection, name: str = "temp", **extra: Any) -> None:
    values = {
        "name": name,
        "title": "Температура",
        "fields_json": json.dumps(FIELDS, ensure_ascii=False),
        "created_at": CREATED,
    }
    add_form(conn, values | extra)


def entry(conn: sqlite3.Connection, day: str, clock: str = "09:00:00", **extra: Any) -> int:
    event_id = add_event(conn, coach_event(survey="form:temp"))
    values = {
        "date": day,
        "time": clock,
        "event_id": event_id,
        "form": "temp",
        "values_json": json.dumps({"temperature": 37.2}),
        "text": None,
    }
    return add_form_entry(conn, values | extra)


def test_get_form_returns_stored_definition(conn: sqlite3.Connection) -> None:
    put(conn)
    row = get_form(conn, "temp")
    assert row is not None
    assert (row["name"], row["title"], row["archived_at"]) == ("temp", "Температура", None)
    assert json.loads(row["fields_json"]) == FIELDS


def test_get_form_unknown_is_none(conn: sqlite3.Connection) -> None:
    assert get_form(conn, "нет") is None


def test_list_forms_returns_active_forms(conn: sqlite3.Connection) -> None:
    put(conn, "temp")
    put(conn, "rpe")
    assert sorted(r["name"] for r in list_forms(conn)) == ["rpe", "temp"]


def test_archive_form_sets_archived_at(conn: sqlite3.Connection) -> None:
    put(conn)
    assert archive_form(conn, "temp", ARCHIVED) is True
    row = get_form(conn, "temp")
    assert row is not None
    assert row["archived_at"] == ARCHIVED


def test_archived_form_is_not_listed(conn: sqlite3.Connection) -> None:
    put(conn, "temp")
    put(conn, "rpe")
    archive_form(conn, "temp", ARCHIVED)
    assert [r["name"] for r in list_forms(conn)] == ["rpe"]


def test_archive_unknown_form_is_false(conn: sqlite3.Connection) -> None:
    assert archive_form(conn, "нет", ARCHIVED) is False


def test_add_form_entry_returns_id(conn: sqlite3.Connection) -> None:
    put(conn)
    assert isinstance(entry(conn, "2026-11-15"), int)


def test_list_form_log_takes_days_in_period_only(conn: sqlite3.Connection) -> None:
    put(conn)
    for day in ("2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17"):
        entry(conn, day)
    rows = list_form_log(conn, "2026-11-15", "2026-11-16")
    assert [r["date"] for r in rows] == ["2026-11-15", "2026-11-16"]


def test_list_form_log_is_ordered_by_date_and_time(conn: sqlite3.Connection) -> None:
    put(conn)
    entry(conn, "2026-11-16", "08:00:00")
    entry(conn, "2026-11-15", "21:00:00")
    entry(conn, "2026-11-15", "09:00:00")
    rows = list_form_log(conn, "2026-11-15", "2026-11-16")
    assert [(r["date"], r["time"]) for r in rows] == [
        ("2026-11-15", "09:00:00"),
        ("2026-11-15", "21:00:00"),
        ("2026-11-16", "08:00:00"),
    ]


def test_second_entry_of_same_event_is_second_row(conn: sqlite3.Connection) -> None:
    put(conn)
    first = entry(conn, "2026-11-15", "09:00:00")
    event_id = conn.execute("SELECT event_id FROM form_log WHERE id = ?", (first,)).fetchone()[0]
    entry(conn, "2026-11-15", "09:30:00", event_id=event_id)
    assert len(list_form_log(conn, "2026-11-15", "2026-11-15")) == 2


def test_list_form_log_row_has_form_event_and_values(conn: sqlite3.Connection) -> None:
    put(conn)
    entry(conn, "2026-11-15", text="знобит")
    row = list_form_log(conn, "2026-11-15", "2026-11-15")[0]
    assert row["form"] == "temp"
    assert row["text"] == "знобит"
    assert json.loads(row["values_json"]) == {"temperature": 37.2}
    assert row["event_id"] is not None


def test_list_form_log_empty_period(conn: sqlite3.Connection) -> None:
    assert list_form_log(conn, "2026-11-15", "2026-11-16") == []
