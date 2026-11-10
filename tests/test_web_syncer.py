"""Синк из пульта: поток-демон, один запуск за раз, статус (шаг П4, партия 3)."""

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
