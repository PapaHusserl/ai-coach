"""WHO-5: балл, сигналы и отчёт на день (load/who5.py), план Н12."""

import sqlite3

import pytest

from ai_coach.load.who5 import who5_report, who5_score, who5_signals
from ai_coach.store.journal import add_who5

DAY = "2026-11-02"


def put(conn: sqlite3.Connection, day: str, score: int, at: str = "09:00:00") -> None:
    """Замер с нужным баллом (кратным 4, не больше 100): ответы раскладываются по пяти."""
    total = score // 4
    items = [min(5, max(0, total - 5 * n)) for n in range(5)]
    add_who5(
        conn,
        {
            "date": day,
            "logged_at": f"{day} {at}",
            **{f"q{n}": value for n, value in enumerate(items, 1)},
            "score": score,
            "text": None,
        },
    )


@pytest.mark.parametrize(
    ("items", "score"),
    [
        ([5, 5, 5, 5, 5], 100),
        ([0, 0, 0, 0, 0], 0),
        ([5, 4, 3, 4, 5], 84),
        ([1, 1, 1, 1, 3], 28),
    ],
)
def test_score_is_sum_times_four(items: list[int], score: int) -> None:
    assert who5_score(items) == score


def kinds(score: int, prev: int | None, days: int) -> list[str]:
    return [s["kind"] for s in who5_signals(score, prev, days)]


def test_signal_low_at_28_has_value_and_limit() -> None:
    assert who5_signals(28, None, 0) == [{"kind": "who5_low", "value": 28, "limit": 28}]


def test_signal_29_is_reduced_not_low() -> None:
    assert kinds(29, None, 0) == ["who5_reduced"]


def test_signal_50_is_reduced() -> None:
    assert who5_signals(50, None, 0) == [{"kind": "who5_reduced", "value": 50, "limit": 50}]


def test_signal_51_is_none() -> None:
    assert kinds(51, None, 0) == []


def test_signal_drop_of_10_has_value() -> None:
    assert who5_signals(60, 70, 0) == [{"kind": "who5_drop", "value": 10, "limit": 10}]


def test_signal_drop_of_9_is_none() -> None:
    assert kinds(61, 70, 0) == []


def test_signal_rise_is_not_drop() -> None:
    assert kinds(80, 60, 0) == []


def test_signal_low_after_14_days_is_gone() -> None:
    assert kinds(20, None, 14) == []


def test_signal_low_at_13_days_is_kept() -> None:
    assert kinds(20, None, 13) == ["who5_low"]


def test_signals_reduced_and_drop_after_14_days_are_gone() -> None:
    assert kinds(45, 60, 14) == []


def test_signals_reduced_and_drop_at_13_days_are_kept() -> None:
    assert kinds(45, 60, 13) == ["who5_reduced", "who5_drop"]


def test_low_and_reduced_never_come_together() -> None:
    for score in range(0, 101, 4):
        assert not {"who5_low", "who5_reduced"} <= set(kinds(score, None, 0))


def test_report_on_empty_base(conn: sqlite3.Connection) -> None:
    assert who5_report(conn, DAY) == {
        "last_date": None,
        "score": None,
        "prev_date": None,
        "prev_score": None,
        "delta": None,
        "days_since": None,
        "due": True,
        "low_until": None,
        "signals": [],
    }


def test_report_last_yesterday_is_not_due(conn: sqlite3.Connection) -> None:
    put(conn, "2026-11-01", 84)
    report = who5_report(conn, DAY)
    assert (report["score"], report["last_date"]) == (84, "2026-11-01")
    assert (report["days_since"], report["due"], report["delta"]) == (1, False, None)
    assert (report["prev_date"], report["prev_score"]) == (None, None)
    assert (report["signals"], report["low_until"]) == ([], None)


def test_report_two_entries_give_delta_and_signals(conn: sqlite3.Connection) -> None:
    put(conn, "2026-10-13", 72)
    put(conn, "2026-11-01", 56)
    report = who5_report(conn, DAY)
    assert (report["prev_date"], report["prev_score"]) == ("2026-10-13", 72)
    assert report["delta"] == -16
    assert [s["kind"] for s in report["signals"]] == ["who5_drop"]
    assert report["signals"][0]["value"] == 16


def test_report_28_yesterday_is_low_until_two_weeks_later(conn: sqlite3.Connection) -> None:
    put(conn, "2026-11-01", 28)
    report = who5_report(conn, DAY)
    assert [s["kind"] for s in report["signals"]] == ["who5_low"]
    assert report["low_until"] == "2026-11-15"


def test_report_reduced_has_no_low_until(conn: sqlite3.Connection) -> None:
    put(conn, "2026-11-01", 44)
    report = who5_report(conn, DAY)
    assert [s["kind"] for s in report["signals"]] == ["who5_reduced"]
    assert report["low_until"] is None


def test_report_entry_14_days_ago_is_due(conn: sqlite3.Connection) -> None:
    put(conn, "2026-10-19", 84)
    report = who5_report(conn, DAY)
    assert (report["days_since"], report["due"]) == (14, True)


def test_report_entry_13_days_ago_is_not_due(conn: sqlite3.Connection) -> None:
    put(conn, "2026-10-20", 84)
    assert who5_report(conn, DAY)["due"] is False


def test_report_does_not_read_entries_after_day(conn: sqlite3.Connection) -> None:
    put(conn, "2026-10-30", 84)
    put(conn, "2026-11-05", 20)
    report = who5_report(conn, DAY)
    assert (report["last_date"], report["score"]) == ("2026-10-30", 84)
    assert report["signals"] == []


def test_report_same_day_entry_counts(conn: sqlite3.Connection) -> None:
    put(conn, DAY, 84)
    assert who5_report(conn, DAY)["days_since"] == 0


def test_report_same_date_later_entry_is_last(conn: sqlite3.Connection) -> None:
    put(conn, DAY, 40, "08:00:00")
    put(conn, DAY, 80, "21:00:00")
    report = who5_report(conn, DAY)
    assert (report["score"], report["prev_score"]) == (80, 40)
