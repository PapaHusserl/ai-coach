"""Сигнал «возможно, заболеваешь»: коридор, флаги дня, серия, сигналы, отчёт. Синтетика."""

import json
import sqlite3
from datetime import date, timedelta
from statistics import pstdev
from typing import Any

import pytest
from workload_fakes import coach_event

from ai_coach.load.episode import REST_DAYS, RETURN_DAYS
from ai_coach.load.illness import (
    SHOWN_DAYS,
    STREAK_DAYS,
    SWC_K,
    corridor,
    day_flags,
    illness_report,
    illness_signals,
    out_streak,
)
from ai_coach.store.agenda import add_event
from ai_coach.store.forms import add_form, add_form_entry, get_form
from ai_coach.store.garmin_data import upsert_daily_metrics
from ai_coach.store.journal import add_wellbeing

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
    assert found["swc"] == SWC_K * pstdev([50] * 27 + [60])


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


def test_out_when_only_rhr_high() -> None:
    flags = day_flags({"rhr": 60, "hrv": 60}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags == {"rhr_high": True, "hrv_low": False, "out": True}


def test_out_when_only_hrv_low() -> None:
    flags = day_flags({"rhr": 50, "hrv": 40}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags == {"rhr_high": False, "hrv_low": True, "out": True}


def test_not_out_when_both_in_corridor() -> None:
    flags = day_flags({"rhr": 50, "hrv": 60}, {"mean7": 50, "swc": 2}, {"mean7": 60, "swc": 5})
    assert flags == {"rhr_high": False, "hrv_low": False, "out": False}


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


def test_first_day_gives_one_weak_signal() -> None:
    assert illness_signals({"streak": 1}) == [
        {"kind": "corridor_out", "value": 1, "limit": STREAK_DAYS}
    ]


def test_no_weak_signal_with_streak_signal() -> None:
    kinds = [s["kind"] for s in illness_signals({"streak": STREAK_DAYS})]
    assert kinds == ["illness_risk"]


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
    rhr_swc = SWC_K * pstdev([50] * 27 + [60])
    hrv_swc = SWC_K * pstdev([60] * 27 + [70])
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


def test_report_one_out_day_is_weak_signal_only(conn: sqlite3.Connection) -> None:
    base_28(conn)
    out_day(conn, 0)
    found = report(conn)
    assert found["streak"] == 1
    assert found["signals"] == [{"kind": "corridor_out", "value": 1, "limit": STREAK_DAYS}]


def test_report_only_rhr_high_day_is_out(conn: sqlite3.Connection) -> None:
    base_28(conn)
    put(conn, 0, 90, 60)
    found = report(conn)
    assert (found["rhr_high"], found["hrv_low"], found["out_today"]) == (True, False, True)
    assert found["streak"] == 1


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


# --- episode и сигналы фаз (Н33, партия 2б) ---

EPISODE_KEYS = {
    "phase",
    "severe",
    "sick_first",
    "sick_last",
    "clean_days",
    "rest_day",
    "rest_step",
    "return_day",
    "until",
    "by_cap",
    "not_clean",
    "covid",
    "series_day",
}


def note(conn: sqlite3.Connection, days: int, text: str = "") -> None:
    """Запись самочувствия за день back(days)."""
    add_wellbeing(
        conn,
        {
            "date": back(days).isoformat(),
            "logged_at": f"{back(days).isoformat()} 09:00:00",
            "score": 3,
            "text": text,
        },
    )


def normal_nights(conn: sqlite3.Connection) -> None:
    """28 ночей базы и сегодняшняя ночь - в коридоре."""
    base_28(conn)
    put(conn, 0, 50, 60)


def episode(conn: sqlite3.Connection) -> dict[str, Any]:
    return report(conn)["episode"]


def signal_of(conn: sqlite3.Connection, kind: str) -> dict[str, Any] | None:
    found = [s for s in report(conn)["signals"] if s["kind"] == kind]
    return found[0] if found else None


def test_episode_without_illness_has_all_keys_and_no_phase(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    found = episode(conn)
    assert set(found) == EPISODE_KEYS
    assert found["phase"] is None
    assert found["not_clean"] == []


def test_episode_rest_day_one_without_record(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 1, "озноб")
    assert episode(conn) == {
        "phase": "rest",
        "severe": True,
        "sick_first": back(1).isoformat(),
        "sick_last": back(1).isoformat(),
        "clean_days": 0,
        "rest_day": 1,
        "rest_step": 1,
        "return_day": None,
        "until": None,
        "by_cap": False,
        "not_clean": ["no_record"],
        "covid": False,
        "series_day": 2,
    }


def test_illness_rest_signal_carries_why_of_today(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 1, "озноб")
    assert signal_of(conn, "illness_rest") == {
        "kind": "illness_rest",
        "value": 1,
        "limit": REST_DAYS,
        "why": ["no_record"],
        "covid": False,
    }


def test_illness_rest_why_is_empty_for_counted_day(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 1, "озноб")
    note(conn, 0)
    assert signal_of(conn, "illness_rest") == {
        "kind": "illness_rest",
        "value": 1,
        "limit": REST_DAYS,
        "why": [],
        "covid": False,
    }


def test_illness_rest_value_is_step_not_count_of_clean_days(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 2, "озноб")
    note(conn, 1)
    note(conn, 0)
    assert signal_of(conn, "illness_rest") == {
        "kind": "illness_rest",
        "value": 2,
        "limit": REST_DAYS,
        "why": [],
        "covid": False,
    }


def test_illness_rest_why_names_corridor(conn: sqlite3.Connection) -> None:
    base_28(conn)
    out_day(conn, 0)
    note(conn, 1, "озноб")
    note(conn, 0)
    found = signal_of(conn, "illness_rest")
    assert found is not None
    assert found["why"] == ["corridor"]


def test_illness_rest_why_names_night_without_data(conn: sqlite3.Connection) -> None:
    base_28(conn)
    note(conn, 1, "озноб")
    note(conn, 0)
    found = signal_of(conn, "illness_rest")
    assert found is not None
    assert found["why"] == ["no_night"]


def test_illness_rest_why_keeps_order_of_codes(conn: sqlite3.Connection) -> None:
    base_28(conn)
    out_day(conn, 0)
    note(conn, 1, "озноб")
    found = signal_of(conn, "illness_rest")
    assert found is not None
    assert found["why"] == ["no_record", "corridor"]


def test_illness_return_signal_has_no_why(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 3, "озноб")
    note(conn, 2)
    note(conn, 1)
    assert signal_of(conn, "illness_return") == {
        "kind": "illness_return",
        "value": 1,
        "limit": RETURN_DAYS,
        "covid": False,
    }


def test_episode_return_day_and_until(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 3, "озноб")
    note(conn, 2)
    note(conn, 1)
    found = episode(conn)
    assert found["phase"] == "return"
    assert found["return_day"] == 1
    assert found["until"] == (TODAY + timedelta(days=RETURN_DAYS - 1)).isoformat()


def test_rest_phase_gives_no_return_signal(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 1, "озноб")
    assert signal_of(conn, "illness_return") is None


def test_return_phase_gives_no_rest_signal(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 3, "озноб")
    note(conn, 2)
    note(conn, 1)
    assert signal_of(conn, "illness_rest") is None


def test_ill_phase_gives_no_phase_signals(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 0, "озноб")
    assert episode(conn)["phase"] == "ill"
    kinds = [s["kind"] for s in report(conn)["signals"]]
    assert "illness_rest" not in kinds
    assert "illness_return" not in kinds


def test_light_series_gives_no_phase_signals(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 1, "кашель")
    assert episode(conn)["phase"] is None
    assert [s["kind"] for s in report(conn)["signals"]] == []


def covid_episode(phase: str, first: int, last: int, **fields: Any) -> dict[str, Any]:
    """Эпизод по ключам episode_state; first и last - дни серии в днях назад от 2026-11-10."""
    base = date(2026, 11, 10)
    return {
        "phase": phase,
        "severe": phase != "light",
        "sick_first": (base - timedelta(days=first)).isoformat(),
        "sick_last": (base - timedelta(days=last)).isoformat(),
        "rest_day": None,
        "rest_step": None,
        "return_day": None,
        "not_clean": [],
        "covid": True,
        **fields,
    }


def phase_signal(episode: dict[str, Any]) -> list[dict[str, Any]]:
    return illness_signals({"streak": 0, "episode": episode})


def test_covid_rest_short_series_counts_series_days() -> None:
    episode = covid_episode("rest", 2, 1, series_day=3, rest_day=2, rest_step=2)
    assert phase_signal(episode) == [
        {
            "kind": "illness_rest",
            "value": 3,
            "limit": 5,
            "why": [],
            "covid": True,
            "count": "series",
        }
    ]


def test_covid_rest_short_series_why_is_empty_even_with_not_clean() -> None:
    episode = covid_episode(
        "rest", 1, 0, series_day=2, rest_day=1, rest_step=1, not_clean=["no_record"]
    )
    assert phase_signal(episode)[0]["why"] == []


def test_covid_rest_long_series_keeps_old_shape_plus_covid() -> None:
    episode = covid_episode(
        "rest", 3, 0, series_day=4, rest_day=3, rest_step=1, not_clean=["no_record"]
    )
    assert phase_signal(episode) == [
        {
            "kind": "illness_rest",
            "value": 1,
            "limit": REST_DAYS,
            "why": ["no_record"],
            "covid": True,
        }
    ]


def test_covid_rest_length_three_is_long() -> None:
    episode = covid_episode("rest", 3, 1, series_day=4, rest_day=2, rest_step=2)
    signal = phase_signal(episode)[0]
    assert (signal["value"], signal["limit"], "count" in signal) == (2, REST_DAYS, False)


def test_covid_return_signal() -> None:
    episode = covid_episode("return", 6, 0, series_day=7, return_day=1)
    assert phase_signal(episode) == [
        {"kind": "illness_return", "value": 1, "limit": RETURN_DAYS, "covid": True}
    ]


def test_covid_light_signal() -> None:
    episode = covid_episode("light", 1, 0, series_day=2)
    assert phase_signal(episode) == [
        {"kind": "illness_light", "value": 2, "limit": 5, "covid": True}
    ]


def test_signals_without_covid_have_covid_false() -> None:
    rest = covid_episode("rest", 2, 1, series_day=3, rest_day=2, rest_step=2, covid=False)
    ret = covid_episode("return", 6, 0, series_day=7, return_day=1, covid=False)
    assert [s["covid"] for s in phase_signal(rest) + phase_signal(ret)] == [False, False]
    assert "count" not in phase_signal(rest)[0]


def test_other_signals_keep_their_keys_next_to_phase_signal(conn: sqlite3.Connection) -> None:
    base_28(conn)
    out_day(conn, 1)
    out_day(conn, 0)
    note(conn, 2, "озноб")
    note(conn, 1)
    assert signal_of(conn, "illness_risk") == {
        "kind": "illness_risk",
        "value": 2,
        "limit": STREAK_DAYS,
    }
    assert signal_of(conn, "illness_rest") is not None


def test_phase_signal_goes_after_illness_risk(conn: sqlite3.Connection) -> None:
    base_28(conn)
    out_day(conn, 1)
    out_day(conn, 0)
    note(conn, 2, "озноб")
    kinds = [s["kind"] for s in report(conn)["signals"]]
    assert kinds == ["illness_risk", "illness_rest"]


def test_phase_signal_goes_after_corridor_out(conn: sqlite3.Connection) -> None:
    base_28(conn)
    put(conn, 1, 50, 60)
    out_day(conn, 0)
    note(conn, 2, "озноб")
    kinds = [s["kind"] for s in report(conn)["signals"]]
    assert kinds == ["corridor_out", "illness_rest"]


def test_episode_reads_corridor_flags_over_whole_episode_window(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 12, "озноб")
    note(conn, 11)
    note(conn, 10)
    note(conn, 2, "кашель")
    found = episode(conn)
    assert found["phase"] is None
    assert found["severe"] is False
    assert found["sick_first"] == back(2).isoformat()


def put_form(
    conn: sqlite3.Connection, days: int, answers: dict[str, Any], text: str | None = None
) -> None:
    fields = [
        {"key": "temperature", "type": "number", "label": "Температура", "unit": "°C"},
        {"key": "nose", "type": "yesno", "label": "Насморк"},
    ]
    if get_form(conn, "sick") is None:
        add_form(
            conn,
            {
                "name": "sick",
                "title": "Болезнь",
                "fields_json": json.dumps(fields, ensure_ascii=False),
                "created_at": f"{back(20).isoformat()} 07:00:00",
            },
        )
    add_form_entry(
        conn,
        {
            "date": back(days).isoformat(),
            "time": "09:00:00",
            "event_id": add_event(conn, coach_event(survey="form:sick")),
            "form": "sick",
            "values_json": json.dumps(answers),
            "text": text,
        },
    )


def test_episode_takes_fever_from_form_answer_without_journal_record(
    conn: sqlite3.Connection,
) -> None:
    normal_nights(conn)
    put_form(conn, 1, {"temperature": 38.0})
    found = episode(conn)
    assert found["phase"] == "rest"
    assert found["severe"] is True
    assert found["sick_last"] == back(1).isoformat()


def test_episode_takes_own_text_of_form_answer_without_wellbeing(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    put_form(conn, 1, {}, text="озноб")
    assert episode(conn)["phase"] == "rest"


def test_episode_form_answer_is_not_a_journal_record(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 2, "озноб")
    put_form(conn, 1, {"nose": False})
    put_form(conn, 0, {"nose": False})
    assert episode(conn)["not_clean"] == ["no_record"]


def test_report_streak_and_days_stay_within_shown_days_with_episode(
    conn: sqlite3.Connection,
) -> None:
    base_28(conn)
    for days in range(12, -1, -1):
        put(conn, days, 100 + 10 * (12 - days), 50 - 3 * (12 - days))
    found = report(conn)
    assert found["streak"] == SHOWN_DAYS
    assert len(found["days"]) == SHOWN_DAYS


def test_report_mean7_is_rounded_to_one_digit(conn: sqlite3.Connection) -> None:
    base_28(conn)
    put(conn, 1, 52, 61)
    put(conn, 0, 50, 60)
    found = report(conn)
    assert found["rhr_mean7"] == 50.3
    assert found["hrv_mean7"] == 60.1


def test_episode_window_reaches_twenty_days_back(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 20, "озноб")
    found = episode(conn)
    assert found["severe"] is True
    assert found["sick_first"] == back(20).isoformat()


def test_form_answer_after_answer_of_missing_form_is_still_read(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    put_form(conn, 1, {}, text="озноб")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    add_form_entry(
        conn,
        {
            "date": back(2).isoformat(),
            "time": "09:00:00",
            "event_id": add_event(conn, coach_event(survey="form:ghost")),
            "form": "ghost",
            "values_json": json.dumps({}),
            "text": None,
        },
    )
    assert episode(conn)["phase"] == "rest"


# --- серия статуса HRV и метрики ночи (Н33, партия 3) ---

VITALS_BASE: dict[str, Any] = {"skin": 0.2, "resp": 15.0, "spo2": 96}


def night(
    conn: sqlite3.Connection,
    days: int,
    *,
    status: str | None = None,
    skin: float | None = None,
    resp: float | None = None,
    spo2: float | None = None,
    rhr: float = 50,
    hrv: float = 60,
) -> None:
    """Ночь back(days): пульс и HRV (по умолчанию в коридоре), статус и метрики ночи."""
    dto: dict[str, Any] = {}
    if resp is not None:
        dto["averageRespirationValue"] = resp
    if spo2 is not None:
        dto["averageSpO2Value"] = spo2
    sleep: dict[str, Any] = {"restingHeartRate": rhr, "dailySleepDTO": dto}
    if skin is not None:
        sleep["avgSkinTempDeviationC"] = skin
    upsert_daily_metrics(
        conn,
        {
            "date": back(days).isoformat(),
            "hrv_last_night": hrv,
            "hrv_status": status,
            "raw_json": {"sleep": sleep},
        },
    )


def nights(
    conn: sqlite3.Connection,
    statuses: dict[int, str | None] | None = None,
    today: dict[str, Any] | None = None,
) -> None:
    """28 ночей базы с постоянными метриками (коридор без разброса) и сегодняшняя ночь."""
    for days in range(28, 0, -1):
        night(conn, days, status=(statuses or {}).get(days), **VITALS_BASE)
    night(conn, 0, status=(statuses or {}).get(0), **(VITALS_BASE if today is None else today))


def streak_signal(
    conn: sqlite3.Connection, statuses: dict[int, str | None]
) -> dict[str, Any] | None:
    nights(conn, statuses)
    return signal_of(conn, "hrv_streak")


def test_hrv_streak_one_bad_day_gives_no_signal(conn: sqlite3.Connection) -> None:
    assert streak_signal(conn, {0: "UNBALANCED"}) is None


def test_hrv_streak_two_bad_days_give_signal(conn: sqlite3.Connection) -> None:
    assert streak_signal(conn, {0: "UNBALANCED", 1: "UNBALANCED"}) == {
        "kind": "hrv_streak",
        "value": 2,
        "limit": 2,
    }


def test_hrv_streak_counts_days_in_row(conn: sqlite3.Connection) -> None:
    found = streak_signal(conn, {0: "LOW", 1: "BELOW", 2: "UNBALANCED"})
    assert found is not None
    assert found["value"] == 3


def test_hrv_streak_status_case_does_not_matter(conn: sqlite3.Connection) -> None:
    assert streak_signal(conn, {0: "unbalanced", 1: "Low"}) is not None


@pytest.mark.parametrize("middle", [None, "BALANCED", "POOR", "IN_RANGE"])
def test_hrv_streak_broken_by_day_without_bad_status(
    conn: sqlite3.Connection, middle: str | None
) -> None:
    assert streak_signal(conn, {0: "UNBALANCED", 1: middle, 2: "UNBALANCED"}) is None


def test_hrv_streak_ends_at_today(conn: sqlite3.Connection) -> None:
    assert streak_signal(conn, {0: "BALANCED", 1: "UNBALANCED", 2: "UNBALANCED"}) is None


def rest_day_two(conn: sqlite3.Connection, **today: Any) -> dict[str, Any]:
    """Тяжёлый день два дня назад, запись на сегодня, ночь сегодня: метрики базы с поправкой
    today (None - метрики нет); сегодня день покоя 2; возвращает episode."""
    nights(conn, today={**VITALS_BASE, **today})
    note(conn, 2, "озноб")
    note(conn, 0)
    return episode(conn)


def test_clean_day_with_normal_vitals_has_no_reasons(conn: sqlite3.Connection) -> None:
    assert rest_day_two(conn)["not_clean"] == []


@pytest.mark.parametrize(
    ("code", "today"),
    [
        ("skin_temp", {"skin": 0.3}),
        ("respiration", {"resp": 15.1}),
        ("spo2", {"spo2": 91}),
    ],
)
def test_one_vital_out_makes_day_not_clean_with_its_code(
    conn: sqlite3.Connection, code: str, today: dict[str, Any]
) -> None:
    found = rest_day_two(conn, **today)
    assert found["not_clean"] == [code]
    assert found["clean_days"] == 0


@pytest.mark.parametrize(
    "today",
    [
        {"skin": 0.2},
        {"skin": -0.5},
        {"resp": 15.0},
        {"resp": 12.0},
        {"spo2": 92},
        {"spo2": 99},
    ],
    ids=["skin_edge", "skin_below", "resp_edge", "resp_below", "spo2_92", "spo2_high"],
)
def test_vital_on_edge_or_on_good_side_is_clean(
    conn: sqlite3.Connection, today: dict[str, Any]
) -> None:
    assert rest_day_two(conn, **today)["not_clean"] == []


def test_spo2_is_checked_without_corridor(conn: sqlite3.Connection) -> None:
    for days in range(28, 0, -1):
        night(conn, days, skin=0.2, resp=15.0)
    night(conn, 0, skin=0.2, resp=15.0, spo2=91)
    note(conn, 2, "озноб")
    note(conn, 0)
    assert episode(conn)["not_clean"] == ["spo2"]


@pytest.mark.parametrize("missing", ["skin", "resp", "spo2"])
def test_night_without_one_vital_is_clean(conn: sqlite3.Connection, missing: str) -> None:
    assert rest_day_two(conn, **{missing: None})["not_clean"] == []


def test_night_without_three_vitals_but_with_pulse_and_hrv_is_clean(
    conn: sqlite3.Connection,
) -> None:
    found = rest_day_two(conn, skin=None, resp=None, spo2=None)
    assert found["not_clean"] == []
    assert found["clean_days"] == 1


def test_vital_without_corridor_is_not_checked(conn: sqlite3.Connection) -> None:
    for days in range(28, 0, -1):
        night(conn, days, resp=15.0, spo2=96)
    night(conn, 0, skin=9.9, resp=15.0, spo2=96)
    note(conn, 2, "озноб")
    note(conn, 0)
    assert episode(conn)["not_clean"] == []


def test_vital_out_with_pulse_out_names_both_codes(conn: sqlite3.Connection) -> None:
    nights(conn, today={**VITALS_BASE, "spo2": 90, "rhr": 90, "hrv": 10})
    note(conn, 2, "озноб")
    note(conn, 0)
    found = episode(conn)["not_clean"]
    assert "corridor" in found
    assert "spo2" in found


def test_vital_out_on_past_rest_day_breaks_the_count(conn: sqlite3.Connection) -> None:
    nights(conn)
    night(conn, 1, **{**VITALS_BASE, "spo2": 90})
    note(conn, 3, "озноб")
    for days in (2, 1, 0):
        note(conn, days)
    found = episode(conn)
    assert (found["phase"], found["rest_step"], found["clean_days"]) == ("rest", 1, 1)


def spread_respiration(conn: sqlite3.Connection, today: float) -> dict[str, Any]:
    """База дыхания 14.0 / 16.0 вперемешку (граница коридора 15.9), сегодня - today."""
    for days in range(28, 0, -1):
        night(conn, days, resp=14.0 if days % 2 == 0 else 16.0)
    night(conn, 0, resp=today)
    note(conn, 2, "озноб")
    note(conn, 0)
    return episode(conn)


def test_corridor_with_spread_respiration_inside_is_clean(conn: sqlite3.Connection) -> None:
    assert spread_respiration(conn, 15.5)["not_clean"] == []


def test_corridor_with_spread_respiration_above_is_reason(conn: sqlite3.Connection) -> None:
    assert spread_respiration(conn, 17.0)["not_clean"] == ["respiration"]


VITALS_KEYS = {
    "skin_temp",
    "skin_temp_high_from",
    "skin_temp_high",
    "respiration",
    "respiration_high_from",
    "respiration_high",
    "spo2",
    "spo2_low",
}


def test_report_hrv_streak_is_zero_on_empty_base(conn: sqlite3.Connection) -> None:
    assert report(conn)["hrv_streak"] == 0


def test_report_hrv_streak_is_number_of_bad_days(conn: sqlite3.Connection) -> None:
    nights(conn, {0: "LOW", 1: "BELOW", 2: "UNBALANCED"})
    assert report(conn)["hrv_streak"] == 3


def test_report_vitals_is_all_none_on_empty_base(conn: sqlite3.Connection) -> None:
    found = report(conn)["vitals"]
    assert set(found) == VITALS_KEYS
    assert set(found.values()) == {None}


def test_report_vitals_values_edges_and_flags(conn: sqlite3.Connection) -> None:
    nights(conn)
    assert report(conn)["vitals"] == {
        "skin_temp": 0.2,
        "skin_temp_high_from": 0.2,
        "skin_temp_high": False,
        "respiration": 15.0,
        "respiration_high_from": 15.0,
        "respiration_high": False,
        "spo2": 96,
        "spo2_low": False,
    }


def test_report_vitals_flags_out_of_norm(conn: sqlite3.Connection) -> None:
    nights(conn, today={"skin": 0.3, "resp": 15.1, "spo2": 91})
    found = report(conn)["vitals"]
    assert (found["skin_temp_high"], found["respiration_high"], found["spo2_low"]) == (
        True,
        True,
        True,
    )


def test_report_vitals_without_corridor_has_value_and_no_edge(conn: sqlite3.Connection) -> None:
    night(conn, 0, skin=0.4, resp=15.0, spo2=95)
    found = report(conn)["vitals"]
    assert (found["skin_temp"], found["skin_temp_high_from"], found["skin_temp_high"]) == (
        0.4,
        None,
        None,
    )
    assert (found["spo2"], found["spo2_low"]) == (95, False)


def test_signals_without_hrv_streak_key_and_zero_streak_are_empty() -> None:
    assert illness_signals({"streak": 0}) == []


def test_signals_hrv_streak_below_limit_is_absent() -> None:
    assert illness_signals({"streak": 0, "hrv_streak": 1}) == []


def test_signals_hrv_streak_does_not_depend_on_streak() -> None:
    assert illness_signals({"streak": 0, "hrv_streak": 3}) == [
        {"kind": "hrv_streak", "value": 3, "limit": 2}
    ]


def test_hrv_streak_signal_is_present_on_ill_day(conn: sqlite3.Connection) -> None:
    nights(conn, {0: "UNBALANCED", 1: "UNBALANCED"})
    note(conn, 0, "озноб")
    assert episode(conn)["phase"] == "ill"
    assert signal_of(conn, "hrv_streak") is not None


def test_signals_order_risk_streak_phase(conn: sqlite3.Connection) -> None:
    nights(conn)
    for days in (1, 0):
        night(conn, days, status="UNBALANCED", rhr=90, hrv=10, **VITALS_BASE)
    note(conn, 3, "озноб")
    kinds = [s["kind"] for s in report(conn)["signals"]]
    assert kinds == ["illness_risk", "hrv_streak", "illness_rest"]


def test_signals_order_corridor_out_before_hrv_streak(conn: sqlite3.Connection) -> None:
    nights(conn, {0: "UNBALANCED", 1: "UNBALANCED"})
    night(conn, 0, status="UNBALANCED", rhr=90, hrv=10, **VITALS_BASE)
    kinds = [s["kind"] for s in report(conn)["signals"]]
    assert kinds == ["corridor_out", "hrv_streak"]


def test_not_clean_reasons_keep_server_order(conn: sqlite3.Connection) -> None:
    nights(conn, today={"skin": 0.3, "resp": 15.1, "spo2": 91, "rhr": 90, "hrv": 10})
    note(conn, 2, "озноб")
    assert episode(conn)["not_clean"] == [
        "no_record",
        "corridor",
        "skin_temp",
        "respiration",
        "spo2",
    ]


def spread_metric(conn: sqlite3.Connection, key: str, today: float) -> None:
    """База метрики key (skin / resp) 14.0 / 16.0 вперемешку (граница 15.9), сегодня today."""
    for days in range(28, 0, -1):
        base: dict[str, Any] = {key: 14.0 if days % 2 == 0 else 16.0}
        night(conn, days, **base)
    last: dict[str, Any] = {key: today}
    night(conn, 0, **last)


@pytest.mark.parametrize(
    ("key", "code"), [("skin", "skin_temp"), ("resp", "respiration")], ids=["skin", "resp"]
)
def test_value_between_edge_and_double_swc_is_reason(
    conn: sqlite3.Connection, key: str, code: str
) -> None:
    spread_metric(conn, key, 16.2)
    note(conn, 2, "озноб")
    note(conn, 0)
    assert episode(conn)["not_clean"] == [code]


def test_report_vitals_edges_come_from_mean_plus_one_swc(conn: sqlite3.Connection) -> None:
    for days in range(28, 0, -1):
        value = 14.0 if days % 2 == 0 else 16.0
        night(conn, days, skin=value, resp=value)
    night(conn, 0, skin=16.2, resp=16.2)
    found = report(conn)["vitals"]
    assert (found["skin_temp_high_from"], found["respiration_high_from"]) == (15.9, 15.9)
    assert (found["skin_temp_high"], found["respiration_high"]) == (True, True)
