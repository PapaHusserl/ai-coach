"""Шаг П12, партия 2: инструменты MCP create_form, archive_form, get_forms, get_form_log."""

import json
import sqlite3
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call
from workload_fakes import coach_event

from ai_coach.store.agenda import add_event
from ai_coach.store.forms import add_form_entry, get_form

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
}


def create(conn: sqlite3.Connection, name: str = "temp", **fields: Any) -> Any:
    arguments = {"name": name, "title": "Температура", "fields": [SCORE, TEMPERATURE]} | fields
    return call(conn, "create_form", **arguments)


def form_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM forms").fetchone()[0]


def test_create_form_stores_definition(conn: sqlite3.Connection) -> None:
    create(conn)
    row = get_form(conn, "temp")
    assert row is not None
    assert (row["title"], row["archived_at"]) == ("Температура", None)
    assert json.loads(row["fields_json"])[1]["unit"] == "°C"


def test_create_form_twice_is_error_and_keeps_one_form(conn: sqlite3.Connection) -> None:
    create(conn)
    with pytest.raises(ToolError):
        create(conn)
    assert form_count(conn) == 1


def test_create_form_with_bad_name_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        create(conn, name="my temp")
    assert form_count(conn) == 0


def test_create_form_with_ready_survey_name_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        create(conn, name="feel")
    assert form_count(conn) == 0


def test_create_form_with_scale_without_poles_is_error(conn: sqlite3.Connection) -> None:
    field = {"key": "mood", "type": "scale", "label": "Настроение"}
    with pytest.raises(ToolError):
        create(conn, fields=[field])
    assert form_count(conn) == 0


def test_create_form_with_scale_poles_stores_them(conn: sqlite3.Connection) -> None:
    field = {
        "key": "mood",
        "type": "scale",
        "label": "Настроение",
        "low": "плохо",
        "high": "хорошо",
    }
    create(conn, fields=[field])
    stored = call(conn, "get_forms")["rows"][0]["fields"][0]
    assert (stored["low"], stored["high"]) == ("плохо", "хорошо")


def test_create_form_with_unit_on_scale_is_error(conn: sqlite3.Connection) -> None:
    field = {"key": "score", "type": "scale", "label": "Самочувствие", "unit": "балл"}
    with pytest.raises(ToolError):
        create(conn, fields=[field])
    assert form_count(conn) == 0


def test_archive_unknown_form_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError):
        call(conn, "archive_form", name="нет")


def test_archive_form_sets_archived_at(conn: sqlite3.Connection) -> None:
    create(conn)
    call(conn, "archive_form", name="temp")
    row = get_form(conn, "temp")
    assert row is not None
    assert row["archived_at"] is not None


def test_get_forms_without_forms_is_empty(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_forms") == {"rows": [], "truncated": False}


def test_get_forms_gives_fields_as_object(conn: sqlite3.Connection) -> None:
    create(conn)
    row = call(conn, "get_forms")["rows"][0]
    assert row["name"] == "temp"
    assert [f["key"] for f in row["fields"]] == ["score", "temperature"]
    assert "fields_json" not in row


def test_get_forms_gives_options_of_choice_as_list(conn: sqlite3.Connection) -> None:
    create(conn, name="stool", title="Стул", fields=[STOOL])
    field = call(conn, "get_forms")["rows"][0]["fields"][0]
    assert field["options"] == ["норма", "жидкий", "твёрдый"]


def test_get_forms_skips_archived_form(conn: sqlite3.Connection) -> None:
    create(conn, name="temp")
    create(conn, name="stool", title="Стул", fields=[STOOL])
    call(conn, "archive_form", name="temp")
    assert [r["name"] for r in call(conn, "get_forms")["rows"]] == ["stool"]


def test_get_form_log_without_entries_is_empty(conn: sqlite3.Connection) -> None:
    create(conn)
    result = call(conn, "get_form_log", date_from="2026-11-01", date_to="2026-11-30")
    assert result == {"rows": [], "truncated": False}


def test_get_form_log_gives_entry_with_values_as_object(conn: sqlite3.Connection) -> None:
    create(conn)
    event_id = add_event(conn, coach_event(kind="checkin", category=None, survey="form:temp"))
    add_form_entry(
        conn,
        {
            "date": "2026-11-15",
            "time": "09:00:00",
            "event_id": event_id,
            "form": "temp",
            "values_json": json.dumps({"temperature": 37.2}),
            "text": "знобит",
        },
    )
    rows = call(conn, "get_form_log", date_from="2026-11-15", date_to="2026-11-15")["rows"]
    assert len(rows) == 1
    assert (rows[0]["form"], rows[0]["event_id"], rows[0]["text"]) == ("temp", event_id, "знобит")
    assert rows[0]["values"] == {"temperature": 37.2}
