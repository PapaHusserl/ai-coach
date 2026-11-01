"""Сигнал «возможно, заболеваешь»: коридор, флаги дня, серия, сигналы, отчёт. Синтетика."""

import json
import sqlite3
from datetime import date, timedelta
from statistics import pstdev
from typing import Any

from ai_coach.load.illness import (
    SHOWN_DAYS,
    STREAK_DAYS,
    corridor,
    day_flags,
    illness_report,
    illness_signals,
    out_streak,
)
from ai_coach.store.garmin_data import upsert_daily_metrics

TODAY = date(2026, 11, 2)


def back(days: int) -> date:
    return TODAY - timedelta(days=days)


def row(days: int, rhr: float | None, hrv: float | None = None) -> dict[str, Any]:
    return {"date": back(days).isoformat(), "rhr": rhr, "hrv": hrv}


def fifty(first: int, last: int) -> list[dict[str, Any]]:
    """Дни от first до last дней назад (включительно) с пульсом 50."""
    return [row(days, 50) for days in range(first, last - 1, -1)]


def put(conn: sqlite3.Connection, days: int, rhr: float | None, hrv: float | None) -> None:
    sleep = {} if rhr is None else {"restingHeartRate": rhr}
    upsert_daily_metrics(
        conn,
        {
            "date": back(days).isoformat(),
            "hrv_last_night": hrv,
            "raw_json": {"secret": "SECRET", "sleep": sleep},
        },
    )


def base_28(conn: sqlite3.Connection) -> None:
    """28 дней перед TODAY: пульс 50, HRV 60; в одном дне 60 и 70 - у коридоров есть разброс."""
    for days in range(28, 0, -1):
        outlier = days == 20
        put(conn, days, 60 if outlier else 50, 70 if outlier else 60)


def out_day(conn: sqlite3.Connection, days: int) -> None:
    put(conn, days, 90, 10)


FLAGS_OUT = {"rhr_high": True, "hrv_low": True, "out": True}
FLAGS_NONE = {"rhr_high": None, "hrv_low": None, "out": None}


# --- corridor ---


def test_corridor_center_is_mean_of_previous_week_and_swc_from_base() -> None:
    rows = [row(days, 60 if days == 20 else 50) for days in range(28, 0, -1)]
    found = corridor(rows, TODAY, "rhr")
    assert found is not None
    assert found["mean7"] == 50
    assert found["swc"] == 0.5 * pstdev([50] * 27 + [60])


def test_corridor_none_when_base_has_13_days() -> None:
    assert corridor(fifty(13, 1), TODAY, "rhr") is None


def test_corridor_exists_with_14_days_in_base() -> None:
    assert corridor(fifty(14, 1), TODAY, "rhr") is not None


def test_corridor_none_when_center_has_3_days() -> None:
    rows = fifty(28, 8) + fifty(3, 1)
    assert corridor(rows, TODAY, "rhr") is None


def test_corridor_exists_with_4_days_in_center() -> None:
    rows = fifty(28, 8) + fifty(4, 1)
    assert corridor(rows, TODAY, "rhr") is not None


def test_corridor_ignores_today_in_center_and_base() -> None:
    rows = fifty(28, 1) + [row(0, 90)]
    found = corridor(rows, TODAY, "rhr")
    assert found == {"mean7": 50, "swc": 0}


def test_corridor_center_takes_only_seven_previous_days() -> None:
    rows = fifty(28, 8) + [row(7, 80)] + fifty(6, 1)
    found = corridor(rows, TODAY, "rhr")
    assert found is not None
    assert found["mean7"] == (80 + 6 * 50) / 7


def test_corridor_skips_none_values() -> None:
    rows = fifty(14, 2) + [row(1, None)]
    assert corridor(rows, TODAY, "rhr") is None


def test_corridor_reads_the_requested_key() -> None:
    rows = [row(days, 50, 70) for days in range(28, 0, -1)]
    found = corridor(rows, TODAY, "hrv")
    assert found is not None
    assert found["mean7"] == 70


# --- day_flags ---


def test_rhr_equal_to_edge_is_not_high() -> None:
    flags = day_flags({"rhr": 52, "hrv": 60}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags["rhr_high"] is False


def test_rhr_above_edge_is_high() -> None:
    flags = day_flags({"rhr": 53, "hrv": 60}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags["rhr_high"] is True


def test_rhr_is_compared_with_edge_rounded_to_one_digit() -> None:
    flags = day_flags({"rhr": 52, "hrv": 60}, {"mean7": 50, "swc": 1.96}, {"mean7": 60, "swc": 5})
    assert flags["rhr_high"] is False


def test_hrv_equal_to_edge_is_not_low() -> None:
    flags = day_flags({"rhr": 50, "hrv": 55}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags["hrv_low"] is False


def test_hrv_below_edge_is_low() -> None:
    flags = day_flags({"rhr": 50, "hrv": 54}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags["hrv_low"] is True


def test_out_when_both_flags_true() -> None:
    flags = day_flags({"rhr": 60, "hrv": 40}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags == FLAGS_OUT


def test_not_out_when_only_rhr_high() -> None:
    flags = day_flags({"rhr": 60, "hrv": 60}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags == {"rhr_high": True, "hrv_low": False, "out": False}


def test_not_out_when_only_hrv_low() -> None:
    flags = day_flags({"rhr": 50, "hrv": 40}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags == {"rhr_high": False, "hrv_low": True, "out": False}


def test_flags_none_when_value_missing() -> None:
    flags = day_flags({"rhr": None, "hrv": 40}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags == FLAGS_NONE


def test_flags_none_when_hrv_missing() -> None:
    flags = day_flags({"rhr": 60, "hrv": None}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags == FLAGS_NONE


def test_flags_none_when_corridor_missing() -> None:
    assert day_flags({"rhr": 60, "hrv": 40}, None, {"mean7": 60, "swc": 5}) == FLAGS_NONE
    assert day_flags({"rhr": 60, "hrv": 40}, {"mean7": 50, "swc": 2}, None) == FLAGS_NONE


# --- out_streak ---


def by_date(*outs: bool | None) -> dict[str, dict[str, bool | None]]:
    """Флаги по датам; последний элемент - TODAY."""
    result: dict[str, dict[str, bool | None]] = {}
    for index, out in enumerate(outs):
        result[back(len(outs) - 1 - index).isoformat()] = {"out": out}
    return result


def test_streak_counts_trailing_out_days() -> None:
    assert out_streak(by_date(False, True, True), TODAY.isoformat()) == 2


def test_streak_stops_at_a_day_in_corridor() -> None:
    assert out_streak(by_date(True, False, True), TODAY.isoformat()) == 1


def test_streak_zero_when_today_unknown() -> None:
    assert out_streak(by_date(True, True, None), TODAY.isoformat()) == 0


def test_streak_zero_when_today_in_corridor() -> None:
    assert out_streak(by_date(True, True, False), TODAY.isoformat()) == 0


def test_streak_stops_at_unknown_yesterday() -> None:
    assert out_streak(by_date(True, None, True), TODAY.isoformat()) == 1


def test_streak_stops_at_missing_date() -> None:
    assert out_streak({TODAY.isoformat(): {"out": True}}, TODAY.isoformat()) == 1


# --- illness_signals ---


def test_signal_at_streak_days() -> None:
    assert illness_signals({"streak": 2}) == [
        {"kind": "illness_risk", "value": 2, "limit": STREAK_DAYS}
    ]


def test_no_signal_for_one_day() -> None:
    assert illness_signals({"streak": 1}) == []


def test_no_signal_for_zero_days() -> None:
    assert illness_signals({"streak": 0}) == []


def test_one_signal_with_long_streak() -> None:
    signals = illness_signals({"streak": 5})
    assert len(signals) == 1
    assert signals[0]["value"] == 5


# --- illness_report ---


def report(conn: sqlite3.Connection, day: date = TODAY, **kwargs: Any) -> dict[str, Any]:
    return illness_report(conn, day.isoformat(), **kwargs)


def test_report_fields_follow_formulas(conn: sqlite3.Connection) -> None:
    base_28(conn)
    put(conn, 0, 58, 40)
    found = report(conn)
    rhr_swc = 0.5 * pstdev([50] * 27 + [60])
    hrv_swc = 0.5 * pstdev([60] * 27 + [70])
    assert found["date"] == TODAY.isoformat()
    assert found["rhr"] == 58
    assert found["hrv"] == 40
    assert found["rhr_mean7"] == 50.0
    assert found["hrv_mean7"] == 60.0
    assert found["rhr_high_from"] == round(50 + rhr_swc, 1)
    assert found["hrv_low_from"] == round(60 - hrv_swc, 1)
    assert found["rhr_high"] is True
    assert found["hrv_low"] is True
    assert found["out_today"] is True


def test_report_days_are_shown_days_ascending(conn: sqlite3.Connection) -> None:
    base_28(conn)
    put(conn, 0, 58, 40)
    days = report(conn)["days"]
    assert [d["date"] for d in days] == [back(n).isoformat() for n in range(SHOWN_DAYS - 1, -1, -1)]
    assert days[-1] == {"date": TODAY.isoformat(), "rhr": 58, "hrv": 40, "out": True}
    assert days[0]["out"] is False


def test_report_two_out_days_give_streak_and_signal(conn: sqlite3.Connection) -> None:
    base_28(conn)
    out_day(conn, 1)
    out_day(conn, 0)
    found = report(conn)
    assert found["streak"] == 2
    assert found["signals"] == [{"kind": "illness_risk", "value": 2, "limit": STREAK_DAYS}]


def test_report_one_out_day_is_no_signal(conn: sqlite3.Connection) -> None:
    base_28(conn)
    out_day(conn, 0)
    found = report(conn)
    assert found["streak"] == 1
    assert found["signals"] == []


def test_report_streak_is_capped_by_shown_days(conn: sqlite3.Connection) -> None:
    base_28(conn)
    for days in range(9, -1, -1):
        put(conn, days, 100 + 10 * (9 - days), 50 - 5 * (9 - days))
    assert report(conn)["streak"] == SHOWN_DAYS


def test_report_day_in_days_matches_report_on_that_day(conn: sqlite3.Connection) -> None:
    base_28(conn)
    for days in range(6, -1, -1):
        out_day(conn, days)
    shown = {d["date"]: d["out"] for d in report(conn)["days"]}
    earlier = report(conn, back(6))
    assert shown[back(6).isoformat()] is earlier["out_today"] is True
    assert shown[back(3).isoformat()] == report(conn, back(3))["out_today"]


def test_report_reads_import_row_resting_heart_rate(conn: sqlite3.Connection) -> None:
    base_28(conn)
    upsert_daily_metrics(
        conn,
        {
            "date": TODAY.isoformat(),
            "hrv_last_night": 60,
            "raw_json": {
                "hrv": {"metrics": [{"type": "HR", "value": 52}, {"type": "HRV", "value": 60}]}
            },
        },
    )
    assert report(conn)["rhr"] == 52


def test_report_day_without_row_has_no_values(conn: sqlite3.Connection) -> None:
    base_28(conn)
    out_day(conn, 1)
    found = report(conn)
    assert found["rhr"] is None
    assert found["hrv"] is None
    assert found["out_today"] is None
    assert found["streak"] == 0
    assert found["signals"] == []


def test_report_without_data_has_no_corridors(conn: sqlite3.Connection) -> None:
    found = report(conn)
    assert found["rhr_mean7"] is None
    assert found["rhr_high_from"] is None
    assert found["hrv_mean7"] is None
    assert found["hrv_low_from"] is None
    assert found["baseline_days"] == 0
    assert len(found["days"]) == SHOWN_DAYS


def test_report_baseline_days_count_days_with_both_values(conn: sqlite3.Connection) -> None:
    base_28(conn)
    for days in range(10, 0, -1):
        put(conn, days, 50, None)
    assert report(conn)["baseline_days"] == 18


def test_report_baseline_days_exclude_today(conn: sqlite3.Connection) -> None:
    base_28(conn)
    put(conn, 0, 58, 40)
    assert report(conn)["baseline_days"] == 28


def test_report_baseline_days_ignore_older_days(conn: sqlite3.Connection) -> None:
    base_28(conn)
    put(conn, 29, 50, 60)
    assert report(conn)["baseline_days"] == 28


def test_report_trained_yesterday_in_confounders(conn: sqlite3.Connection) -> None:
    found = report(conn, tss={back(1).isoformat(): 30})
    assert "trained_yesterday" in found["confounders"]
    assert found["tss_yesterday"] == 30


def test_report_without_tss_has_no_tss_yesterday(conn: sqlite3.Connection) -> None:
    found = report(conn, tss={})
    assert found["tss_yesterday"] is None
    assert "trained_yesterday" not in found["confounders"]


def test_report_zero_tss_yesterday_is_not_confounder(conn: sqlite3.Connection) -> None:
    found = report(conn, tss={back(1).isoformat(): 0.0})
    assert found["tss_yesterday"] == 0.0
    assert found["confounders"] == []


def test_report_tss_of_other_day_is_ignored(conn: sqlite3.Connection) -> None:
    found = report(conn, tss={back(2).isoformat(): 30})
    assert found["tss_yesterday"] is None


def test_report_short_night_in_confounders(conn: sqlite3.Connection) -> None:
    sleep = {"signals": [{"kind": "short_night", "value": 1.5, "limit": 1.0}]}
    found = report(conn, sleep=sleep)
    assert found["confounders"] == ["short_night"]
    assert found["sleep_debt"] is False


def test_report_sleep_debt_flag(conn: sqlite3.Connection) -> None:
    sleep = {"signals": [{"kind": "sleep_debt", "value": 6, "limit": 5}]}
    found = report(conn, sleep=sleep)
    assert found["sleep_debt"] is True
    assert found["confounders"] == []


def test_report_both_confounders(conn: sqlite3.Connection) -> None:
    sleep = {"signals": [{"kind": "short_night", "value": 1.5, "limit": 1.0}]}
    found = report(conn, tss={back(1).isoformat(): 30}, sleep=sleep)
    assert found["confounders"] == ["short_night", "trained_yesterday"]


def test_report_without_sleep_has_no_confounders(conn: sqlite3.Connection) -> None:
    found = report(conn)
    assert found["confounders"] == []
    assert found["sleep_debt"] is False


def test_report_has_no_raw_json(conn: sqlite3.Connection) -> None:
    base_28(conn)
    put(conn, 0, 58, 40)
    assert "SECRET" not in json.dumps(report(conn))
