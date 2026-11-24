"""Отклик ночи на вечер и день (Н6): пары, группы с фактором и без, отчёт. Синтетика.

Интерфейс (по плану Н6, «Умолчания» 1; сигнатуры — решение этой партии, кабан следует им):
night_pairs(days, nights, sick) - days: строки дней (date), nights: строки ночей (date, hrv, rhr,
sleep_min), sick: даты болезни; пара - {date, day, hrv, rhr, sleep_min} (отклик - ночь D+1).
response(with_pairs, without_pairs) - {with, without, hrv, rhr, sleep_min, enough}.
recovery_report(conn, day, tss) - {factors: [{factor, with, without, hrv, rhr, sleep_min, enough}]}.
"""

import sqlite3
from datetime import date, timedelta
from typing import Any

from workload_fakes import stored_event

from ai_coach.store.garmin_data import upsert_daily_metrics
from ai_coach.store.journal import add_wellbeing
from ai_coach.store.workload import replace_calendar_window, upsert_counter

DAY = date(2026, 11, 24)
FACTORS = ["evening_work", "claude_evening", "heavy_day"]


def back(days: int) -> str:
    return (DAY - timedelta(days=days)).isoformat()


def pair(
    hrv: float | None, rhr: float | None = 50, sleep_min: float | None = 420
) -> dict[str, Any]:
    return {"hrv": hrv, "rhr": rhr, "sleep_min": sleep_min}


def pairs_of(count: int, hrv: float | None, rhr: float | None = 50) -> list[dict[str, Any]]:
    return [pair(hrv, rhr) for _ in range(count)]


# --- night_pairs ---


def entry(iso: str) -> dict[str, Any]:
    return {"date": iso}


def night(iso: str, hrv: float | None = 45, rhr: float | None = 50) -> dict[str, Any]:
    return {"date": iso, "hrv": hrv, "rhr": rhr, "sleep_min": 420}


def make_pairs(
    days: list[str], nights: list[dict[str, Any]], sick: set[str] | None = None
) -> list[dict[str, Any]]:
    from ai_coach.load.recovery import night_pairs

    return night_pairs([entry(d) for d in days], nights, sick or set())


def test_pair_takes_response_from_next_night() -> None:
    found = make_pairs(["2026-11-10"], [night("2026-11-11", hrv=41, rhr=53)])
    assert [(p["date"], p["hrv"], p["rhr"], p["sleep_min"]) for p in found] == [
        ("2026-11-10", 41, 53, 420)
    ]


def test_pair_carries_the_evening_day() -> None:
    found = make_pairs(["2026-11-10"], [night("2026-11-11")])
    assert found[0]["day"] == entry("2026-11-10")


def test_no_pair_without_next_night() -> None:
    assert make_pairs(["2026-11-10"], [night("2026-11-10"), night("2026-11-12")]) == []


def test_no_pair_when_next_night_has_no_hrv() -> None:
    assert make_pairs(["2026-11-10"], [night("2026-11-11", hrv=None)]) == []


def test_no_pair_when_next_night_has_no_resting_heart_rate() -> None:
    assert make_pairs(["2026-11-10"], [night("2026-11-11", rhr=None)]) == []


def test_no_pair_when_evening_day_is_sick() -> None:
    nights = [night("2026-11-11")]
    assert make_pairs(["2026-11-10"], nights, {"2026-11-10"}) == []


def test_no_pair_when_next_night_day_is_sick() -> None:
    nights = [night("2026-11-11")]
    assert make_pairs(["2026-11-10"], nights, {"2026-11-11"}) == []


def test_sick_day_removes_only_its_own_pairs() -> None:
    days = ["2026-11-10", "2026-11-11", "2026-11-12"]
    nights = [night("2026-11-11"), night("2026-11-12"), night("2026-11-13")]
    found = make_pairs(days, nights, {"2026-11-12"})
    assert [p["date"] for p in found] == ["2026-11-10"]


def test_last_day_of_window_without_next_night_gives_no_pair() -> None:
    days = ["2026-11-10", "2026-11-11"]
    found = make_pairs(days, [night("2026-11-11")])
    assert [p["date"] for p in found] == ["2026-11-10"]


# --- response ---


def respond(with_pairs: list[dict[str, Any]], without: list[dict[str, Any]]) -> dict[str, Any]:
    from ai_coach.load.recovery import response

    return response(with_pairs, without)


def test_response_counts_and_differences() -> None:
    found = respond(pairs_of(12, 40, 52), pairs_of(15, 46, 49))
    assert (found["with"], found["without"]) == (12, 15)
    assert (found["hrv"], found["rhr"], found["enough"]) == (-6, 3, True)


def test_response_is_not_enough_when_with_group_is_small() -> None:
    found = respond(pairs_of(6, 40, 52), pairs_of(21, 46, 49))
    assert found["enough"] is False
    assert (found["hrv"], found["rhr"]) == (-6, 3)


def test_response_is_not_enough_when_without_group_is_small() -> None:
    found = respond(pairs_of(21, 40, 52), pairs_of(6, 46, 49))
    assert found["enough"] is False
    assert found["hrv"] == -6


def test_response_enough_at_ten_nights_in_each_group() -> None:
    assert respond(pairs_of(10, 40), pairs_of(10, 46))["enough"] is True


def test_response_not_enough_at_nine_nights_in_a_group() -> None:
    assert respond(pairs_of(9, 40), pairs_of(10, 46))["enough"] is False
    assert respond(pairs_of(10, 40), pairs_of(9, 46))["enough"] is False


def test_response_differences_are_null_when_with_group_is_empty() -> None:
    found = respond([], pairs_of(15, 46, 49))
    assert (found["with"], found["hrv"], found["rhr"], found["sleep_min"]) == (0, None, None, None)
    assert found["enough"] is False


def test_response_differences_are_null_when_without_group_is_empty() -> None:
    found = respond(pairs_of(15, 40, 52), [])
    assert (found["without"], found["hrv"], found["rhr"], found["sleep_min"]) == (
        0,
        None,
        None,
        None,
    )


def test_response_uses_medians() -> None:
    with_pairs = [pair(40), pair(41), pair(80)]
    found = respond(with_pairs, [pair(46), pair(46), pair(0)])
    assert found["hrv"] == -5


def test_response_skips_pair_without_value_of_this_response_only() -> None:
    with_pairs = [pair(40, 52), pair(None, 56), pair(44, None)]
    found = respond(with_pairs, [pair(46, 49)] * 3)
    assert found["with"] == 3
    assert found["hrv"] == -4  # медиана 40 и 44 = 42
    assert found["rhr"] == 5  # медиана 52 и 56 = 54, минус 49


def test_response_difference_is_null_when_no_pair_has_the_value() -> None:
    found = respond([pair(40, None)] * 3, [pair(46, 49)] * 3)
    assert found["rhr"] is None
    assert found["hrv"] == -6


def test_response_rounds_hrv_and_rhr_to_one_digit() -> None:
    found = respond([pair(40.26, 52.26)], [pair(46, 49)])
    assert found["hrv"] == -5.7
    assert found["rhr"] == 3.3


def test_response_sleep_difference_is_whole_minutes() -> None:
    found = respond([pair(40, 50, 400.4)], [pair(46, 49, 430)])
    assert found["sleep_min"] == -30
    assert isinstance(found["sleep_min"], int)


# --- recovery_report ---


def put_night(
    conn: sqlite3.Connection,
    iso: str,
    hrv: float = 45,
    rhr: float = 50,
    api: bool = True,
    sleep_seconds: int = 25200,
) -> None:
    sleep = {"restingHeartRate": rhr}
    metrics = {"hrv": {"metrics": [{"type": "HR", "value": rhr}]}}
    upsert_daily_metrics(
        conn,
        {
            "date": iso,
            "hrv_last_night": hrv,
            "sleep_seconds": sleep_seconds,
            "raw_json": {"sleep": sleep} if api else metrics,
        },
    )


def put_counter(conn: sqlite3.Connection, iso: str, kind: str, value: float) -> None:
    source = "claude" if kind.startswith("claude") else "screen"
    upsert_counter(
        conn,
        {
            "date": iso,
            "kind": kind,
            "value": value,
            "source": source,
            "synced_at": "2026-11-24T10:00:00",
        },
    )


def build(conn: sqlite3.Connection) -> dict[str, Any]:
    from ai_coach.load.recovery import recovery_report

    return recovery_report(conn, DAY.isoformat(), {})


def factor(report: dict[str, Any], name: str) -> dict[str, Any]:
    return next(f for f in report["factors"] if f["factor"] == name)


def test_report_without_data_has_three_empty_factors_in_order(conn: sqlite3.Connection) -> None:
    report = build(conn)
    assert [f["factor"] for f in report["factors"]] == FACTORS
    for found in report["factors"]:
        assert (found["with"], found["without"], found["enough"]) == (0, 0, False)
        assert found["hrv"] is None


def test_report_evening_work_splits_pairs_by_threshold(conn: sqlite3.Connection) -> None:
    for ago in (10, 9, 8):  # вечер D = ago, ночь D+1 = ago - 1
        put_counter(conn, back(ago), "screen_work_evening_hours", 1.5)
        put_night(conn, back(ago - 1), hrv=40, rhr=52)
    for ago in (7, 6):
        put_counter(conn, back(ago), "screen_work_evening_hours", 0.99)
        put_night(conn, back(ago - 1), hrv=46, rhr=49)
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (3, 2)
    assert (found["hrv"], found["rhr"]) == (-6, 3)


def test_report_evening_work_at_exactly_one_hour_is_with(conn: sqlite3.Connection) -> None:
    put_counter(conn, back(5), "screen_work_evening_hours", 1.0)
    put_night(conn, back(4))
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (1, 0)


def test_report_heavy_day_splits_pairs_by_total(conn: sqlite3.Connection) -> None:
    put_counter(conn, back(6), "screen_work_hours", 12.0)
    put_night(conn, back(5), hrv=40, rhr=52)
    put_counter(conn, back(4), "screen_work_hours", 11.99)
    put_night(conn, back(3), hrv=46, rhr=49)
    found = factor(build(conn), "heavy_day")
    assert (found["with"], found["without"]) == (1, 1)
    assert (found["hrv"], found["rhr"]) == (-6, 3)


def test_report_claude_evening_splits_by_window_median_strictly_above(
    conn: sqlite3.Connection,
) -> None:
    for ago, prompts in ((9, 1), (8, 2), (7, 3), (6, 4), (5, 5)):  # медиана 3
        put_counter(conn, back(ago), "claude_prompts_evening", prompts)
        put_night(conn, back(ago - 1), hrv=40 if prompts > 3 else 46)
    found = factor(build(conn), "claude_evening")
    assert (found["with"], found["without"]) == (2, 3)
    assert found["hrv"] == -6


def test_report_day_without_claude_counter_is_in_no_claude_group(conn: sqlite3.Connection) -> None:
    for ago, prompts in ((9, 1), (8, 5)):
        put_counter(conn, back(ago), "claude_prompts_evening", prompts)
        put_night(conn, back(ago - 1))
    put_night(conn, back(6))  # вечер дня 7 назад без счётчика Claude
    found = factor(build(conn), "claude_evening")
    assert (found["with"], found["without"]) == (1, 1)


def test_report_day_without_claude_counter_does_not_move_the_median(
    conn: sqlite3.Connection,
) -> None:
    for ago, prompts in ((9, 10), (8, 20), (7, 30)):  # медиана 20, пустые дни медиану не тянут
        put_counter(conn, back(ago), "claude_prompts_evening", prompts)
        put_night(conn, back(ago - 1))
    for ago in (6, 5, 4, 3):
        put_night(conn, back(ago - 1))
    found = factor(build(conn), "claude_evening")
    assert (found["with"], found["without"]) == (1, 2)


def test_report_day_without_screen_counter_is_in_no_evening_work_group(
    conn: sqlite3.Connection,
) -> None:
    put_night(conn, back(4))
    report = build(conn)
    found = factor(report, "evening_work")
    assert (found["with"], found["without"]) == (0, 0)
    assert (factor(report, "heavy_day")["with"], factor(report, "heavy_day")["without"]) == (0, 1)


def test_report_day_with_zero_screen_counter_is_in_evening_work_without(
    conn: sqlite3.Connection,
) -> None:
    put_counter(conn, back(5), "screen_work_evening_hours", 0.0)
    put_night(conn, back(4))
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (0, 1)


def test_report_calendar_evening_without_screen_counter_is_in_no_evening_work_group(
    conn: sqlite3.Connection,
) -> None:
    event = stored_event(
        "work", uid="late", start_at=f"{back(5)}T20:00:00", end_at=f"{back(5)}T22:00:00"
    )
    replace_calendar_window(conn, back(30), back(0), [event])
    put_night(conn, back(4))
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (0, 0)


def test_report_takes_pairs_inside_the_window_only(conn: sqlite3.Connection) -> None:
    from ai_coach.load.recovery import RESPONSE_DAYS

    put_counter(conn, back(5), "screen_work_evening_hours", 2.0)
    put_night(conn, back(4))
    outside = RESPONSE_DAYS + 5
    put_counter(conn, back(outside), "screen_work_evening_hours", 2.0)
    put_night(conn, back(outside - 1))
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (1, 0)


def test_report_window_edge_evening_ninety_days_back_is_in_ninety_one_is_out(
    conn: sqlite3.Connection,
) -> None:
    from ai_coach.load.recovery import RESPONSE_DAYS

    put_counter(conn, back(RESPONSE_DAYS + 1), "screen_work_evening_hours", 0.0)
    put_counter(conn, back(RESPONSE_DAYS), "screen_work_evening_hours", 0.0)
    put_night(conn, back(RESPONSE_DAYS + 1 - 1))  # вечер day - 91, ночь day - 90
    put_night(conn, back(RESPONSE_DAYS - 1))  # вечер day - 90, ночь day - 89
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (0, 1)


def test_report_claude_median_counts_day_without_night(conn: sqlite3.Connection) -> None:
    for ago, prompts in ((9, 1), (8, 5), (7, 100)):  # ночь есть только у дней 1 и 5
        put_counter(conn, back(ago), "claude_prompts_evening", prompts)
    put_night(conn, back(8))
    put_night(conn, back(7))
    found = factor(build(conn), "claude_evening")
    assert (found["with"], found["without"]) == (0, 2)  # медиана 5, а не 3


def test_report_window_is_ninety_days() -> None:
    from ai_coach.load.recovery import RESPONSE_DAYS

    assert RESPONSE_DAYS == 90


def test_report_not_enough_below_threshold_constant() -> None:
    from ai_coach.load.recovery import RESPONSE_MIN_DAYS

    assert RESPONSE_MIN_DAYS == 10


def test_report_skips_import_nights_before_first_api_night(conn: sqlite3.Connection) -> None:
    put_counter(conn, back(12), "screen_work_evening_hours", 2.0)
    put_night(conn, back(11), api=False)  # импорт: пульс покоя другого источника
    put_counter(conn, back(7), "screen_work_evening_hours", 2.0)
    put_night(conn, back(6), api=True)
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (1, 0)


def test_report_takes_nights_after_first_api_night(conn: sqlite3.Connection) -> None:
    put_counter(conn, back(9), "screen_work_evening_hours", 0.0)
    put_counter(conn, back(4), "screen_work_evening_hours", 0.0)
    put_night(conn, back(8), api=True)
    put_counter(conn, back(6), "screen_work_evening_hours", 2.0)
    put_night(conn, back(5), api=True)
    put_night(conn, back(3), api=True)
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (1, 2)  # пара с ночью back(8) тоже берётся


def test_report_night_after_today_is_not_taken(conn: sqlite3.Connection) -> None:
    put_counter(conn, DAY.isoformat(), "screen_work_evening_hours", 2.0)
    put_night(conn, (DAY + timedelta(days=1)).isoformat())
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"]) == (0, 0)


def test_report_enough_when_each_group_has_ten_pairs(conn: sqlite3.Connection) -> None:
    for ago in range(30, 20, -1):
        put_counter(conn, back(ago), "screen_work_evening_hours", 2.0)
        put_night(conn, back(ago - 1), hrv=40)
    for ago in range(19, 9, -1):
        put_counter(conn, back(ago), "screen_work_evening_hours", 0.0)
        put_night(conn, back(ago - 1), hrv=46)
    found = factor(build(conn), "evening_work")
    assert (found["with"], found["without"], found["enough"]) == (10, 10, True)
    assert found["hrv"] == -6


def test_report_sleep_difference_in_minutes(conn: sqlite3.Connection) -> None:
    put_counter(conn, back(6), "screen_work_evening_hours", 2.0)
    put_counter(conn, back(4), "screen_work_evening_hours", 0.0)
    put_night(conn, back(5), sleep_seconds=6 * 3600)
    put_night(conn, back(3), sleep_seconds=7 * 3600)
    found = factor(build(conn), "evening_work")
    assert found["sleep_min"] == -60


# --- болезнь (Р6в): день фазы или сигнала illness_* выпадает из пар ---


def normal_nights(conn: sqlite3.Connection, first: int = 40, last: int = 1) -> None:
    """Ночи API от first до last дней назад в коридоре; в одной ночи значения выше - разброс."""
    for ago in range(first, last - 1, -1):
        outlier = ago == 30
        put_night(conn, back(ago), hrv=70 if outlier else 60, rhr=60 if outlier else 50)


def note(conn: sqlite3.Connection, ago: int, text: str = "") -> None:
    add_wellbeing(
        conn,
        {"date": back(ago), "logged_at": f"{back(ago)} 09:00:00", "score": 3, "text": text},
    )


def pairs_count(conn: sqlite3.Connection) -> int:
    found = factor(build(conn), "heavy_day")
    return found["with"] + found["without"]


def test_report_without_illness_counts_all_pairs(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    assert pairs_count(conn) == 40


def test_report_illness_risk_day_drops_its_pairs_but_first_out_day_does_not(
    conn: sqlite3.Connection,
) -> None:
    normal_nights(conn)
    put_night(conn, back(3), hrv=10, rhr=90)  # первый день вне коридора: corridor_out
    put_night(conn, back(2), hrv=10, rhr=90)  # второй подряд: illness_risk
    # пары с D = back(3) (ночь X) и D = back(2) (вечер X) не считаются, пара с ночью back(3) - да
    assert pairs_count(conn) == 38


def test_report_symptom_day_drops_pairs_of_that_day(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 25, "озноб")
    # фаза болезни идёт от дня симптома: 11 дней (back 25..15) выпадают, пары с ними - тоже
    assert pairs_count(conn) == 28


def test_report_return_day_without_symptom_text_drops_pairs(conn: sqlite3.Connection) -> None:
    normal_nights(conn)
    note(conn, 25, "озноб")
    note(conn, 24)
    note(conn, 23)
    # дни возврата back 22..16 без симптома в тексте тоже болезнь; по правилу «симптом в тексте»
    # выпал бы один день (38 пар)
    assert pairs_count(conn) == 29
