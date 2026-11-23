"""Синк из пульта: поток-демон, один запуск за раз, статус (шаг П4, партия 3)."""

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from garmin_fakes import FakeGarmin
from workload_fakes import FakeCalendar

from ai_coach.garmin.client import GarminAuthError
from ai_coach.store.db import open_db
from ai_coach.store.journal import last_sync_log
from ai_coach.sync import workload_sync
from ai_coach.web import syncer

WAIT = 5.0
REAL_SLEEP = (
    time.sleep
)  # настоящий: тесты подменяют time.sleep, а ожидание без паузы душит поток синка


def wait_idle() -> None:
    deadline = time.monotonic() + WAIT
    while syncer.status()["running"]:
        assert time.monotonic() < deadline, "синк не закончился"
        REAL_SLEEP(0.01)


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(syncer, "load_client", lambda *a, **k: FakeGarmin())
    monkeypatch.setattr(workload_sync, "CalendarReader", lambda *a, **k: FakeCalendar())
    path = tmp_path / "coach.db"
    open_db(path).close()
    wait_idle()
    yield path
    wait_idle()


def test_start_runs_sync_in_background_and_logs_it(db: Path) -> None:
    assert syncer.start(db) is True
    wait_idle()
    conn = open_db(db)
    try:
        log = last_sync_log(conn)
    finally:
        conn.close()
    assert log is not None
    assert log["status"] == "ok"
    assert syncer.status()["error"] is None


def test_status_while_running_has_start_time(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()

    def slow(*a: object, **k: object) -> FakeGarmin:
        release.wait(WAIT)
        return FakeGarmin()

    monkeypatch.setattr(syncer, "load_client", slow)
    try:
        assert syncer.start(db) is True
        status = syncer.status()
        assert status["running"] is True
        assert status["started_at"]
    finally:
        release.set()
    wait_idle()
    assert syncer.status()["running"] is False


def test_second_start_while_running_is_refused(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    calls: list[int] = []

    def slow(*a: object, **k: object) -> FakeGarmin:
        calls.append(1)
        release.wait(WAIT)
        return FakeGarmin()

    monkeypatch.setattr(syncer, "load_client", slow)
    try:
        assert syncer.start(db) is True
        assert syncer.start(db) is False
    finally:
        release.set()
    wait_idle()
    assert calls == [1]


def test_start_works_again_after_finish(db: Path) -> None:
    assert syncer.start(db) is True
    wait_idle()
    assert syncer.start(db) is True
    wait_idle()


def test_garmin_auth_error_goes_to_status_error(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_tokens(*a: object, **k: object) -> None:
        raise GarminAuthError("Токенов Garmin нет. Выполни: coach login")

    monkeypatch.setattr(syncer, "load_client", no_tokens)
    assert syncer.start(db) is True
    wait_idle()
    status = syncer.status()
    assert status["running"] is False
    assert status["error"] == "Токенов Garmin нет. Выполни: coach login"


def test_garmin_auth_error_does_not_cancel_workload(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_tokens(*a: object, **k: object) -> None:
        raise GarminAuthError("Токенов Garmin нет. Выполни: coach login")

    monkeypatch.setattr(syncer, "load_client", no_tokens)
    syncer.start(db)
    wait_idle()
    conn = open_db(db)
    try:
        log = last_sync_log(conn)
    finally:
        conn.close()
    assert log is not None
    assert log["kind"] == "workload"
    assert syncer.status()["error"] == "Токенов Garmin нет. Выполни: coach login"


def test_successful_run_clears_previous_error(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_tokens(*a: object, **k: object) -> None:
        raise GarminAuthError("Токенов Garmin нет.")

    monkeypatch.setattr(syncer, "load_client", no_tokens)
    syncer.start(db)
    wait_idle()
    monkeypatch.setattr(syncer, "load_client", lambda *a, **k: FakeGarmin())
    syncer.start(db)
    wait_idle()
    assert syncer.status()["error"] is None


def test_sync_runs_over_week_with_pause(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def spy(conn: object, client: object, days: int, **kwargs: object) -> None:
        seen["days"] = days
        seen.update(kwargs)

    monkeypatch.setattr(syncer, "run_sync", spy)
    syncer.start(db)
    wait_idle()
    assert seen == {"days": 7, "pause": 0.5}


def test_unexpected_failure_goes_to_status_error(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("сбой воркера")

    monkeypatch.setattr(syncer, "run_workload", boom)
    syncer.start(db)
    wait_idle()
    status = syncer.status()
    assert status["running"] is False
    assert status["error"] == "сбой воркера"


def with_weather(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_coach import location, weather

    path = Path(__file__).parent / "fixtures" / "weather" / "open_meteo.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    monkeypatch.setattr(location, "read_place", lambda *a, **k: location.Place(52.52, 13.41))
    monkeypatch.setattr(weather, "fetch_forecast", lambda place: raw)


def kinds(db: Path) -> list[str]:
    conn = open_db(db)
    try:
        return [r["kind"] for r in conn.execute("SELECT kind FROM sync_log ORDER BY id")]
    finally:
        conn.close()


def test_run_syncs_weather_after_workload(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with_weather(monkeypatch)
    syncer.start(db)
    wait_idle()
    conn = open_db(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM weather_now").fetchone()[0] == 1
    finally:
        conn.close()
    log = kinds(db)
    assert log.index("weather") > log.index("workload")


def test_weather_failure_is_not_in_status_error(db: Path) -> None:
    syncer.start(db)
    wait_idle()
    assert "weather" in kinds(db)
    assert syncer.status()["error"] is None


def test_weather_runs_even_after_garmin_error(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_tokens(*a: object, **k: object) -> None:
        raise GarminAuthError("Токенов Garmin нет.")

    monkeypatch.setattr(syncer, "load_client", no_tokens)
    with_weather(monkeypatch)
    syncer.start(db)
    wait_idle()
    assert "weather" in kinds(db)
    assert syncer.status()["error"] == "Токенов Garmin нет."


def with_kp(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_coach import kp

    path = Path(__file__).parent / "fixtures" / "weather" / "kp.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    monkeypatch.setattr(kp, "fetch_kp", lambda: raw)


def kp_count(db: Path) -> int:
    conn = open_db(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM kp_index").fetchone()[0]
    finally:
        conn.close()


def test_run_syncs_kp_after_weather(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with_weather(monkeypatch)
    with_kp(monkeypatch)
    syncer.start(db)
    wait_idle()
    assert kp_count(db) == 81
    log = kinds(db)
    assert log.index("kp") > log.index("weather")


def test_kp_failure_is_not_in_status_error(db: Path) -> None:
    syncer.start(db)
    wait_idle()
    assert "kp" in kinds(db)
    assert syncer.status()["error"] is None


def test_kp_runs_even_after_weather_failure(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with_kp(monkeypatch)
    syncer.start(db)
    wait_idle()
    assert kp_count(db) == 81
    assert syncer.status()["error"] is None


def test_kp_runs_even_after_garmin_error(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_tokens(*a: object, **k: object) -> None:
        raise GarminAuthError("Токенов Garmin нет.")

    monkeypatch.setattr(syncer, "load_client", no_tokens)
    with_kp(monkeypatch)
    syncer.start(db)
    wait_idle()
    assert kp_count(db) == 81
    assert syncer.status()["error"] == "Токенов Garmin нет."


def test_sync_thread_is_daemon(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kwargs_seen: list[dict[str, object]] = []
    real_thread = threading.Thread

    def spy(*a: object, **k: object) -> threading.Thread:
        kwargs_seen.append(k)
        return real_thread(*a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(syncer.threading, "Thread", spy)
    syncer.start(db)
    wait_idle()
    assert [k.get("daemon") for k in kwargs_seen] == [True]


def mark_first_day(db: Path) -> str:
    """Отметка раньше любого дня фикстуры прогноза: тест не зависит от даты запуска."""
    from ai_coach.store.journal import add_wellbeing

    day = "2026-10-07"
    conn = open_db(db)
    try:
        with conn:
            values = {"date": day, "logged_at": f"{day} 09:00:00", "score": 3, "text": ""}
            add_wellbeing(conn, values)
    finally:
        conn.close()
    return day


def test_run_backfills_archive_with_the_same_call(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai_coach import weather

    with_weather(monkeypatch)
    day = mark_first_day(db)
    asked: list[str] = []

    def reader(place: object, start: str, end: str) -> dict[str, object]:
        asked.append(start)
        return {}

    monkeypatch.setattr(weather, "fetch_archive", reader)
    syncer.start(db)
    wait_idle()
    assert asked == [day] == ["2026-10-07"]
    assert "weather_archive" in kinds(db)


def test_archive_failure_is_not_in_status_error(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_coach import weather

    with_weather(monkeypatch)
    mark_first_day(db)

    def broken(*a: object, **k: object) -> None:
        raise weather.WeatherError("архив не ответил")

    monkeypatch.setattr(weather, "fetch_archive", broken)
    syncer.start(db)
    wait_idle()
    conn = open_db(db)
    try:
        row = conn.execute("SELECT status FROM sync_log WHERE kind = 'weather_archive'").fetchone()
    finally:
        conn.close()
    assert row["status"] == "error"
    assert syncer.status()["error"] is None
