from pathlib import Path
from typing import Any

import pytest
from test_plan_push import PushClient, row, status_of, workout
from test_plan_push_failures import FailingClient, use
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.store.db import open_db

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    return db


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> PushClient:
    fake = PushClient()
    monkeypatch.setattr(main, "load_client", lambda *a, **k: fake)
    return fake


def pushed(db: Path, pushed_at: str | None = None) -> int:
    return workout(db, "pushed", garmin_workout_id=11, garmin_schedule_id=22, pushed_at=pushed_at)


@pytest.mark.parametrize("status", ["draft", "approved"])
def test_cancel_unsent_goes_without_garmin(isolated: Path, client: PushClient, status: str) -> None:
    wid = workout(isolated, status)
    result = runner.invoke(main.app, ["cancel", str(wid)])
    assert result.exit_code == 0
    assert status_of(isolated, wid) == "cancelled"
    assert client.calls == []


def test_cancel_pushed_without_y_changes_nothing(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wid = pushed(isolated)
    fake = PushClient()
    loads = use(monkeypatch, fake)
    result = runner.invoke(main.app, ["cancel", str(wid)], input="n\n")
    assert "Ничего не отменено." in result.output
    assert status_of(isolated, wid) == "pushed"
    assert loads == []
    assert fake.calls == []


def test_cancel_pushed_with_y_removes_from_garmin(isolated: Path, client: PushClient) -> None:
    wid = pushed(isolated)
    result = runner.invoke(main.app, ["cancel", str(wid)], input="y\n")
    assert result.exit_code == 0
    assert client.calls == [("unschedule_workout", 22), ("delete_workout", 11)]


@pytest.mark.parametrize("flag", ["--yes", "-y"])
def test_cancel_pushed_with_yes_removes_without_stdin(
    isolated: Path, client: PushClient, flag: str
) -> None:
    wid = pushed(isolated)
    result = runner.invoke(main.app, ["cancel", str(wid), flag], input="")
    assert result.exit_code == 0
    assert "Aborted" not in result.output
    assert client.calls == [("unschedule_workout", 22), ("delete_workout", 11)]
    assert status_of(isolated, wid) == "cancelled"


def test_cancel_pushed_without_yes_and_empty_stdin_aborts(
    isolated: Path, client: PushClient
) -> None:
    wid = pushed(isolated)
    result = runner.invoke(main.app, ["cancel", str(wid)], input="")
    assert "Aborted" in result.output
    assert client.calls == []
    assert status_of(isolated, wid) == "pushed"


def test_cancel_pushed_clears_ids_keeps_pushed_at(isolated: Path, client: PushClient) -> None:
    wid = pushed(isolated, "2026-03-10T10:00:00")
    runner.invoke(main.app, ["cancel", str(wid)], input="y\n")
    saved = row(isolated, wid)
    assert saved["status"] == "cancelled"
    assert saved["garmin_workout_id"] is None
    assert saved["garmin_schedule_id"] is None
    assert saved["pushed_at"] == "2026-03-10T10:00:00"


def test_cancel_unschedule_failure_keeps_row(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wid = pushed(isolated)
    fake = FailingClient("unschedule_workout")
    use(monkeypatch, fake)
    result = runner.invoke(main.app, ["cancel", str(wid)], input="y\n")
    assert result.exit_code != 0
    saved = row(isolated, wid)
    assert saved["status"] == "pushed"
    assert (saved["garmin_workout_id"], saved["garmin_schedule_id"]) == (11, 22)
    assert "Копия осталась в Garmin: workoutId=11, scheduleId=22." in result.output
    assert "delete_workout" not in fake.names()


def test_cancel_delete_failure_keeps_row(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wid = pushed(isolated)
    use(monkeypatch, FailingClient("delete_workout"))
    result = runner.invoke(main.app, ["cancel", str(wid)], input="y\n")
    assert result.exit_code != 0
    assert status_of(isolated, wid) == "pushed"
    assert "снята с календаря, но шаблон" in result.output
    assert "не удалён" in result.output


def test_cancel_already_cancelled_fails(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "cancelled")
    result = runner.invoke(main.app, ["cancel", str(wid)])
    assert result.exit_code != 0
    assert "уже отменена" in result.output
    assert status_of(isolated, wid) == "cancelled"
    assert client.calls == []


def test_cancel_pushed_without_garmin_ids_skips_garmin(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wid = workout(isolated, "pushed")
    fake = PushClient()
    loads = use(monkeypatch, fake)
    result = runner.invoke(main.app, ["cancel", str(wid)])
    assert result.exit_code == 0
    assert f"Тренировка {wid} отменена." in result.output
    assert status_of(isolated, wid) == "cancelled"
    assert loads == []
    assert fake.calls == []


def test_cancel_unknown_id_fails(isolated: Path, client: PushClient) -> None:
    result = runner.invoke(main.app, ["cancel", "999"])
    assert result.exit_code != 0
    assert "Тренировки 999 нет." in result.output
    assert client.calls == []


def item_status(db: Path, wid: int) -> str | None:
    conn = open_db(db)
    try:
        found = conn.execute(
            "SELECT status FROM decision_log WHERE kind = 'workout' AND ref_id = ?", (wid,)
        ).fetchone()
        return found[0] if found else None
    finally:
        conn.close()


def track_item(db: Path, wid: int, close_as: str | None = None) -> None:
    from ai_coach.decisions import settle, track

    conn = open_db(db)
    try:
        track(conn, "workout", wid, "Бег лёгкий", "2026-03-12")
        if close_as is not None:
            settle(conn, "workout", wid, close_as)
        conn.commit()
    finally:
        conn.close()


def test_cancel_draft_closes_item_with_no(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "draft")
    track_item(isolated, wid)
    assert runner.invoke(main.app, ["cancel", str(wid)]).exit_code == 0
    assert item_status(isolated, wid) == "no"


@pytest.mark.parametrize("status", ["approved", "pushed"])
def test_cancel_sent_keeps_closed_item_yes(isolated: Path, client: PushClient, status: str) -> None:
    ids: dict[str, Any] = (
        {"garmin_workout_id": 11, "garmin_schedule_id": 22} if status == "pushed" else {}
    )
    wid = workout(isolated, status, **ids)
    track_item(isolated, wid, close_as="yes")
    assert runner.invoke(main.app, ["cancel", str(wid), "--yes"]).exit_code == 0
    assert item_status(isolated, wid) == "yes"


def test_cancel_shows_date_and_name_before_question(isolated: Path, client: PushClient) -> None:
    wid = workout(
        isolated,
        "pushed",
        date="2026-04-05",
        name="Длинный бег",
        garmin_workout_id=11,
        garmin_schedule_id=22,
    )
    result = runner.invoke(main.app, ["cancel", str(wid)], input="n\n")
    assert "2026-04-05" in result.output
    assert "Длинный бег" in result.output
