"""Шаг Н29, партия 1: часть дня по часам."""

import sqlite3
from datetime import datetime
from typing import Any

import pytest
from fake_clock import freeze

DAY = "2026-10-07"


@pytest.mark.parametrize(
    ("clock", "part"),
    [
        ("04:00", "morning"),
        ("11:59", "morning"),
        ("12:00", "day"),
        ("18:59", "day"),
        ("19:00", "evening"),
        ("23:59", "evening"),
        ("00:30", "evening"),
        ("03:59", "evening"),
    ],
)
def test_day_part_boundaries(clock: str, part: str) -> None:
    from ai_coach.decisions import day_part

    assert day_part(datetime.fromisoformat(f"{DAY} {clock}:00")) == part


# партия 2: track и settle


def row_of(conn: sqlite3.Connection, decision_id: int) -> dict[str, Any]:
    from ai_coach.store.decisions import get_decision

    found = get_decision(conn, decision_id)
    assert found is not None
    return found


def test_track_puts_open_item(conn: sqlite3.Connection) -> None:
    from ai_coach.decisions import track

    decision_id = track(conn, "workout", 5, "Бег 5 км", "2026-11-13")
    row = row_of(conn, decision_id)
    expected = ("workout", 5, "Бег 5 км", "2026-11-13", "open")
    assert (row["kind"], row["ref_id"], row["text"], row["target_date"], row["status"]) == expected
    assert row["created_at"]


def test_track_without_target_date_gives_null(conn: sqlite3.Connection) -> None:
    from ai_coach.decisions import track

    decision_id = track(conn, "phase", 2, "База", None)
    assert row_of(conn, decision_id)["target_date"] is None


def test_track_takes_time_from_clock(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach.decisions import track

    freeze(monkeypatch, "2026-11-12 09:30:00")
    decision_id = track(conn, "workout", 5, "Бег", "2026-11-13")
    created = row_of(conn, decision_id)["created_at"]
    assert created.startswith("2026-11-12")
    assert "09:30" in created


def test_settle_closes_item_with_decided_at(conn: sqlite3.Connection) -> None:
    from ai_coach.decisions import settle, track

    decision_id = track(conn, "workout", 5, "Бег", "2026-11-13")
    assert settle(conn, "workout", 5, "yes") is True
    row = row_of(conn, decision_id)
    assert row["status"] == "yes"
    assert row["decided_at"]


def test_settle_takes_time_from_clock(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach.decisions import settle, track

    decision_id = track(conn, "workout", 5, "Бег", "2026-11-13")
    freeze(monkeypatch, "2026-11-12 20:15:00")
    settle(conn, "workout", 5, "dropped")
    decided = row_of(conn, decision_id)["decided_at"]
    assert decided.startswith("2026-11-12")
    assert "20:15" in decided


def test_settle_twice_returns_false_and_keeps_row(conn: sqlite3.Connection) -> None:
    from ai_coach.decisions import settle, track

    decision_id = track(conn, "workout", 5, "Бег", "2026-11-13")
    settle(conn, "workout", 5, "yes")
    before = row_of(conn, decision_id)
    assert settle(conn, "workout", 5, "no") is False
    assert row_of(conn, decision_id) == before


def test_settle_object_without_item_returns_false(conn: sqlite3.Connection) -> None:
    from ai_coach.decisions import settle

    assert settle(conn, "workout", 5, "yes") is False
    assert conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == 0


def test_settle_does_not_touch_other_kind(conn: sqlite3.Connection) -> None:
    from ai_coach.decisions import settle, track

    phase_id = track(conn, "phase", 5, "База", None)
    assert settle(conn, "workout", 5, "yes") is False
    assert row_of(conn, phase_id)["status"] == "open"
