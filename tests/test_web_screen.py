"""GET /api/screen: часы экрана за день пункта, живое чтение ActivityWatch (шаг П6)."""

from datetime import date, datetime
from pathlib import Path

import pytest
from workload_fakes import FakeAw, write_config

from ai_coach.store.db import open_db
from ai_coach.web import screen
from ai_coach.workload.screen import ScreenError

HOUR = 3600
DAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 21, 0)
SCREEN = '[screen]\nwork = ["Alpha Editor"]\nhobby = ["BetaGame"]\nbrowser = ["Gamma Browser"]\n'


@pytest.fixture(autouse=True)
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = write_config(tmp_path / "w.toml", SCREEN)
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(path))
    return path


def use_aw(monkeypatch: pytest.MonkeyPatch, aw: FakeAw) -> FakeAw:
    monkeypatch.setattr(screen, "AwReader", lambda config: aw)
    return aw


def day_of(work: float, hobby: float) -> dict[str, tuple[dict[tuple[str, str], float], dict]]:
    whole = {("alpha editor", ""): work * HOUR, ("betagame", ""): hobby * HOUR}
    return {"2026-11-13": (whole, {})}


def test_screen_view_gives_hours(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_aw(monkeypatch, FakeAw(day_of(work=4.2, hobby=0.8)))
    conn = open_db(tmp_path / "coach.db")
    try:
        view = screen.screen_view(conn, DAY, NOW)
    finally:
        conn.close()
    assert view == {"work": 4.2, "hobby": 0.8, "browser": 0.0}


def test_screen_view_without_screen_section_is_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_config(tmp_path / "no-screen.toml", '[calendar]\nwork = ["Work"]\n')
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(path))
    aw = use_aw(monkeypatch, FakeAw(day_of(4, 1)))
    conn = open_db(tmp_path / "coach.db")
    try:
        assert screen.screen_view(conn, DAY, NOW) == {"missing": "config"}
    finally:
        conn.close()
    assert aw.calls == []


def test_screen_view_broken_config_is_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_config(tmp_path / "broken.toml", "[screen\nwork = ")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(path))
    use_aw(monkeypatch, FakeAw(day_of(4, 1)))
    conn = open_db(tmp_path / "coach.db")
    try:
        assert screen.screen_view(conn, DAY, NOW) == {"missing": "config"}
    finally:
        conn.close()


def test_screen_view_screen_error_is_missing_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_aw(monkeypatch, FakeAw(error=ScreenError("aw-server не отвечает")))
    conn = open_db(tmp_path / "coach.db")
    try:
        assert screen.screen_view(conn, DAY, NOW) == {"missing": "silent"}
    finally:
        conn.close()


def test_screen_view_day_without_window_events_is_missing_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_aw(monkeypatch, FakeAw())
    conn = open_db(tmp_path / "coach.db")
    try:
        assert screen.screen_view(conn, DAY, NOW) == {"missing": "empty"}
    finally:
        conn.close()


def test_screen_view_past_day_asks_for_that_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aw = use_aw(monkeypatch, FakeAw())
    conn = open_db(tmp_path / "coach.db")
    try:
        screen.screen_view(conn, date(2026, 11, 12), NOW)
    finally:
        conn.close()
    start, end = aw.calls[0][0]
    assert (start.date(), start.hour) == (date(2026, 11, 12), 4)
    assert (end.date(), end.hour) == (date(2026, 11, 13), 4)
    assert len(aw.calls[0]) == 2


def test_screen_view_gives_reader_the_screen_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    given: list[object] = []

    def reader(config: object) -> FakeAw:
        given.append(config)
        return FakeAw()

    monkeypatch.setattr(screen, "AwReader", reader)
    conn = open_db(tmp_path / "coach.db")
    try:
        screen.screen_view(conn, DAY, NOW)
    finally:
        conn.close()
    assert len(given) == 1
    assert given[0].work == frozenset({"alpha editor"})  # type: ignore[attr-defined]


def test_screen_view_writes_no_counters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_aw(monkeypatch, FakeAw(day_of(work=4.2, hobby=0.8)))
    conn = open_db(tmp_path / "coach.db")
    try:
        screen.screen_view(conn, DAY, NOW)
        rows = conn.execute("SELECT * FROM day_counters").fetchall()
    finally:
        conn.close()
    assert rows == []
