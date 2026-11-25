"""ai_coach.load.attention (Н8, партия 1б; сигнатуры - из «Партия 1: сигнатуры» плана):

baseline(values) -> float | None: медиана значений без None; значений меньше MIN_BASE_DAYS - None.
find_attention(rate, median, stretch) -> [{"kind", "value", "limit"}]: switching_high при
rate >= SWITCH_FACTOR * median, затем long_stretch при stretch >= STRETCH_LIMIT_HOURS.
attention_report(conn, day) -> dict: оценивается день day - 1 (date, switches_hour,
switches_median, base_days, stretch_hours, signals); база - BASE_DAYS дней до оцениваемого.
"""

import sqlite3
from datetime import date, timedelta
from typing import Any

from ai_coach.load.attention import attention_report, baseline, find_attention

from ai_coach.load import attention
from ai_coach.store.workload import upsert_counter

DAY = "2026-11-10"
EVALUATED = "2026-11-09"
SWITCHES = "screen_switches_hour"
STRETCH = "screen_stretch_hours"


def shift(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


def put(conn: sqlite3.Connection, day: str, kind: str, value: float) -> None:
    upsert_counter(
        conn,
        {
            "date": day,
            "kind": kind,
            "value": value,
            "source": "screen",
            "raw_json": None,
            "synced_at": "2026-11-10T10:00:00",
        },
    )


def base(conn: sqlite3.Connection, count: int, value: float = 8.0, first_back: int = 1) -> None:
    """count дней подряд со switches = value; первый - за first_back дней до оцениваемого."""
    for number in range(count):
        put(conn, shift(EVALUATED, -(first_back + number)), SWITCHES, value)


def test_constants() -> None:
    assert attention.SWITCH_FACTOR == 1.5
    assert attention.BASE_DAYS == 28
    assert attention.MIN_BASE_DAYS == 14
    assert attention.STRETCH_LIMIT_HOURS == 2.0


# --- baseline ---


def test_baseline_of_fourteen_values_is_the_median() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 8.0, 8.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]
    assert baseline(values) == 8.0


def test_baseline_of_thirteen_values_is_none() -> None:
    assert baseline([8.0] * 13) is None


def test_baseline_does_not_count_none() -> None:
    assert baseline([8.0] * 13 + [None]) is None


def test_baseline_skips_none_when_enough_values() -> None:
    assert baseline([None, *([8.0] * 14), None]) == 8.0


def test_baseline_of_empty_is_none() -> None:
    assert baseline([]) is None


# --- find_attention ---


def test_switching_high_at_the_limit() -> None:
    found = find_attention(12.0, 8.0, 0.0)
    assert found == [{"kind": "switching_high", "value": 12.0, "limit": 12.0}]


def test_no_switching_just_below_the_limit() -> None:
    assert find_attention(11.9, 8.0, 0.0) == []


def test_no_switching_without_median() -> None:
    assert find_attention(30.0, None, 0.0) == []


def test_no_switching_without_rate() -> None:
    assert find_attention(None, 8.0, 0.0) == []


def test_switching_limit_is_rounded_to_a_tenth() -> None:
    found = find_attention(20.0, 6.37, 0.0)
    assert found == [{"kind": "switching_high", "value": 20.0, "limit": 9.6}]


def test_long_stretch_at_the_limit() -> None:
    found = find_attention(None, None, 2.0)
    assert found == [{"kind": "long_stretch", "value": 2.0, "limit": 2.0}]


def test_no_long_stretch_just_below_the_limit() -> None:
    assert find_attention(None, None, 1.99) == []


def test_both_signals_switching_first() -> None:
    found = find_attention(12.0, 8.0, 2.6)
    assert [signal["kind"] for signal in found] == ["switching_high", "long_stretch"]
    assert found[1] == {"kind": "long_stretch", "value": 2.6, "limit": 2.0}


# --- attention_report ---


def test_report_evaluates_yesterday(conn: sqlite3.Connection) -> None:
    assert attention_report(conn, DAY)["date"] == EVALUATED


def test_report_has_the_agreed_keys(conn: sqlite3.Connection) -> None:
    keys = {"date", "switches_hour", "switches_median", "base_days", "stretch_hours", "signals"}
    assert keys <= set(attention_report(conn, DAY))


def test_report_without_counters_is_empty(conn: sqlite3.Connection) -> None:
    report = attention_report(conn, DAY)
    assert report["switches_hour"] is None
    assert report["stretch_hours"] is None
    assert report["switches_median"] is None
    assert report["base_days"] == 0
    assert report["signals"] == []


def test_report_without_the_evaluated_day_has_no_signals(conn: sqlite3.Connection) -> None:
    base(conn, 20)
    put(conn, DAY, SWITCHES, 50.0)
    put(conn, DAY, STRETCH, 5.0)
    report = attention_report(conn, DAY)
    assert report["signals"] == []
    assert report["switches_hour"] is None


def test_report_shows_the_values_of_the_evaluated_day(conn: sqlite3.Connection) -> None:
    put(conn, EVALUATED, SWITCHES, 5.5)
    put(conn, EVALUATED, STRETCH, 1.25)
    report = attention_report(conn, DAY)
    assert report["switches_hour"] == 5.5
    assert report["stretch_hours"] == 1.25


def test_report_switching_high_over_the_median(conn: sqlite3.Connection) -> None:
    base(conn, 14)
    put(conn, EVALUATED, SWITCHES, 12.0)
    put(conn, EVALUATED, STRETCH, 0.5)
    report = attention_report(conn, DAY)
    assert report["switches_median"] == 8.0
    assert report["base_days"] == 14
    assert report["signals"] == [{"kind": "switching_high", "value": 12.0, "limit": 12.0}]


def test_report_no_signal_below_the_limit(conn: sqlite3.Connection) -> None:
    base(conn, 14)
    put(conn, EVALUATED, SWITCHES, 11.9)
    put(conn, EVALUATED, STRETCH, 1.0)
    assert attention_report(conn, DAY)["signals"] == []


def test_report_long_stretch_signal(conn: sqlite3.Connection) -> None:
    put(conn, EVALUATED, SWITCHES, 3.0)
    put(conn, EVALUATED, STRETCH, 2.6)
    report = attention_report(conn, DAY)
    assert report["signals"] == [{"kind": "long_stretch", "value": 2.6, "limit": 2.0}]


def test_report_both_signals_switching_first(conn: sqlite3.Connection) -> None:
    base(conn, 14)
    put(conn, EVALUATED, SWITCHES, 13.0)
    put(conn, EVALUATED, STRETCH, 2.0)
    kinds = [signal["kind"] for signal in attention_report(conn, DAY)["signals"]]
    assert kinds == ["switching_high", "long_stretch"]


def test_report_with_thirteen_base_days_has_no_median(conn: sqlite3.Connection) -> None:
    base(conn, 13)
    put(conn, EVALUATED, SWITCHES, 100.0)
    put(conn, EVALUATED, STRETCH, 2.5)
    report = attention_report(conn, DAY)
    assert report["switches_median"] is None
    assert report["base_days"] == 13
    assert [signal["kind"] for signal in report["signals"]] == ["long_stretch"]


def test_report_todays_counters_do_not_change_the_answer(conn: sqlite3.Connection) -> None:
    base(conn, 14)
    put(conn, EVALUATED, SWITCHES, 9.0)
    put(conn, EVALUATED, STRETCH, 1.0)
    before = attention_report(conn, DAY)
    put(conn, DAY, SWITCHES, 99.0)
    put(conn, DAY, STRETCH, 9.0)
    assert attention_report(conn, DAY) == before


def test_report_base_excludes_the_evaluated_day(conn: sqlite3.Connection) -> None:
    base(conn, 13)
    put(conn, EVALUATED, SWITCHES, 100.0)
    assert attention_report(conn, DAY)["base_days"] == 13


def test_report_base_takes_the_28th_day_back(conn: sqlite3.Connection) -> None:
    base(conn, 13)
    put(conn, shift(EVALUATED, -28), SWITCHES, 8.0)
    assert attention_report(conn, DAY)["base_days"] == 14


def test_report_base_leaves_the_29th_day_back(conn: sqlite3.Connection) -> None:
    base(conn, 13)
    put(conn, shift(EVALUATED, -29), SWITCHES, 8.0)
    report: dict[str, Any] = attention_report(conn, DAY)
    assert report["base_days"] == 13
    assert report["switches_median"] is None


def test_report_base_ignores_stretch_counters(conn: sqlite3.Connection) -> None:
    base(conn, 13)
    put(conn, shift(EVALUATED, -14), STRETCH, 3.0)
    assert attention_report(conn, DAY)["base_days"] == 13
