"""Долг сна: норма, долг, часы от подъёма, сигналы, отчёт. Синтетические данные."""

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ai_coach.load.sleep import (
    awake_hours,
    night_hours,
    sleep_debt,
    sleep_norm,
    sleep_report,
    sleep_signals,
)
from ai_coach.store.garmin_data import upsert_daily_metrics

TODAY = date(2026, 11, 1)


def night(day: date, hours: float | None, nap: int | None = None) -> dict[str, Any]:
    seconds = None if hours is None else int(hours * 3600)
    return {
        "date": day.isoformat(),
        "sleep_seconds": seconds,
        "sleep_end": None,
        "nap_seconds": nap,
    }


def back(days: int) -> date:
    return TODAY - timedelta(days=days)


def millis(moment: str) -> int:
    return int(datetime.fromisoformat(moment).replace(tzinfo=UTC).timestamp() * 1000)


def put(conn: sqlite3.Connection, day: date, hours: float, wake: str | None = None) -> None:
    sleep: dict[str, Any] = {}
    if wake is not None:
        sleep["dailySleepDTO"] = {"sleepEndTimestampLocal": millis(wake)}
    upsert_daily_metrics(
        conn,
        {
            "date": day.isoformat(),
            "sleep_seconds": int(hours * 3600),
            "raw_json": {"secret": "SECRET", "sleep": sleep},
        },
    )


def seven_hour_nights(conn: sqlite3.Connection, first: date, count: int) -> None:
    for number in range(count):
        put(conn, first + timedelta(days=number), 7)


def report_with(**fields: Any) -> dict[str, Any]:
    base = {"last_night_h": 7.0, "norm_h": 7.0, "debt_7_h": 0.0, "debt_14_h": 0.0}
    return {**base, **fields}


def kinds(report: dict[str, Any]) -> list[str]:
    return [s["kind"] for s in sleep_signals(report)]


# --- night_hours ---


def test_night_hours_converts_seconds() -> None:
    assert night_hours({"sleep_seconds": 27000}) == 7.5


def test_night_hours_zero_is_none() -> None:
    assert night_hours({"sleep_seconds": 0}) is None


def test_night_hours_null_is_none() -> None:
    assert night_hours({"sleep_seconds": None}) is None


# --- sleep_norm ---


def test_norm_is_median_of_nights() -> None:
    nights = [night(back(n), 7) for n in range(1, 21)] + [night(back(21), 4)]
    assert sleep_norm(nights, TODAY) == {"norm_h": 7.0, "nights": 21}


def test_norm_needs_twenty_nights() -> None:
    assert sleep_norm([night(back(n), 7) for n in range(1, 20)], TODAY) is None


def test_norm_ignores_nights_older_than_window() -> None:
    nights = [night(back(n), 7) for n in range(1, 20)] + [night(back(90), 7)]
    assert sleep_norm(nights, TODAY) is None


def test_norm_counts_night_on_oldest_window_day() -> None:
    nights = [night(back(n), 7) for n in range(1, 20)] + [night(back(89), 7)]
    assert sleep_norm(nights, TODAY) == {"norm_h": 7.0, "nights": 20}


def test_norm_skips_nights_without_data() -> None:
    nights = [night(back(n), 7) for n in range(1, 20)] + [night(back(20), 0)]
    assert sleep_norm(nights, TODAY) is None


def test_norm_nights_do_not_include_empty() -> None:
    nights = [night(back(n), 7) for n in range(1, 21)] + [night(back(21), 0)]
    assert sleep_norm(nights, TODAY) == {"norm_h": 7.0, "nights": 20}


def test_norm_rounded_to_hundredths() -> None:
    nights = [{**night(back(n), 7), "sleep_seconds": 22044} for n in range(1, 21)]
    assert sleep_norm(nights, TODAY) == {"norm_h": 6.12, "nights": 20}


# --- sleep_debt ---


def test_debt_is_signed() -> None:
    nights = [night(back(1), 6), night(back(2), 7), night(back(3), 8)]
    assert sleep_debt(nights, TODAY, 7.0, 7) == {"debt_h": 0.0, "nights": 3}


def test_debt_sums_shortfall() -> None:
    nights = [night(back(n), 6) for n in (1, 2, 3)]
    assert sleep_debt(nights, TODAY, 7.0, 7) == {"debt_h": 3.0, "nights": 3}


def test_debt_negative_when_slept_more() -> None:
    assert sleep_debt([night(back(1), 9)], TODAY, 7.0, 7)["debt_h"] == -2.0


def test_debt_window_7_takes_last_seven_dates() -> None:
    nights = [night(back(n), 6) for n in range(0, 10)]
    assert sleep_debt(nights, TODAY, 7.0, 7) == {"debt_h": 7.0, "nights": 7}


def test_debt_window_14_takes_last_fourteen_dates() -> None:
    nights = [night(back(n), 6) for n in range(0, 20)]
    assert sleep_debt(nights, TODAY, 7.0, 14) == {"debt_h": 14.0, "nights": 14}


def test_debt_window_includes_today_and_excludes_future() -> None:
    nights = [night(TODAY, 6), night(TODAY + timedelta(days=1), 6)]
    assert sleep_debt(nights, TODAY, 7.0, 7) == {"debt_h": 1.0, "nights": 1}


def test_debt_skips_night_without_data() -> None:
    nights = [night(back(1), 6), night(back(2), None), night(back(3), 0)]
    assert sleep_debt(nights, TODAY, 7.0, 7) == {"debt_h": 1.0, "nights": 1}


def test_debt_without_norm_is_none() -> None:
    nights = [night(back(1), 6), night(back(2), 6)]
    assert sleep_debt(nights, TODAY, None, 7) == {"debt_h": None, "nights": 2}


def test_debt_rounded_to_tenths() -> None:
    nights = [{**night(back(1), 7), "sleep_seconds": 24000}]
    assert sleep_debt(nights, TODAY, 7.0, 7)["debt_h"] == 0.3


def test_debt_missing_nap_adds_no_hours() -> None:
    # 3 * (7 - 25139 / 3600) = 0.0508 ч → 0.1; при `or 1` было бы 0.0500 → 0.0
    nights = [{**night(back(n), 7), "sleep_seconds": 25139} for n in (1, 2, 3)]
    assert sleep_debt(nights, TODAY, 7.0, 7)["debt_h"] == 0.1


def test_debt_nap_divides_by_exact_hour() -> None:
    # 20 - 6 - 50223 / 3600 = 0.0492 ч → 0.0; при /3601 было бы 0.0530 → 0.1
    nights = [{**night(back(1), 6), "nap_seconds": 50223}]
    assert sleep_debt(nights, TODAY, 20.0, 7)["debt_h"] == 0.0


# --- дневной сон ---


def test_nap_reduces_debt() -> None:
    nights = [night(back(1), 6, nap=3600), night(back(2), 6), night(back(3), 6)]
    assert sleep_debt(nights, TODAY, 7.0, 7)["debt_h"] == 2.0


def test_nap_none_counts_as_zero() -> None:
    nights = [night(back(n), 6, nap=None) for n in (1, 2, 3)]
    assert sleep_debt(nights, TODAY, 7.0, 7)["debt_h"] == 3.0


def test_nap_does_not_change_norm() -> None:
    plain = [night(back(n), 7) for n in range(1, 21)]
    napping = [night(back(n), 7, nap=7200) for n in range(1, 21)]
    assert sleep_norm(napping, TODAY) == sleep_norm(plain, TODAY)


def test_nap_does_not_hide_short_night(conn: sqlite3.Connection) -> None:
    seven_hour_nights(conn, date(2026, 10, 10), 21)
    put(conn, TODAY, 5)
    conn.execute(
        "UPDATE daily_metrics SET raw_json = ? WHERE date = ?",
        (json.dumps({"sleep": {"dailySleepDTO": {"napTimeSeconds": 7200}}}), TODAY.isoformat()),
    )
    report = sleep_report(conn, TODAY.isoformat())
    assert [s["kind"] for s in report["signals"]] == ["short_night"]


def test_nap_without_night_data_is_ignored() -> None:
    nights = [night(back(1), None, nap=3600), night(back(2), 6)]
    assert sleep_debt(nights, TODAY, 7.0, 7) == {"debt_h": 1.0, "nights": 1}


# --- awake_hours ---


def test_awake_hours_from_wake() -> None:
    assert awake_hours("2026-10-31 07:10:00", datetime(2026, 10, 31, 11, 0)) == 3.8


def test_awake_hours_without_wake_is_none() -> None:
    assert awake_hours(None, datetime(2026, 10, 31, 11, 0)) is None


def test_awake_hours_before_wake_is_zero() -> None:
    assert awake_hours("2026-10-31 07:10:00", datetime(2026, 10, 31, 6, 0)) == 0.0


def test_awake_hours_exact_for_long_span() -> None:
    assert awake_hours("2026-10-01 00:00:00", datetime(2026, 10, 11, 0, 0)) == 240.0


# --- sleep_signals ---


def test_short_night_signal() -> None:
    signals = sleep_signals(report_with(last_night_h=5.9))
    assert signals == [{"kind": "short_night", "value": 1.1, "limit": 1.0}]


def test_short_night_at_limit_fires() -> None:
    assert kinds(report_with(last_night_h=6.0)) == ["short_night"]


def test_slightly_short_night_is_quiet() -> None:
    assert kinds(report_with(last_night_h=6.1)) == []


def test_debt_7_signal() -> None:
    signals = sleep_signals(report_with(debt_7_h=3.0))
    assert signals == [{"kind": "sleep_debt", "value": 3.0, "limit": 3.0}]


def test_debt_14_signal_without_debt_7() -> None:
    signals = sleep_signals(report_with(debt_14_h=5.0))
    assert signals == [{"kind": "sleep_debt", "value": 5.0, "limit": 5.0}]


def test_debt_signal_is_single_when_both_reached() -> None:
    signals = sleep_signals(report_with(debt_7_h=4.0, debt_14_h=6.0))
    assert [(s["kind"], s["value"]) for s in signals] == [("sleep_debt", 4.0)]


def test_gap_just_under_limit_is_quiet() -> None:
    assert kinds(report_with(norm_h=7.0, last_night_h=6.05)) == []


def test_gap_rounded_to_limit_fires() -> None:
    signals = sleep_signals(report_with(norm_h=7.1, last_night_h=6.1))
    assert [(s["kind"], s["value"]) for s in signals] == [("short_night", 1.0)]


def test_short_night_value_rounded_to_hundredths() -> None:
    signals = sleep_signals(report_with(norm_h=7.0, last_night_h=5.994))
    assert [(s["kind"], s["value"]) for s in signals] == [("short_night", 1.01)]


def test_no_last_night_no_short_night() -> None:
    assert kinds(report_with(last_night_h=None)) == []


def test_below_both_thresholds_is_empty() -> None:
    assert sleep_signals(report_with(debt_7_h=2.9, debt_14_h=4.9)) == []


def test_no_norm_no_signals() -> None:
    quiet = report_with(last_night_h=3.0, norm_h=None, debt_7_h=None, debt_14_h=None)
    assert sleep_signals(quiet) == []


# --- sleep_report ---

DAY = "2026-10-31"


def filled(conn: sqlite3.Connection, wake: str = "2026-10-31 07:10:00") -> None:
    seven_hour_nights(conn, date(2026, 10, 7), 24)
    put(conn, date(2026, 10, 31), 5.9, wake)


def test_report_fields_follow_formulas(conn: sqlite3.Connection) -> None:
    filled(conn)
    report = sleep_report(conn, DAY)
    assert report["date"] == DAY
    assert (report["norm_h"], report["norm_nights"]) == (7.0, 25)
    assert report["last_night_h"] == 5.9
    assert (report["debt_7_h"], report["nights_7"]) == (1.1, 7)
    assert (report["debt_14_h"], report["nights_14"]) == (1.1, 14)
    assert report["nap_h"] == 0.0
    assert report["signals"] == [{"kind": "short_night", "value": 1.1, "limit": 1.0}]


def test_report_wake_and_caution(conn: sqlite3.Connection) -> None:
    filled(conn)
    report = sleep_report(conn, DAY)
    assert report["wake_at"] == "2026-10-31 07:10"
    assert report["caution_from"] == "2026-10-31 23:10"


def test_report_caution_crosses_midnight(conn: sqlite3.Connection) -> None:
    filled(conn, wake="2026-10-31 09:30:00")
    assert sleep_report(conn, DAY)["caution_from"] == "2026-11-01 01:30"


def test_report_awake_same_day(conn: sqlite3.Connection) -> None:
    filled(conn)
    assert sleep_report(conn, DAY, datetime(2026, 10, 31, 11, 0))["awake_h"] == 3.8


def test_report_awake_other_day_is_none(conn: sqlite3.Connection) -> None:
    filled(conn)
    assert sleep_report(conn, DAY, datetime(2026, 11, 1, 11, 0))["awake_h"] is None


def test_report_awake_without_now_is_none(conn: sqlite3.Connection) -> None:
    filled(conn)
    assert sleep_report(conn, DAY)["awake_h"] is None


def test_report_day_without_row(conn: sqlite3.Connection) -> None:
    seven_hour_nights(conn, date(2026, 10, 7), 24)
    report = sleep_report(conn, DAY)
    assert report["last_night_h"] is None
    assert report["wake_at"] is None
    assert report["caution_from"] is None
    assert report["norm_h"] == 7.0


def test_report_import_row_without_daily_dto(conn: sqlite3.Connection) -> None:
    filled(conn)
    put(conn, date(2026, 10, 31), 5.9)
    report = sleep_report(conn, DAY)
    assert report["wake_at"] is None
    assert report["last_night_h"] == 5.9


def test_report_nap_hours(conn: sqlite3.Connection) -> None:
    filled(conn)
    conn.execute(
        "UPDATE daily_metrics SET raw_json = ? WHERE date = ?",
        (json.dumps({"sleep": {"dailySleepDTO": {"napTimeSeconds": 3600}}}), DAY),
    )
    assert sleep_report(conn, DAY)["nap_h"] == 1.0


def nap_report(conn: sqlite3.Connection, nap_seconds: int) -> dict[str, Any]:
    filled(conn)
    conn.execute(
        "UPDATE daily_metrics SET raw_json = ? WHERE date = ?",
        (json.dumps({"sleep": {"dailySleepDTO": {"napTimeSeconds": nap_seconds}}}), DAY),
    )
    return sleep_report(conn, DAY)


def test_report_nap_hours_rounded_to_tenths(conn: sqlite3.Connection) -> None:
    assert nap_report(conn, 4620)["nap_h"] == 1.3


def test_report_nap_hours_keeps_fraction(conn: sqlite3.Connection) -> None:
    assert nap_report(conn, 5400)["nap_h"] == 1.5


def test_report_nap_hours_divides_by_exact_hour(conn: sqlite3.Connection) -> None:
    # 46628 / 3600 = 12.9522 ч → 13.0; при /3601 было бы 12.9 (12.9486)
    assert nap_report(conn, 46628)["nap_h"] == 13.0


def test_report_last_night_rounded_to_hundredths(conn: sqlite3.Connection) -> None:
    seven_hour_nights(conn, date(2026, 10, 7), 24)
    put(conn, date(2026, 10, 31), 6.1234)
    assert sleep_report(conn, DAY)["last_night_h"] == 6.12


def test_report_norm_uses_night_on_oldest_window_day(conn: sqlite3.Connection) -> None:
    seven_hour_nights(conn, date(2026, 10, 13), 19)
    put(conn, date(2026, 10, 31) - timedelta(days=89), 7)
    report = sleep_report(conn, DAY)
    assert (report["norm_h"], report["norm_nights"]) == (7.0, 20)


def test_report_few_nights_no_norm_no_debt(conn: sqlite3.Connection) -> None:
    seven_hour_nights(conn, date(2026, 10, 25), 5)
    report = sleep_report(conn, DAY)
    assert report["norm_h"] is None
    assert report["norm_nights"] == 5
    assert report["debt_7_h"] is None
    assert report["debt_14_h"] is None
    assert report["signals"] == []


def test_report_has_no_raw_json(conn: sqlite3.Connection) -> None:
    filled(conn)
    assert "SECRET" not in json.dumps(sleep_report(conn, DAY))
