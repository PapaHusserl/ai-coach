import sqlite3
from datetime import date

import pytest
from garmin_fakes import FakeGarmin
from garminconnect import GarminConnectConnectionError, GarminConnectTooManyRequestsError

from ai_coach.profile.service import current_profile, set_value
from ai_coach.store.garmin_data import list_daily_metrics
from ai_coach.sync.garmin_sync import sync

TODAY = date(2026, 3, 10)


def run_sync(conn: sqlite3.Connection, client: FakeGarmin) -> str:
    return sync(conn, client, 1, pause=0, today=TODAY)  # type: ignore[arg-type]


def entries(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM profile_log ORDER BY id").fetchall()


def garmin_value(conn: sqlite3.Connection, key: str) -> str:
    rows = [r for r in entries(conn) if r["key"] == key]
    assert len(rows) == 1
    assert rows[0]["source"] == "garmin"
    return rows[0]["value"]


def test_sync_asks_for_user_profile_once(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin()
    run_sync(conn, fake)
    assert [c for c in fake.calls if c[0] == "get_user_profile"] == [("get_user_profile", None)]


def test_sync_writes_sex_from_gender(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    assert garmin_value(conn, "sex") == "m"


def test_sync_writes_female_sex(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin()
    fake.profile["userData"]["gender"] = "FEMALE"
    run_sync(conn, fake)
    assert garmin_value(conn, "sex") == "f"


def test_sync_writes_birth_date(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    assert garmin_value(conn, "birth_date") == "1990-01-15"


def test_sync_writes_height(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    assert float(garmin_value(conn, "height_cm")) == 180


def test_sync_converts_weight_from_grams_to_kg(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    assert float(garmin_value(conn, "weight")) == 80.0


def test_sync_does_not_write_weight_log(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    assert conn.execute("SELECT count(*) FROM weight_log").fetchone()[0] == 0


def test_sync_offers_schedule_from_available_days(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    assert garmin_value(conn, "schedule")


def test_sync_does_not_write_activity_level_or_vo2max(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    keys = {r["key"] for r in entries(conn)}
    assert "activity_level" not in keys
    assert not any("vo2" in key for key in keys)


def test_sync_writes_max_hr_from_zones(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    assert float(garmin_value(conn, "max_hr")) in (195, 200)


def test_current_profile_after_sync(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    profile = current_profile(conn, "2026-03-10")
    assert profile["values"]["sex"]["value"] == "m"
    assert profile["values"]["sex"]["source"] == "garmin"
    assert profile["weight_kg"] == 80.0
    assert profile["age"] == 36


def test_repeated_sync_adds_no_rows(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    first = [tuple(r) for r in entries(conn)]
    run_sync(conn, FakeGarmin())
    assert [tuple(r) for r in entries(conn)] == first


def test_changed_garmin_height_adds_a_row(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    before = len(entries(conn))
    fake = FakeGarmin()
    fake.profile["userData"]["height"] = 181.0
    run_sync(conn, fake)
    assert len(entries(conn)) == before + 1


def test_manual_values_win_over_synced(conn: sqlite3.Connection) -> None:
    set_value(conn, "height_cm", "178", "manual", "2026-03-01T10:00:00")
    set_value(conn, "schedule", "только вечера", "manual", "2026-03-01T10:00:00")
    run_sync(conn, FakeGarmin())
    values = current_profile(conn, "2026-03-10")["values"]
    assert float(values["height_cm"]["value"]) == 178
    assert values["schedule"]["value"] == "только вечера"


@pytest.mark.parametrize(
    "error", [GarminConnectTooManyRequestsError("429"), GarminConnectConnectionError("net")]
)
def test_garmin_error_on_profile_does_not_fail_sync(
    conn: sqlite3.Connection, error: Exception
) -> None:
    fake = FakeGarmin(fail={"get_user_profile": error})
    fake.zones = []
    message = run_sync(conn, fake)
    assert entries(conn) == []
    assert "профил" in message.lower()
    assert list_daily_metrics(conn, "2026-03-01", "2026-03-10")


def test_garmin_error_on_profile_keeps_old_profile(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin())
    before = [tuple(r) for r in entries(conn)]
    run_sync(conn, FakeGarmin(fail={"get_user_profile": GarminConnectTooManyRequestsError("429")}))
    assert [tuple(r) for r in entries(conn)] == before


@pytest.mark.parametrize("answer", [{}, None, {"id": 1}, {"id": 1, "userData": None}])
def test_incomplete_profile_answer_does_not_fail_sync(
    conn: sqlite3.Connection, answer: object
) -> None:
    fake = FakeGarmin(profile=answer)
    fake.zones = []
    run_sync(conn, fake)
    assert entries(conn) == []
    assert list_daily_metrics(conn, "2026-03-01", "2026-03-10")


def test_sync_ok_is_logged_when_profile_failed(conn: sqlite3.Connection) -> None:
    run_sync(conn, FakeGarmin(fail={"get_user_profile": GarminConnectTooManyRequestsError("429")}))
    assert conn.execute("SELECT status FROM sync_log").fetchone()[0] == "ok"


def test_height_out_of_range_does_not_fail_sync(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin()
    fake.profile["userData"]["height"] = 300.0
    message = run_sync(conn, fake)
    assert "height_cm вне диапазона" in message
    assert "height_cm" not in {r["key"] for r in entries(conn)}
    assert "sex" in {r["key"] for r in entries(conn)}
    assert list_daily_metrics(conn, "2026-03-01", "2026-03-10")


def test_partial_profile_writes_what_came_and_names_missing(conn: sqlite3.Connection) -> None:
    fake = FakeGarmin()
    del fake.profile["userData"]["height"]
    message = run_sync(conn, fake)
    keys = {r["key"] for r in entries(conn)}
    assert "sex" in keys
    assert "height_cm" not in keys
    assert "нет: height_cm" in message


def test_schedule_is_not_written_when_manual_exists(conn: sqlite3.Connection) -> None:
    set_value(conn, "schedule", "только вечера", "manual", "2026-03-01T10:00:00")
    run_sync(conn, FakeGarmin())
    assert [r["source"] for r in entries(conn) if r["key"] == "schedule"] == ["manual"]
