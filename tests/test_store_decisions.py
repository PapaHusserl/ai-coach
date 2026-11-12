"""Шаг Н29, партия 2: store/decisions.py поверх decision_log."""

import sqlite3
from typing import Any

from ai_coach.store.decisions import (
    add_decision,
    close_decision,
    get_decision,
    list_decisions,
    open_by_ref,
    open_decisions,
    set_result,
)

CREATED = "2026-11-10 20:00:00"
DECIDED = "2026-11-11 09:00:00"


def put(conn: sqlite3.Connection, text: str = "решить", **extra: Any) -> int:
    values = {"text": text, "created_at": CREATED, **extra}
    return add_decision(conn, values)


def test_add_returns_id_and_open_status(conn: sqlite3.Connection) -> None:
    decision_id = put(conn)
    row = get_decision(conn, decision_id)
    assert row is not None
    assert (row["id"], row["status"], row["text"]) == (decision_id, "open", "решить")


def test_get_unknown_is_none(conn: sqlite3.Connection) -> None:
    assert get_decision(conn, 999) is None


def test_open_by_ref_finds_open_item_of_object(conn: sqlite3.Connection) -> None:
    decision_id = put(conn, kind="workout", ref_id=7)
    found = open_by_ref(conn, "workout", 7)
    assert found is not None
    assert found["id"] == decision_id


def test_open_by_ref_ignores_other_kind(conn: sqlite3.Connection) -> None:
    put(conn, kind="phase", ref_id=7)
    assert open_by_ref(conn, "workout", 7) is None


def test_open_by_ref_ignores_closed_item(conn: sqlite3.Connection) -> None:
    decision_id = put(conn, kind="workout", ref_id=7)
    close_decision(conn, decision_id, "yes", DECIDED)
    assert open_by_ref(conn, "workout", 7) is None


def test_close_moves_open_to_each_status(conn: sqlite3.Connection) -> None:
    for status in ("yes", "no", "dropped"):
        decision_id = put(conn)
        assert close_decision(conn, decision_id, status, DECIDED) is True
        row = get_decision(conn, decision_id)
        assert row is not None
        assert (row["status"], row["decided_at"]) == (status, DECIDED)


def test_close_closed_returns_false_and_keeps_row(conn: sqlite3.Connection) -> None:
    decision_id = put(conn)
    close_decision(conn, decision_id, "yes", DECIDED)
    assert close_decision(conn, decision_id, "no", "2026-11-12 10:00:00") is False
    row = get_decision(conn, decision_id)
    assert row is not None
    assert (row["status"], row["decided_at"]) == ("yes", DECIDED)


def test_close_unknown_returns_false(conn: sqlite3.Connection) -> None:
    assert close_decision(conn, 999, "yes", DECIDED) is False


def test_set_result_on_yes_without_result(conn: sqlite3.Connection) -> None:
    decision_id = put(conn)
    close_decision(conn, decision_id, "yes", DECIDED)
    assert set_result(conn, decision_id, "kept", "2026-11-13 08:00:00") is True
    row = get_decision(conn, decision_id)
    assert row is not None
    assert (row["result"], row["result_at"]) == ("kept", "2026-11-13 08:00:00")


def test_set_result_second_time_returns_false_and_keeps_first(conn: sqlite3.Connection) -> None:
    decision_id = put(conn)
    close_decision(conn, decision_id, "yes", DECIDED)
    set_result(conn, decision_id, "kept", "2026-11-13 08:00:00")
    assert set_result(conn, decision_id, "missed", "2026-11-14 08:00:00") is False
    row = get_decision(conn, decision_id)
    assert row is not None
    assert row["result"] == "kept"


def test_set_result_on_open_or_no_returns_false(conn: sqlite3.Connection) -> None:
    open_id = put(conn)
    no_id = put(conn)
    close_decision(conn, no_id, "no", DECIDED)
    assert set_result(conn, open_id, "kept", DECIDED) is False
    assert set_result(conn, no_id, "kept", DECIDED) is False


def test_open_decisions_only_open(conn: sqlite3.Connection) -> None:
    open_id = put(conn, "открытое")
    closed_id = put(conn, "закрытое")
    close_decision(conn, closed_id, "yes", DECIDED)
    assert [r["id"] for r in open_decisions(conn)] == [open_id]


def test_open_decisions_order_by_target_date_then_no_date_last(conn: sqlite3.Connection) -> None:
    after = put(conn, "послезавтра", target_date="2026-11-14")
    no_date = put(conn, "без даты")
    tomorrow = put(conn, "завтра", target_date="2026-11-13")
    overdue = put(conn, "просрочено", target_date="2026-11-11")
    assert [r["id"] for r in open_decisions(conn)] == [overdue, tomorrow, after, no_date]


def test_open_decisions_same_day_older_created_first(conn: sqlite3.Connection) -> None:
    newer = put(conn, "новее", target_date="2026-11-13", created_at="2026-11-11 10:00:00")
    older = put(conn, "старее", target_date="2026-11-13", created_at="2026-11-10 10:00:00")
    assert [r["id"] for r in open_decisions(conn)] == [older, newer]


def test_open_decisions_no_date_rows_older_created_first(conn: sqlite3.Connection) -> None:
    newer = put(conn, "новее", created_at="2026-11-11 10:00:00")
    older = put(conn, "старее", created_at="2026-11-10 10:00:00")
    assert [r["id"] for r in open_decisions(conn)] == [older, newer]


def test_list_decisions_period_bounds_inclusive(conn: sqlite3.Connection) -> None:
    first = put(conn, "первое", created_at="2026-11-10 00:00:00")
    last = put(conn, "последнее", created_at="2026-11-12 23:59:59")
    put(conn, "до", created_at="2026-11-09 23:59:59")
    put(conn, "после", created_at="2026-11-13 00:00:00")
    found = list_decisions(conn, "2026-11-10", "2026-11-12")
    assert [r["id"] for r in found] == [first, last]


def test_list_decisions_includes_closed_and_orders_by_created(conn: sqlite3.Connection) -> None:
    late = put(conn, "позже", created_at="2026-11-11 12:00:00")
    early = put(conn, "раньше", created_at="2026-11-11 08:00:00")
    close_decision(conn, early, "no", DECIDED)
    found = list_decisions(conn, "2026-11-11", "2026-11-11")
    assert [(r["id"], r["status"]) for r in found] == [(early, "no"), (late, "open")]


def decided(conn: sqlite3.Connection, created: str, at: str) -> int:
    decision_id = put(conn, "x", created_at=created)
    close_decision(conn, decision_id, "yes", at)
    return decision_id


def test_list_decisions_takes_created_before_period_decided_on_first_day(
    conn: sqlite3.Connection,
) -> None:
    item = decided(conn, "2026-11-01 10:00:00", "2026-11-10 00:00:00")
    assert [r["id"] for r in list_decisions(conn, "2026-11-10", "2026-11-12")] == [item]


def test_list_decisions_takes_created_before_period_decided_on_last_day(
    conn: sqlite3.Connection,
) -> None:
    item = decided(conn, "2026-11-01 10:00:00", "2026-11-12 23:59:59")
    assert [r["id"] for r in list_decisions(conn, "2026-11-10", "2026-11-12")] == [item]


def test_list_decisions_skips_created_before_period_decided_after(
    conn: sqlite3.Connection,
) -> None:
    decided(conn, "2026-11-01 10:00:00", "2026-11-13 00:00:00")
    assert list_decisions(conn, "2026-11-10", "2026-11-12") == []


def test_list_decisions_skips_created_before_period_and_open(conn: sqlite3.Connection) -> None:
    put(conn, "открытое", created_at="2026-11-01 10:00:00")
    assert list_decisions(conn, "2026-11-10", "2026-11-12") == []


def test_list_decisions_row_matching_both_dates_comes_once(conn: sqlite3.Connection) -> None:
    item = decided(conn, "2026-11-10 10:00:00", "2026-11-11 10:00:00")
    assert [r["id"] for r in list_decisions(conn, "2026-11-10", "2026-11-12")] == [item]


def test_list_decisions_orders_by_created_at_then_id(conn: sqlite3.Connection) -> None:
    late = decided(conn, "2026-11-11 12:00:00", "2026-11-11 13:00:00")
    first_same = decided(conn, "2026-11-10 08:00:00", "2026-11-11 13:00:00")
    second_same = decided(conn, "2026-11-10 08:00:00", "2026-11-11 13:00:00")
    found = list_decisions(conn, "2026-11-10", "2026-11-12")
    assert [r["id"] for r in found] == [first_same, second_same, late]
