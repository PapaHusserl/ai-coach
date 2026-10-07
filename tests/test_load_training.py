import sqlite3

import pytest

from ai_coach.load import daily_tss, hr_tss, load_series
from ai_coach.store.garmin_data import upsert_activity

# Формула hrTSS по резерву ЧСС (см. отчёт): IF = (avg_hr - rest_hr) / (lthr - rest_hr),
# TSS = часы * IF^2 * 100. В тестах rest_hr=50, lthr=170 (знаменатель 120).
REST = 50
LTHR = 170
BY_SPORT: dict[str, float] = {"run": 170, "bike": 160, "swim": 150}


def activity(
    conn: sqlite3.Connection,
    activity_id: int,
    start: str,
    duration_s: float | None,
    avg_hr: float | None,
    type_key: str = "running",
) -> None:
    upsert_activity(
        conn,
        {
            "activity_id": activity_id,
            "start_time_local": start,
            "type_key": type_key,
            "duration_s": duration_s,
            "avg_hr": avg_hr,
            "raw_json": {},
        },
    )


def test_hr_tss_threshold_hour_is_100() -> None:
    # IF = (170-50)/120 = 1, 1 ч -> 100
    assert hr_tss(3600, 170, rest_hr=REST, lthr=LTHR) == pytest.approx(100.0)


def test_hr_tss_manual_value() -> None:
    # IF = (140-50)/120 = 0.75; 1 ч * 0.5625 * 100 = 56.25
    assert hr_tss(3600, 140, rest_hr=REST, lthr=LTHR) == pytest.approx(56.25)


def test_hr_tss_scales_with_duration() -> None:
    # IF = (110-50)/120 = 0.5; 2 ч * 0.25 * 100 = 50
    assert hr_tss(7200, 110, rest_hr=REST, lthr=LTHR) == pytest.approx(50.0)


def test_hr_tss_pulse_at_or_below_rest_is_zero() -> None:
    assert hr_tss(3600, 50, rest_hr=REST, lthr=LTHR) == 0.0
    assert hr_tss(3600, 40, rest_hr=REST, lthr=LTHR) == 0.0


def test_hr_tss_without_pulse_or_duration_is_zero() -> None:
    assert hr_tss(3600, None, rest_hr=REST, lthr=LTHR) == 0.0
    assert hr_tss(None, 140, rest_hr=REST, lthr=LTHR) == 0.0


def test_daily_tss_sums_activities_of_one_local_day(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-03-03 07:00:00", 1800, 170)  # 0.5 ч * 1 * 100 = 50
    activity(conn, 2, "2026-03-03 19:00:00", 3600, 110)  # 1 ч * 0.25 * 100 = 25
    activity(conn, 3, "2026-03-01 07:00:00", 3600, 140)  # 56.25
    result = daily_tss(conn, "2026-03-01", "2026-03-03", rest_hr=REST, lthr_by_sport=BY_SPORT)
    assert result == {
        "2026-03-01": pytest.approx(56.25),
        "2026-03-02": 0.0,
        "2026-03-03": pytest.approx(75.0),
    }


def test_daily_tss_ignores_activities_outside_period(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-02-28 07:00:00", 3600, 170)
    activity(conn, 2, "2026-03-04 07:00:00", 3600, 170)
    result = daily_tss(conn, "2026-03-01", "2026-03-03", rest_hr=REST, lthr_by_sport=BY_SPORT)
    assert result == {"2026-03-01": 0.0, "2026-03-02": 0.0, "2026-03-03": 0.0}


def test_daily_tss_activity_without_pulse_adds_zero(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-03-01 07:00:00", 3600, None)
    result = daily_tss(conn, "2026-03-01", "2026-03-01", rest_hr=REST, lthr_by_sport=BY_SPORT)
    assert result == {"2026-03-01": 0.0}


# Ручной расчёт: TSS по дням 56.25, 0, 75; старт CTL = ATL = 0.
# CTL_t = CTL_{t-1} + (TSS_t - CTL_{t-1}) / 42, ATL_t = ATL_{t-1} + (TSS_t - ATL_{t-1}) / 7.
# День 1: CTL = 56.25/42 = 1.339286;  ATL = 56.25/7 = 8.035714
# День 2: CTL = 1.339286 * 41/42 = 1.307398;  ATL = 8.035714 * 6/7 = 6.887755
# День 3: CTL = 1.307398 + (75 - 1.307398)/42 = 1.307398 + 1.754586 = 3.061984
#         ATL = 6.887755 + (75 - 6.887755)/7 = 6.887755 + 9.730321 = 16.618076
TSS = {"2026-03-01": 56.25, "2026-03-02": 0.0, "2026-03-03": 75.0}


def test_load_series_matches_manual_calculation() -> None:
    series = load_series(TSS)
    assert [r["date"] for r in series] == ["2026-03-01", "2026-03-02", "2026-03-03"]
    assert [r["tss"] for r in series] == [56.25, 0.0, 75.0]
    assert [r["ctl"] for r in series] == pytest.approx([1.339286, 1.307398, 3.061984], abs=1e-6)
    assert [r["atl"] for r in series] == pytest.approx([8.035714, 6.887755, 16.618076], abs=1e-6)


def test_load_series_start_values() -> None:
    # Старт с нуля, один день TSS=42: CTL = 42/42 = 1, ATL = 42/7 = 6
    [row] = load_series({"2026-03-01": 42.0})
    assert row["ctl"] == pytest.approx(1.0)
    assert row["atl"] == pytest.approx(6.0)


def test_load_series_constant_load_converges_to_it() -> None:
    days = {f"2026-{m:02d}-{d:02d}": 100.0 for m in (1, 2, 3, 4) for d in range(1, 29)}
    last = load_series(days)[-1]
    assert last["atl"] == pytest.approx(100.0, abs=0.01)
    assert 80.0 < last["ctl"] < 100.0


def test_load_series_is_sorted_by_date_even_if_dict_is_not() -> None:
    series = load_series({"2026-03-02": 0.0, "2026-03-01": 56.25})
    assert [r["date"] for r in series] == ["2026-03-01", "2026-03-02"]
    assert series[1]["ctl"] == pytest.approx(1.307398, abs=1e-6)


def test_load_series_empty() -> None:
    assert load_series({}) == []


def test_series_from_database_matches_manual_calculation(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-03-01 07:00:00", 3600, 140)
    activity(conn, 2, "2026-03-03 07:00:00", 1800, 170)
    activity(conn, 3, "2026-03-03 19:00:00", 3600, 110)
    series = load_series(
        daily_tss(conn, "2026-03-01", "2026-03-03", rest_hr=REST, lthr_by_sport=BY_SPORT)
    )
    assert series[-1]["ctl"] == pytest.approx(3.061984, abs=1e-6)
    assert series[-1]["atl"] == pytest.approx(16.618076, abs=1e-6)


def test_hr_tss_zero_duration_is_zero() -> None:
    assert hr_tss(0, 150, REST, LTHR) == 0


@pytest.mark.parametrize("lthr", [50, 40])
def test_hr_tss_lthr_not_above_rest_hr_raises(lthr: float) -> None:
    with pytest.raises(ValueError):
        hr_tss(3600, 150, REST, lthr)


def day_tss(conn: sqlite3.Connection) -> float:
    return daily_tss(conn, "2026-03-01", "2026-03-01", REST, BY_SPORT)["2026-03-01"]


def test_bike_activity_uses_bike_threshold(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-03-01 07:00:00", 3600, 160, "cycling")
    # IF = (160-50)/(160-50) = 1 по порогу вело; по беговому было бы (110/120)^2*100
    assert day_tss(conn) == pytest.approx(100.0)


def test_swim_activity_uses_swim_threshold(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-03-01 07:00:00", 3600, 150, "lap_swimming")
    assert day_tss(conn) == pytest.approx(100.0)


def test_unknown_cardio_type_key_uses_run_threshold(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-03-01 07:00:00", 3600, 170, "hiking")
    assert day_tss(conn) == pytest.approx(100.0)


def test_strength_is_35_tss_per_hour_regardless_of_pulse(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-03-01 07:00:00", 3600, None, "strength_training")
    activity(conn, 2, "2026-03-01 19:00:00", 1800, 170, "strength_training")
    assert day_tss(conn) == pytest.approx(52.5)


def test_strength_without_duration_adds_zero(conn: sqlite3.Connection) -> None:
    activity(conn, 1, "2026-03-01 07:00:00", None, 120, "strength_training")
    assert day_tss(conn) == 0.0


@pytest.mark.parametrize("type_key", ["yoga", "stretching", "mobility"])
def test_mobility_adds_zero_even_with_high_pulse(conn: sqlite3.Connection, type_key: str) -> None:
    activity(conn, 1, "2026-03-01 07:00:00", 3600, 170, type_key)
    assert day_tss(conn) == 0.0
