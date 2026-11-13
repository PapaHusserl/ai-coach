"""Вкладка «Состояние» в пульте: сигналы дня и тренды (шаг П4, партия 5)."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

import pytest

from ai_coach.mcp_server.tools import ToolError
from ai_coach.store.garmin_data import upsert_daily_metrics
from ai_coach.store.journal import add_weight, add_who5
from ai_coach.web.state import state_view

DAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 9, 30, 15)
TREND_DAYS = 14


def put(
    conn: sqlite3.Connection,
    day: date,
    hours: float | None = 7,
    rhr: int | None = None,
    hrv: float | None = None,
    readiness: int | None = None,
) -> None:
    sleep = {} if rhr is None else {"restingHeartRate": rhr}
    values: dict[str, Any] = {
        "date": day.isoformat(),
        "sleep_seconds": None if hours is None else int(hours * 3600),
        "raw_json": {"sleep": sleep},
    }
    if hrv is not None:
        values["hrv_last_night"] = hrv
    if readiness is not None:
        values["readiness_score"] = readiness
    upsert_daily_metrics(conn, values)


def nights(conn: sqlite3.Connection, last_h: float, rhr: int | None = None) -> None:
    """25 ночей по 7 часов до DAY и ночь DAY в last_h часов: норма сна считается."""
    for back in range(25, 0, -1):
        put(conn, DAY - timedelta(days=back), 7, rhr)
    put(conn, DAY, last_h, rhr)


def kinds(view: dict[str, Any]) -> list[str]:
    return [signal["kind"] for signal in view["signals"]]


def test_view_has_signals_trends_and_load_error(conn: sqlite3.Connection) -> None:
    assert set(state_view(conn, DAY, NOW)) == {"signals", "trends", "load_error"}


def test_view_of_empty_base_has_no_signals(conn: sqlite3.Connection) -> None:
    assert state_view(conn, DAY, NOW)["signals"] == []


def test_signals_are_a_list(conn: sqlite3.Connection) -> None:
    assert isinstance(state_view(conn, DAY, NOW)["signals"], list)


def test_short_night_is_a_signal_with_the_agreed_keys(conn: sqlite3.Connection) -> None:
    nights(conn, 5, rhr=50)
    view = state_view(conn, DAY, NOW)
    [signal] = [s for s in view["signals"] if s["kind"] == "short_night"]
    assert set(signal) == {"source", "kind", "value", "limit"}
    assert (signal["value"], signal["limit"]) == (2.0, 1.0)
    assert signal["source"]


def test_normal_night_gives_no_short_night(conn: sqlite3.Connection) -> None:
    nights(conn, 7, rhr=50)
    assert "short_night" not in kinds(state_view(conn, DAY, NOW))


def test_sleep_signals_survive_missing_resting_heart_rate(conn: sqlite3.Connection) -> None:
    nights(conn, 5)
    assert "short_night" in kinds(state_view(conn, DAY, NOW))


def test_missing_resting_heart_rate_sets_load_error_text(conn: sqlite3.Connection) -> None:
    nights(conn, 5)
    error = state_view(conn, DAY, NOW)["load_error"]
    assert isinstance(error, str)
    assert error


def test_load_error_is_none_when_load_is_computable(conn: sqlite3.Connection) -> None:
    nights(conn, 7, rhr=50)
    assert state_view(conn, DAY, NOW)["load_error"] is None


def test_trends_have_the_agreed_series(conn: sqlite3.Connection) -> None:
    trends = state_view(conn, DAY, NOW)["trends"]
    assert set(trends) == {"dates", "sleep_h", "hrv", "rhr", "readiness", "weight"}


def test_trends_dates_are_14_consecutive_days_ending_on_the_day(
    conn: sqlite3.Connection,
) -> None:
    dates = state_view(conn, DAY, NOW)["trends"]["dates"]
    expected = [(DAY - timedelta(days=back)).isoformat() for back in range(TREND_DAYS - 1, -1, -1)]
    assert dates == expected


def test_trends_series_are_as_long_as_dates(conn: sqlite3.Connection) -> None:
    trends = state_view(conn, DAY, NOW)["trends"]
    for key in ("sleep_h", "hrv", "rhr", "readiness"):
        assert len(trends[key]) == TREND_DAYS, key


def test_trends_without_data_are_all_null(conn: sqlite3.Connection) -> None:
    trends = state_view(conn, DAY, NOW)["trends"]
    for key in ("sleep_h", "hrv", "rhr", "readiness"):
        assert trends[key] == [None] * TREND_DAYS, key


def test_trends_values_land_on_their_dates(conn: sqlite3.Connection) -> None:
    put(conn, DAY, 6, rhr=52, hrv=61, readiness=70)
    trends = state_view(conn, DAY, NOW)["trends"]
    assert trends["sleep_h"][-1] == 6
    assert trends["rhr"][-1] == 52
    assert trends["hrv"][-1] == 61
    assert trends["readiness"][-1] == 70


def test_trends_skipped_day_is_null_between_neighbours(conn: sqlite3.Connection) -> None:
    put(conn, DAY - timedelta(days=2), 6, hrv=60)
    put(conn, DAY, 8, hrv=64)
    hrv = state_view(conn, DAY, NOW)["trends"]["hrv"]
    assert hrv[-3:] == [60, None, 64]


def test_trends_ignore_days_older_than_14(conn: sqlite3.Connection) -> None:
    put(conn, DAY - timedelta(days=14), 3, hrv=10)
    assert state_view(conn, DAY, NOW)["trends"]["hrv"] == [None] * TREND_DAYS


def test_trends_weight_is_list_of_date_and_kg(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-11-01 07:00:00", "weight_kg": 82.4})
    add_weight(conn, {"measured_at": "2026-11-07 07:00:00", "weight_kg": 81.7})
    assert state_view(conn, DAY, NOW)["trends"]["weight"] == [
        {"date": "2026-11-01", "kg": 82.4},
        {"date": "2026-11-07", "kg": 81.7},
    ]


def test_trends_weight_covers_30_days(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-09 07:00:00", "weight_kg": 83.0})
    add_weight(conn, {"measured_at": "2026-10-07 07:00:00", "weight_kg": 90.0})
    weight = state_view(conn, DAY, NOW)["trends"]["weight"]
    assert [row["date"] for row in weight] == ["2026-10-09"]


def test_trends_weight_empty_is_empty_list(conn: sqlite3.Connection) -> None:
    assert state_view(conn, DAY, NOW)["trends"]["weight"] == []


def sources(view: dict[str, Any], kind: str) -> list[str]:
    return [s["source"] for s in view["signals"] if s["kind"] == kind]


def put_who5(conn: sqlite3.Connection, score: int) -> None:
    items = [min(5, max(0, score // 4 - 5 * n)) for n in range(5)]
    add_who5(
        conn,
        {
            "date": DAY.isoformat(),
            "logged_at": f"{DAY.isoformat()} 08:00:00",
            **{f"q{n}": value for n, value in enumerate(items, 1)},
            "score": score,
            "text": None,
        },
    )


def test_short_night_source_is_sleep(conn: sqlite3.Connection) -> None:
    nights(conn, 5, rhr=50)
    assert sources(state_view(conn, DAY, NOW), "short_night") == ["sleep"]


def test_deviation_of_the_day_comes_from_deviations(conn: sqlite3.Connection) -> None:
    put(conn, DAY, 4)
    view = state_view(conn, DAY, NOW)
    assert sources(view, "sleep") == ["deviations"]


def test_low_readiness_is_a_deviation(conn: sqlite3.Connection) -> None:
    put(conn, DAY, 7, readiness=30)
    view = state_view(conn, DAY, NOW)
    assert sources(view, "readiness") == ["deviations"]


def test_symptom_in_wellbeing_text_is_a_deviation_signal(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, text, logged_at) VALUES (?, 4, 'горло', ?)",
        (DAY.isoformat(), f"{DAY.isoformat()} 08:00:00"),
    )
    view = state_view(conn, DAY, NOW)
    assert sources(view, "symptoms") == ["deviations"]
    signal = next(s for s in view["signals"] if s["kind"] == "symptoms")
    assert (signal["value"], signal["limit"]) == (["горло"], None)


def test_low_who5_comes_from_who5(conn: sqlite3.Connection) -> None:
    put_who5(conn, 24)
    view = state_view(conn, DAY, NOW)
    assert sources(view, "who5_low") == ["who5"]


def test_illness_signals_come_from_illness_report(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = {"signals": [{"kind": "illness_risk", "value": 2, "limit": 2}]}
    monkeypatch.setattr("ai_coach.web.state.illness_report", lambda *args, **kwargs: fake)
    view = state_view(conn, DAY, NOW)
    assert sources(view, "illness_risk") == ["illness"]


def test_overload_signals_come_from_overload_report(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = {"signals": [{"kind": "total_streak", "value": 3, "limit": 3}]}
    monkeypatch.setattr("ai_coach.web.state.overload_report", lambda *args, **kwargs: fake)
    view = state_view(conn, DAY, NOW)
    assert sources(view, "total_streak") == ["overload"]


def test_signal_sources_go_in_the_agreed_order(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    illness = {"signals": [{"kind": "illness_risk", "value": 2, "limit": 2}]}
    overload = {"signals": [{"kind": "total_streak", "value": 3, "limit": 3}]}
    monkeypatch.setattr("ai_coach.web.state.illness_report", lambda *args, **kwargs: illness)
    monkeypatch.setattr("ai_coach.web.state.overload_report", lambda *args, **kwargs: overload)
    nights(conn, 4, rhr=50)
    put_who5(conn, 24)
    order = [s["source"] for s in state_view(conn, DAY, NOW)["signals"]]
    firsts = list(dict.fromkeys(order))
    assert firsts == ["sleep", "illness", "overload", "who5", "deviations"]
    assert order == sorted(order, key=firsts.index)


def test_sleep_goes_before_deviations(conn: sqlite3.Connection) -> None:
    nights(conn, 4, rhr=50)
    view = state_view(conn, DAY, NOW)
    assert kinds(view).index("short_night") < kinds(view).index("sleep")


def test_load_error_tells_to_run_sync(conn: sqlite3.Connection) -> None:
    nights(conn, 5)
    assert "coach sync" in state_view(conn, DAY, NOW)["load_error"]


def test_trends_weight_30_days_back_is_in_31_is_out(conn: sqlite3.Connection) -> None:
    add_weight(conn, {"measured_at": "2026-10-08 07:00:00", "weight_kg": 83.0})
    add_weight(conn, {"measured_at": "2026-10-07 07:00:00", "weight_kg": 90.0})
    weight = state_view(conn, DAY, NOW)["trends"]["weight"]
    assert weight == [{"date": "2026-10-08", "kg": 83.0}]


def test_view_follows_the_viewed_day(conn: sqlite3.Connection) -> None:
    nights(conn, 5, rhr=50)
    earlier = state_view(conn, DAY - timedelta(days=3), NOW)
    assert "short_night" not in kinds(earlier)
    assert earlier["trends"]["dates"][-1] == "2026-11-04"


def test_trends_first_day_of_window_is_filled(conn: sqlite3.Connection) -> None:
    put(conn, DAY - timedelta(days=TREND_DAYS - 1), 7, rhr=55, hrv=66, readiness=44)
    trends = state_view(conn, DAY, NOW)["trends"]
    assert trends["dates"][0] == "2026-10-25"
    assert (trends["sleep_h"][0], trends["rhr"][0], trends["hrv"][0]) == (7, 55, 66)
    assert trends["readiness"][0] == 44


def test_trends_sleep_hours_rounded_to_one_decimal(conn: sqlite3.Connection) -> None:
    upsert_daily_metrics(conn, {"date": DAY.isoformat(), "sleep_seconds": 27123, "raw_json": {}})
    assert state_view(conn, DAY, NOW)["trends"]["sleep_h"][-1] == 7.5


ROWS = [
    {"date": "2026-11-05", "tss": 10.0},
    {"date": "2026-11-06", "tss": 20.0},
    {"date": "2026-11-07", "tss": 30.0},
]


def spy_collaborators(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {}
    sleep = {"signals": []}

    def load(conn: Any, start: str, end: str) -> dict[str, Any]:
        calls["load"] = (start, end)
        return {"rows": ROWS}

    def sleep_report(*args: Any) -> dict[str, Any]:
        calls["sleep"] = args[1:]
        return sleep

    def illness(*args: Any) -> dict[str, Any]:
        calls["illness"] = args[1:]
        return {"signals": []}

    def deviations(*args: Any) -> list[dict[str, Any]]:
        calls["deviations"] = args[1:]
        return []

    calls["sleep_value"] = sleep
    monkeypatch.setattr("ai_coach.web.state.tools.load", load)
    monkeypatch.setattr("ai_coach.web.state.sleep_report", sleep_report)
    monkeypatch.setattr("ai_coach.web.state.illness_report", illness)
    monkeypatch.setattr("ai_coach.web.state.day_deviations", deviations)
    return calls


def test_load_is_asked_for_14_days_ending_on_the_day(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = spy_collaborators(monkeypatch)
    state_view(conn, DAY, NOW)
    assert calls["load"] == ("2026-10-25", "2026-11-07")


def test_sleep_report_gets_the_day_and_now(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = spy_collaborators(monkeypatch)
    state_view(conn, DAY, NOW)
    assert calls["sleep"] == ("2026-11-07", NOW)


def test_illness_report_gets_tss_by_date_and_the_sleep_report(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = spy_collaborators(monkeypatch)
    state_view(conn, DAY, NOW)
    tss = {"2026-11-05": 10.0, "2026-11-06": 20.0, "2026-11-07": 30.0}
    assert calls["illness"][0] == "2026-11-07"
    assert calls["illness"][1] == tss
    assert calls["illness"][2] is calls["sleep_value"]
    assert len(calls["illness"]) == 3


def test_deviations_get_the_last_load_row(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = spy_collaborators(monkeypatch)
    state_view(conn, DAY, NOW)
    assert calls["deviations"] == ("2026-11-07", ROWS[-1])


def test_deviations_get_no_load_row_when_load_fails(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = spy_collaborators(monkeypatch)

    def failing(*args: Any) -> dict[str, Any]:
        raise ToolError("нагрузка не считается")

    monkeypatch.setattr("ai_coach.web.state.tools.load", failing)
    state_view(conn, DAY, NOW)
    assert calls["deviations"] == ("2026-11-07", None)
