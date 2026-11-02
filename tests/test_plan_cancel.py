from pathlib import Path

import pytest
from test_plan_push import PushClient, row, status_of, workout
from test_plan_push_failures import FailingClient, use
from typer.testing import CliRunner

from ai_coach.cli import main

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
