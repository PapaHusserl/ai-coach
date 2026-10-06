from pathlib import Path
from typing import Any

import pytest
from garminconnect import GarminConnectConnectionError
from test_plan_push import PushClient, row, workout
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.workouts import build_workout, describe_workout

runner = CliRunner()


class FailingClient(PushClient):
    def __init__(self, fail: str) -> None:
        super().__init__()
        self.fail = fail

    def _maybe(self, name: str) -> None:
        if name == self.fail:
            raise GarminConnectConnectionError("boom")

    def upload_workout(self, workout: Any) -> dict[str, Any]:
        self._maybe("upload_workout")
        return super().upload_workout(workout)

    def schedule_workout(self, workout_id: int, date: str) -> dict[str, Any]:
        self._maybe("schedule_workout")
        return super().schedule_workout(workout_id, date)

    def unschedule_workout(self, schedule_id: int) -> Any:
        self._maybe("unschedule_workout")
        return super().unschedule_workout(schedule_id)

    def delete_workout(self, workout_id: int) -> Any:
        self._maybe("delete_workout")
        return super().delete_workout(workout_id)


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    return db


def use(monkeypatch: pytest.MonkeyPatch, client: PushClient) -> list[int]:
    loads: list[int] = []

    def load(*a: Any, **k: Any) -> PushClient:
        loads.append(1)
        return client

    monkeypatch.setattr(main, "load_client", load)
    return loads


def test_load_client_not_called_on_no(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wid = workout(isolated, "approved")
    loads = use(monkeypatch, PushClient())
    runner.invoke(main.app, ["push", str(wid)], input="n\n")
    assert loads == []


@pytest.mark.parametrize("method", ["upload_workout", "schedule_workout"])
def test_first_push_failure_keeps_row(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    wid = workout(isolated, "approved")
    use(monkeypatch, FailingClient(method))
    result = runner.invoke(main.app, ["push", str(wid)], input="y\n")
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    saved = row(isolated, wid)
    assert saved["status"] == "approved"
    assert saved["garmin_workout_id"] is None
    assert saved["pushed_at"] is None


def test_schedule_failure_names_uploaded_template(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wid = workout(isolated, "approved")
    use(monkeypatch, FailingClient("schedule_workout"))
    result = runner.invoke(main.app, ["push", str(wid)], input="y\n")
    assert "workoutId=1001" in result.output


def test_repush_after_schedule_failure_still_replaces_old(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    use(monkeypatch, FailingClient("schedule_workout"))
    runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    saved = row(isolated, wid)
    assert (saved["garmin_workout_id"], saved["garmin_schedule_id"]) == (11, 22)
    good = PushClient()
    use(monkeypatch, good)
    result = runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    assert result.exit_code == 0
    assert ("delete_workout", 11) in good.calls
    assert row(isolated, wid)["garmin_workout_id"] == 1001


def test_repush_uploads_new_before_removing_old(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    client = PushClient()
    use(monkeypatch, client)
    runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    assert client.names() == [
        "upload_workout",
        "schedule_workout",
        "unschedule_workout",
        "delete_workout",
    ]


@pytest.mark.parametrize("method", ["unschedule_workout", "delete_workout"])
def test_old_removal_failure_reports_old_ids(
    isolated: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    use(monkeypatch, FailingClient(method))
    result = runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "workoutId=11" in result.output
    saved = row(isolated, wid)
    assert saved["status"] == "pushed"
    assert saved["garmin_workout_id"] == 1001


def test_upload_failure_on_repush_keeps_old_untouched(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    client = FailingClient("upload_workout")
    use(monkeypatch, client)
    result = runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    assert result.exit_code == 1
    assert client.calls == []
    assert row(isolated, wid)["garmin_workout_id"] == 11


def test_describe_shows_pace_per_km() -> None:
    spec = {
        "name": "Бег",
        "steps": [{"type": "interval", "seconds": 600, "pace_sec_per_km": [390, 330]}],
    }
    text = describe_workout(build_workout("run", spec))
    assert "6:30-5:30/км" in text
