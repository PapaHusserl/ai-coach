"""Шаг Н34, партия 1: store/reports.py поверх system_report."""

import sqlite3

from ai_coach.store.reports import add_report, close_report, get_report

CREATED = "2026-11-24 12:00:00"
CLOSED = "2026-11-25 09:00:00"


def put(conn: sqlite3.Connection) -> int:
    return add_report(conn, {"text": "случай", "created_at": CREATED})


def test_close_open_report_sets_fields(conn: sqlite3.Connection) -> None:
    report_id = put(conn)
    assert close_report(conn, report_id, "done", CLOSED, 7) is True
    row = get_report(conn, report_id)
    assert row is not None
    assert (row["status"], row["closed_at"], row["backlog"]) == ("done", CLOSED, 7)


def test_close_missing_report_is_false(conn: sqlite3.Connection) -> None:
    assert close_report(conn, 999, "done", CLOSED, None) is False


def test_close_already_closed_report_is_false_and_unchanged(conn: sqlite3.Connection) -> None:
    report_id = put(conn)
    close_report(conn, report_id, "done", CLOSED, 7)
    assert close_report(conn, report_id, "dropped", "2026-12-01 00:00:00", 8) is False
    row = get_report(conn, report_id)
    assert row is not None
    assert (row["status"], row["closed_at"], row["backlog"]) == ("done", CLOSED, 7)
