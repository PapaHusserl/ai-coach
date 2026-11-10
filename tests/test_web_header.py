"""Шапка пульта: показатели дня, вес, синк (шаг П4, партия 3)."""

import sqlite3
from datetime import date, datetime
from typing import Any

import pytest

from ai_coach.store.garmin_data import upsert_daily_metrics
from ai_coach.store.journal import add_sync_log, add_weight, list_weights
from ai_coach.web.errors import MarkError
from ai_coach.web.header import header_view, save_weight, sync_view

DAY = date(2026, 11, 7)
D = "2026-11-07"
NOW = datetime(2026, 11, 7, 9, 30, 15)


def test_save_weight_writes_weight_log_row(conn: sqlite3.Connection) -> None:
    reply = save_weight(conn, {"kg": 81.7}, NOW)
    [row] = list_weights(conn, D, D)
    assert reply == {"id": row["id"]}
    assert (row["weight_kg"], row["measured_at"]) == (81.7, f"{D} 09:30:15")


def test_save_weight_accepts_comma(conn: sqlite3.Connection) -> None:
    save_weight(conn, {"kg": "81,7"}, NOW)
    assert [r["weight_kg"] for r in list_weights(conn, D, D)] == [81.7]


@pytest.mark.parametrize("kg", [20, 300])
def test_save_weight_accepts_limits(conn: sqlite3.Connection, kg: int) -> None:
    save_weight(conn, {"kg": kg}, NOW)
    assert [r["weight_kg"] for r in list_weights(conn, D, D)] == [kg]


@pytest.mark.parametrize("kg", [19, 301, 19.9, "abc", None, True])
def test_save_weight_out_of_range_is_rejected_and_nothing_written(
    conn: sqlite3.Connection, kg: Any
) -> None:
    with pytest.raises(MarkError):
        save_weight(conn, {"kg": kg}, NOW)
    assert list_weights(conn, "2026-01-01", "2026-12-31") == []


def test_save_weight_without_kg_is_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(MarkError):
        save_weight(conn, {}, NOW)


def test_header_weight_is_latest_up_to_day(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-11-05 07:00:00", "weight_kg": 82.0})
    add_weight(conn, {"measured_at": "2026-11-06 07:00:00", "weight_kg": 81.5})
    add_weight(conn, {"measured_at": "2026-11-08 07:00:00", "weight_kg": 90.0})
    weight = header_view(conn, DAY, NOW)["weight"]
    assert weight == {"kg": 81.5, "measured_at": "2026-11-06 07:00:00"}


def test_header_weight_29_days_back_is_shown(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-09 07:00:00", "weight_kg": 82.0})
    assert header_view(conn, DAY, NOW)["weight"]["kg"] == 82.0


def test_header_weight_exactly_30_days_back_is_shown(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-08 07:00:00", "weight_kg": 82.0})
    assert header_view(conn, DAY, NOW)["weight"]["kg"] == 82.0


def test_header_weight_31_days_back_is_none(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-07 07:00:00", "weight_kg": 82.0})
    assert header_view(conn, DAY, NOW)["weight"] is None


def test_header_sync_without_logs_has_constant_shape(conn: sqlite3.Connection) -> None:
    sync = header_view(conn, DAY, NOW)["sync"]
    assert sync == {"finished_at": None, "status": None, "running": False, "error": None}


def test_header_metrics_row_without_readiness_keeps_other_fields(
    conn: sqlite3.Connection,
) -> None:
    put_metrics(conn, D, sleep_seconds=27000, hrv_last_night=55)
    metrics = header_view(conn, DAY, NOW)["metrics"]
    assert metrics["readiness"] is None
    assert (metrics["sleep_h"], metrics["hrv"], metrics["rhr"]) == (7.5, 55, 48)


def test_sync_view_without_logs_has_no_last(conn: sqlite3.Connection) -> None:
    assert sync_view(conn, DAY, NOW)["last"] is None


def test_sync_view_last_has_four_keys(conn: sqlite3.Connection) -> None:
    add_sync_log(
        conn,
        {
            "started_at": "2026-11-03T08:00:00",
            "kind": "sync",
            "status": "ok",
            "finished_at": "2026-11-03T08:00:45",
            "message": "y",
        },
    )
    view = sync_view(conn, DAY, NOW)
    assert view["last"] == {
        "started_at": "2026-11-03T08:00:00",
        "finished_at": "2026-11-03T08:00:45",
        "status": "ok",
        "message": "y",
    }
    assert view["running"] is False


def test_header_weight_older_than_30_days_is_none(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-01 07:00:00", "weight_kg": 82.0})
    assert header_view(conn, DAY, NOW)["weight"] is None


def test_header_weight_without_records_is_none(conn: sqlite3.Connection) -> None:
    assert header_view(conn, DAY, NOW)["weight"] is None


def put_metrics(conn: sqlite3.Connection, day: str, **fields: Any) -> None:
    values = {"date": day, "raw_json": {"sleep": {"restingHeartRate": 48}}} | fields
    upsert_daily_metrics(conn, values)


def test_header_metrics_are_of_the_viewed_day(conn: sqlite3.Connection) -> None:
    put_metrics(conn, "2026-11-06", readiness_score=10, sleep_seconds=3600, hrv_last_night=1)
    put_metrics(conn, D, readiness_score=77, sleep_seconds=27000, hrv_last_night=55)
    assert header_view(conn, DAY, NOW)["metrics"] == {
        "readiness": 77,
        "sleep_h": 7.5,
        "hrv": 55,
        "rhr": 48,
    }


def test_header_metrics_without_day_row_is_none(conn: sqlite3.Connection) -> None:
    put_metrics(conn, "2026-11-06", readiness_score=10)
    assert header_view(conn, DAY, NOW)["metrics"] is None


def test_header_sync_is_last_log_not_by_day(conn: sqlite3.Connection) -> None:
    add_sync_log(
        conn,
        {
            "started_at": "2026-11-01T08:00:00",
            "kind": "sync",
            "status": "error",
            "finished_at": "2026-11-01T08:00:30",
            "message": "x",
        },
    )
    add_sync_log(
        conn,
        {
            "started_at": "2026-11-03T08:00:00",
            "kind": "sync",
            "status": "ok",
            "finished_at": "2026-11-03T08:00:45",
            "message": "y",
        },
    )
    sync = header_view(conn, DAY, NOW)["sync"]
    assert sync == {
        "finished_at": "2026-11-03T08:00:45",
        "status": "ok",
        "running": False,
        "error": None,
    }


def put_log(conn: sqlite3.Connection, status: str, message: str) -> None:
    add_sync_log(
        conn,
        {
            "started_at": "2026-11-03T08:00:00",
            "kind": "sync",
            "status": status,
            "finished_at": "2026-11-03T08:00:45",
            "message": message,
        },
    )


def test_header_sync_error_is_thread_error_even_if_last_log_is_ok(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach.web import syncer

    monkeypatch.setitem(syncer._state, "error", "Токенов Garmin нет. Выполни: coach login")  # pyright: ignore[reportPrivateUsage]
    put_log(conn, "ok", "нагрузка")
    sync = header_view(conn, DAY, NOW)["sync"]
    assert sync["error"] == "Токенов Garmin нет. Выполни: coach login"


def test_header_sync_error_is_last_log_message_when_status_not_ok(
    conn: sqlite3.Connection,
) -> None:
    put_log(conn, "error", "Garmin 429")
    assert header_view(conn, DAY, NOW)["sync"]["error"] == "Garmin 429"


def test_header_sync_error_thread_wins_over_log_message(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach.web import syncer

    monkeypatch.setitem(syncer._state, "error", "ошибка потока")  # pyright: ignore[reportPrivateUsage]
    put_log(conn, "error", "Garmin 429")
    assert header_view(conn, DAY, NOW)["sync"]["error"] == "ошибка потока"
