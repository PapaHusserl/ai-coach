import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest
from garmin_fakes import FIXTURES, FakeGarmin, snapshot, sync_log
from garminconnect import GarminConnectConnectionError, GarminConnectTooManyRequestsError
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.garmin.client import GarminAuthError, GarminError, GarminRateLimitError
from ai_coach.store.db import open_db
from ai_coach.store.plans import add_planned_workout

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """База и каталог токенов — во временной папке, пауз между запросами нет."""
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    monkeypatch.setattr(time, "sleep", lambda _: None)
    return db


def use_client(monkeypatch: pytest.MonkeyPatch, client: FakeGarmin) -> None:
    monkeypatch.setattr(main, "load_client", lambda *a, **k: client)


def count(db: Path, table: str) -> int:
    if not db.exists():
        return 0
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def test_sync_saves_days_to_database(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeGarmin())
    result = runner.invoke(main.app, ["sync", "--days", "3"])
    assert result.exit_code == 0
    assert count(isolated, "daily_metrics") == 3
    assert count(isolated, "activities") == 1
    assert count(isolated, "strength_sets") == 5


def test_sync_days_option_is_respected(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeGarmin())
    runner.invoke(main.app, ["sync", "--days", "2"])
    assert count(isolated, "daily_metrics") == 2


def test_sync_writes_sync_log(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_client(monkeypatch, FakeGarmin())
    runner.invoke(main.app, ["sync", "--days", "1"])
    rows = sync_log(isolated)
    assert [(r["kind"], r["status"]) for r in rows] == [("sync", "ok")]


def test_repeated_sync_does_not_change_database(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, FakeGarmin())
    runner.invoke(main.app, ["sync", "--days", "3"])
    first = snapshot(isolated)
    runner.invoke(main.app, ["sync", "--days", "3"])
    assert snapshot(isolated) == first


def test_sync_without_tokens_says_to_run_login(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_tokens(*a: Any, **k: Any) -> None:
        raise GarminError("Токенов Garmin нет. Выполни в обычном терминале: coach login")

    monkeypatch.setattr(main, "load_client", no_tokens)
    result = runner.invoke(main.app, ["sync"])
    assert result.exit_code == 1
    assert "coach login" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_sync_429_shows_clear_error_and_keeps_database(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, FakeGarmin())
    runner.invoke(main.app, ["sync", "--days", "2"])
    before = snapshot(isolated)
    broken = FakeGarmin(fail={"get_sleep_data": GarminConnectTooManyRequestsError("429")})
    use_client(monkeypatch, broken)
    result = runner.invoke(main.app, ["sync", "--days", "5"])
    assert result.exit_code == 1
    assert "429" in result.output
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert snapshot(isolated) == before


def test_login_asks_credentials_and_hides_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(["user@example.com", "s3cret-pass"])
    monkeypatch.setattr(main, "getpass", lambda _="": next(answers))
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main, "full_login", lambda email, password, *a, **k: seen.append((email, password))
    )
    result = runner.invoke(main.app, ["login"])
    assert result.exit_code == 0
    assert seen == [("user@example.com", "s3cret-pass")]
    assert "s3cret-pass" not in result.output
    assert "user@example.com" not in result.output


def test_login_429_shows_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["user@example.com", "s3cret-pass"])
    monkeypatch.setattr(main, "getpass", lambda _="": next(answers))

    def too_many(*a: Any, **k: Any) -> None:
        raise GarminError("Garmin вернул 429 (слишком много запросов или логинов).")

    monkeypatch.setattr(main, "full_login", too_many)
    result = runner.invoke(main.app, ["login"])
    assert result.exit_code == 1
    assert "429" in result.output
    assert "s3cret-pass" not in result.output
    assert "Traceback" not in result.output


def fit_copy(tmp_path: Path, source: str, name: str) -> Path:
    target = tmp_path / name
    shutil.copy(FIXTURES / source, target)
    return target


def test_import_fit_saves_activity(isolated: Path, tmp_path: Path) -> None:
    path = fit_copy(tmp_path, "synthetic_run.fit", "9000000002_ACTIVITY.fit")
    result = runner.invoke(main.app, ["import", str(path)])
    assert result.exit_code == 0
    conn = open_db(isolated)
    row = conn.execute("SELECT * FROM activities WHERE activity_id = 9000000002").fetchone()
    conn.close()
    assert row["type_key"] == "running"
    assert row["start_time_gmt"] == "2026-03-10 06:57:32"
    assert row["start_time_local"] == "2026-03-10 11:57:32"
    assert row["duration_s"] == 1750.0
    assert row["distance_m"] == 5000.0
    assert row["calories"] == 320
    assert row["avg_hr"] == 140
    assert row["max_hr"] == 170
    assert row["raw_json"]


def test_import_fit_writes_sync_log(isolated: Path, tmp_path: Path) -> None:
    path = fit_copy(tmp_path, "synthetic_run.fit", "9000000002_ACTIVITY.fit")
    runner.invoke(main.app, ["import", str(path)])
    rows = sync_log(isolated)
    assert [(r["kind"], r["status"]) for r in rows] == [("import", "ok")]


def test_import_fit_twice_does_not_change_database(isolated: Path, tmp_path: Path) -> None:
    path = fit_copy(tmp_path, "synthetic_run.fit", "9000000002_ACTIVITY.fit")
    runner.invoke(main.app, ["import", str(path)])
    first = snapshot(isolated)
    result = runner.invoke(main.app, ["import", str(path)])
    assert result.exit_code == 0
    assert snapshot(isolated) == first


def test_import_fit_saves_strength_sets_with_wkt_step_index(isolated: Path, tmp_path: Path) -> None:
    path = fit_copy(tmp_path, "synthetic_strength.fit", "9000000003_ACTIVITY.fit")
    result = runner.invoke(main.app, ["import", str(path)])
    assert result.exit_code == 0
    conn = open_db(isolated)
    sets = conn.execute(
        "SELECT * FROM strength_sets WHERE activity_id = 9000000003 ORDER BY set_index"
    ).fetchall()
    conn.close()
    assert [s["wkt_step_index"] for s in sets] == [1, 2, 3]
    assert [s["reps"] for s in sets] == [10, 0, 8]
    assert [s["weight"] for s in sets][0] == 40.0
    assert [s["set_type"] for s in sets] == ["active", "rest", "active"]


def test_import_does_not_overwrite_activity_from_sync(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, FakeGarmin())
    runner.invoke(main.app, ["sync", "--days", "1"])
    before = snapshot(isolated)
    path = fit_copy(tmp_path, "synthetic_strength.fit", "9000000001_ACTIVITY.fit")
    result = runner.invoke(main.app, ["import", str(path)])
    assert result.exit_code == 0
    assert snapshot(isolated) == before


def test_import_broken_file_shows_clear_error_and_keeps_database(
    isolated: Path, tmp_path: Path
) -> None:
    path = tmp_path / "9000000004_ACTIVITY.fit"
    path.write_bytes(b"not a fit file at all")
    result = runner.invoke(main.app, ["import", str(path)])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert count(isolated, "activities") == 0


def test_import_file_without_activity_id_in_name_is_rejected(
    isolated: Path, tmp_path: Path
) -> None:
    path = fit_copy(tmp_path, "synthetic_run.fit", "run.fit")
    result = runner.invoke(main.app, ["import", str(path)])
    assert result.exit_code == 1
    assert count(isolated, "activities") == 0


def test_import_missing_file_is_clear_error(isolated: Path, tmp_path: Path) -> None:
    result = runner.invoke(main.app, ["import", str(tmp_path / "nope.fit")])
    assert result.exit_code == 1
    assert "Traceback" not in result.output


def test_login_with_working_tokens_does_not_ask_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_dir = tmp_path / "garmin"
    token_dir.mkdir()
    (token_dir / "garmin_tokens.json").write_text("{}")

    def never_asked(_: str = "") -> str:
        raise AssertionError("пароль спрашивать не нужно")

    monkeypatch.setattr(main, "getpass", never_asked)
    use_client(monkeypatch, FakeGarmin())
    result = runner.invoke(main.app, ["login"])
    assert result.exit_code == 0


def test_sync_network_error_shows_clear_error_and_keeps_database(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_client(monkeypatch, FakeGarmin())
    runner.invoke(main.app, ["sync", "--days", "2"])
    before = snapshot(isolated)
    broken = FakeGarmin(fail={"get_hrv_data": GarminConnectConnectionError("network down")})
    use_client(monkeypatch, broken)
    result = runner.invoke(main.app, ["sync", "--days", "5"])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert snapshot(isolated) == before


def test_import_fit_without_local_timestamp_takes_local_time_from_start(
    isolated: Path, tmp_path: Path
) -> None:
    path = fit_copy(tmp_path, "synthetic_no_local.fit", "9000000005_ACTIVITY.fit")
    result = runner.invoke(main.app, ["import", str(path)])
    assert result.exit_code == 0
    conn = open_db(isolated)
    row = conn.execute("SELECT * FROM activities WHERE activity_id = 9000000005").fetchone()
    conn.close()
    assert row["start_time_gmt"] == "2026-03-10 06:57:32"
    assert row["start_time_local"] == "2026-03-10 06:57:32"


def test_import_fit_without_start_time_is_clear_error(isolated: Path, tmp_path: Path) -> None:
    path = fit_copy(tmp_path, "synthetic_no_start.fit", "9000000006_ACTIVITY.fit")
    result = runner.invoke(main.app, ["import", str(path)])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert count(isolated, "activities") == 0


def put_stale_tokens(tmp_path: Path) -> None:
    token_dir = tmp_path / "garmin"
    token_dir.mkdir()
    (token_dir / "garmin_tokens.json").write_text("{}")


def test_login_with_stale_tokens_falls_back_to_full_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put_stale_tokens(tmp_path)

    def stale(*a: Any, **k: Any) -> None:
        raise GarminAuthError("Токены Garmin протухли или отклонены.")

    monkeypatch.setattr(main, "load_client", stale)
    answers = iter(["user@example.com", "s3cret-pass"])
    monkeypatch.setattr(main, "getpass", lambda _="": next(answers))
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main, "full_login", lambda email, password, *a, **k: seen.append((email, password))
    )
    result = runner.invoke(main.app, ["login"])
    assert result.exit_code == 0
    assert seen == [("user@example.com", "s3cret-pass")]
    assert "s3cret-pass" not in result.output


def test_login_with_rate_limited_tokens_does_not_start_full_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put_stale_tokens(tmp_path)

    def limited(*a: Any, **k: Any) -> None:
        raise GarminRateLimitError("Garmin вернул 429")

    def never(*a: Any, **k: Any) -> None:
        raise AssertionError("полный логин при 429 не нужен")

    monkeypatch.setattr(main, "load_client", limited)
    monkeypatch.setattr(main, "getpass", never)
    monkeypatch.setattr(main, "full_login", never)
    result = runner.invoke(main.app, ["login"])
    assert result.exit_code == 1
    assert "429" in result.output
    assert "Traceback" not in result.output


def test_login_with_stale_tokens_and_failed_full_login_is_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put_stale_tokens(tmp_path)

    def stale(*a: Any, **k: Any) -> None:
        raise GarminAuthError("Токены Garmin протухли или отклонены.")

    def bad_password(*a: Any, **k: Any) -> None:
        raise GarminAuthError("Garmin не принял логин или пароль.")

    monkeypatch.setattr(main, "load_client", stale)
    answers = iter(["user@example.com", "wrong-pass"])
    monkeypatch.setattr(main, "getpass", lambda _="": next(answers))
    monkeypatch.setattr(main, "full_login", bad_password)
    result = runner.invoke(main.app, ["login"])
    assert result.exit_code == 1
    assert "не принял" in result.output
    assert "wrong-pass" not in result.output


def add_workouts(dates: list[str]) -> None:
    conn = open_db()
    try:
        for d in dates:
            add_planned_workout(
                conn, {"date": d, "sport": "run", "name": f"w{d}", "workout_json": {}}
            )
        conn.commit()
    finally:
        conn.close()


def test_status_without_options_shows_all(isolated: Path) -> None:
    add_workouts(["2026-03-01", "2026-03-10", "2026-04-01"])
    out = runner.invoke(main.app, ["status"]).output
    assert "w2026-03-01" in out
    assert "w2026-03-10" in out
    assert "w2026-04-01" in out


def test_status_date_shows_only_that_day(isolated: Path) -> None:
    add_workouts(["2026-03-09", "2026-03-10", "2026-03-11"])
    out = runner.invoke(main.app, ["status", "--date", "2026-03-10"]).output
    assert "w2026-03-10" in out
    assert "w2026-03-09" not in out
    assert "w2026-03-11" not in out


def test_status_from_without_to(isolated: Path) -> None:
    add_workouts(["2026-03-09", "2026-03-10", "2026-03-11"])
    out = runner.invoke(main.app, ["status", "--from", "2026-03-10"]).output
    assert "w2026-03-09" not in out
    assert "w2026-03-10" in out
    assert "w2026-03-11" in out


def test_status_to_without_from(isolated: Path) -> None:
    add_workouts(["2026-03-09", "2026-03-10", "2026-03-11"])
    out = runner.invoke(main.app, ["status", "--to", "2026-03-10"]).output
    assert "w2026-03-09" in out
    assert "w2026-03-10" in out
    assert "w2026-03-11" not in out


def test_status_range_includes_both_borders(isolated: Path) -> None:
    add_workouts(["2026-03-09", "2026-03-10", "2026-03-11", "2026-03-12"])
    out = runner.invoke(main.app, ["status", "--from", "2026-03-10", "--to", "2026-03-11"]).output
    assert "w2026-03-09" not in out
    assert "w2026-03-10" in out
    assert "w2026-03-11" in out
    assert "w2026-03-12" not in out


def test_status_empty_period_says_no_workouts(isolated: Path) -> None:
    add_workouts(["2026-03-10"])
    result = runner.invoke(main.app, ["status", "--date", "2026-05-05"])
    assert result.exit_code == 0
    assert "Тренировок нет." in result.output


def test_status_date_with_from_is_error(isolated: Path) -> None:
    add_workouts(["2026-03-10"])
    result = runner.invoke(main.app, ["status", "--date", "2026-03-10", "--from", "2026-03-01"])
    assert result.exit_code == 1
    assert "нельзя вместе" in result.output
    assert "w2026-03-10" not in result.output


def test_status_date_with_to_is_error(isolated: Path) -> None:
    result = runner.invoke(main.app, ["status", "--date", "2026-03-10", "--to", "2026-03-11"])
    assert result.exit_code == 1
    assert "нельзя вместе" in result.output


@pytest.mark.parametrize("option", ["--date", "--from", "--to"])
@pytest.mark.parametrize("value", ["вчера", "20261007"])
def test_status_garbage_date_is_error(isolated: Path, option: str, value: str) -> None:
    result = runner.invoke(main.app, ["status", option, value])
    assert result.exit_code == 1
    assert "YYYY-MM-DD" in result.output


def test_status_from_after_to_is_error(isolated: Path) -> None:
    add_workouts(["2026-03-10"])
    result = runner.invoke(main.app, ["status", "--from", "2026-03-11", "--to", "2026-03-10"])
    assert result.exit_code == 1
    assert "позже" in result.output
    assert "w2026-03-10" not in result.output
