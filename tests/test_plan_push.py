import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.plan import PlanError, approve
from ai_coach.store.db import open_db
from ai_coach.store.plans import add_planned_workout, get_planned_workout

runner = CliRunner()


class PushClient:
    """Подмена клиента Garmin: ничего не ходит в сеть, все вызовы записываются."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.next_id = 1000

    def upload_workout(self, workout: Any) -> dict[str, Any]:
        self.calls.append(("upload_workout", workout))
        self.next_id += 1
        return {"workoutId": self.next_id}

    def schedule_workout(self, workout_id: int, date: str) -> dict[str, Any]:
        self.calls.append(("schedule_workout", (workout_id, date)))
        self.next_id += 1
        return {"workoutScheduleId": self.next_id}

    def unschedule_workout(self, schedule_id: int) -> Any:
        self.calls.append(("unschedule_workout", schedule_id))
        return {}

    def delete_workout(self, workout_id: int) -> Any:
        self.calls.append(("delete_workout", workout_id))
        return {}

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]


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


def workout(
    db: Path,
    status: str = "draft",
    date: str = "2026-03-12",
    name: str = "Бег лёгкий",
    **extra: Any,
) -> int:
    values = {
        "date": date,
        "sport": "run",
        "name": name,
        "status": status,
        "workout_json": {"name": name, "steps": [{"type": "interval", "seconds": 600}]},
        **extra,
    }
    conn = open_db(db)
    try:
        wid = add_planned_workout(conn, values)
        conn.commit()
        return wid
    finally:
        conn.close()


def row(db: Path, wid: int) -> dict[str, Any]:
    conn = open_db(db)
    try:
        found = get_planned_workout(conn, wid)
        assert found is not None
        return found
    finally:
        conn.close()


def status_of(db: Path, wid: int) -> str:
    return row(db, wid)["status"]


# переходы статусов


def test_approve_moves_draft_to_approved(isolated: Path) -> None:
    wid = workout(isolated, "draft")
    conn = open_db(isolated)
    approve(conn, wid)
    conn.commit()
    conn.close()
    assert status_of(isolated, wid) == "approved"


@pytest.mark.parametrize("status", ["approved", "pushed", "cancelled"])
def test_approve_only_from_draft(isolated: Path, status: str) -> None:
    wid = workout(isolated, status)
    conn = open_db(isolated)
    with pytest.raises(PlanError):
        approve(conn, wid)
    conn.close()
    assert status_of(isolated, wid) == status


def test_approve_unknown_workout_fails(conn: sqlite3.Connection) -> None:
    with pytest.raises(PlanError):
        approve(conn, 999)


@pytest.mark.parametrize("status", ["draft", "cancelled"])
def test_push_refuses_not_approved(isolated: Path, client: PushClient, status: str) -> None:
    wid = workout(isolated, status)
    result = runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    assert result.exit_code != 0
    assert client.calls == []
    assert status_of(isolated, wid) == status


def test_push_unknown_id_fails_without_calls(isolated: Path, client: PushClient) -> None:
    result = runner.invoke(main.app, ["push", "999"], input="y\n")
    assert result.exit_code != 0
    assert client.calls == []


# push


def test_push_prints_what_it_sends(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "approved", name="Бег лёгкий")
    result = runner.invoke(main.app, ["push", str(wid)], input="n\n")
    assert "Бег лёгкий" in result.output
    assert "2026-03-12" in result.output


@pytest.mark.parametrize("answer", ["n\n", "\n", "yes please\n", ""])
def test_push_without_y_sends_nothing(isolated: Path, client: PushClient, answer: str) -> None:
    wid = workout(isolated, "approved")
    runner.invoke(main.app, ["push", str(wid)], input=answer)
    assert client.calls == []
    assert status_of(isolated, wid) == "approved"


def test_push_with_y_uploads_and_schedules_on_date(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "approved", date="2026-03-12")
    result = runner.invoke(main.app, ["push", str(wid)], input="y\n")
    assert result.exit_code == 0
    assert client.names() == ["upload_workout", "schedule_workout"]
    assert client.calls[1][1] == (1001, "2026-03-12")


def test_push_saves_garmin_ids_and_status(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "approved")
    runner.invoke(main.app, ["push", str(wid)], input="y\n")
    saved = row(isolated, wid)
    assert saved["status"] == "pushed"
    assert saved["garmin_workout_id"] == 1001
    assert saved["garmin_schedule_id"] == 1002
    assert saved["pushed_at"] is not None


def test_first_push_deletes_nothing(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "approved")
    runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    assert "delete_workout" not in client.names()
    assert "unschedule_workout" not in client.names()


# повторный push


def test_repush_without_first_y_changes_nothing(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    runner.invoke(main.app, ["push", str(wid)], input="n\n")
    assert client.calls == []
    saved = row(isolated, wid)
    assert (saved["garmin_workout_id"], saved["garmin_schedule_id"]) == (11, 22)


def test_repush_shows_what_will_be_deleted(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    result = runner.invoke(main.app, ["push", str(wid)], input="y\nn\n")
    assert "11" in result.output


def test_repush_without_second_y_deletes_nothing(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    runner.invoke(main.app, ["push", str(wid)], input="y\nn\n")
    assert "unschedule_workout" not in client.names()
    assert "delete_workout" not in client.names()


def test_repush_with_two_y_replaces_old_workout(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    result = runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    assert result.exit_code == 0
    assert ("unschedule_workout", 22) in client.calls
    assert ("delete_workout", 11) in client.calls
    assert "upload_workout" in client.names()
    assert "schedule_workout" in client.names()


def test_repush_unschedules_before_deleting(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    assert client.names().index("unschedule_workout") < client.names().index("delete_workout")


def test_repush_updates_ids_to_new_workout(isolated: Path, client: PushClient) -> None:
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    saved = row(isolated, wid)
    assert saved["status"] == "pushed"
    assert saved["garmin_workout_id"] not in (None, 11)
    assert saved["garmin_schedule_id"] not in (None, 22)


def test_repush_touches_only_own_workout(isolated: Path, client: PushClient) -> None:
    other = workout(isolated, "pushed", name="Чужая", garmin_workout_id=33, garmin_schedule_id=44)
    wid = workout(isolated, "pushed", garmin_workout_id=11, garmin_schedule_id=22)
    runner.invoke(main.app, ["push", str(wid)], input="y\ny\n")
    deleted = [c[1] for c in client.calls if c[0] in ("unschedule_workout", "delete_workout")]
    assert sorted(deleted) == [11, 22]
    saved = row(isolated, other)
    assert (saved["garmin_workout_id"], saved["garmin_schedule_id"]) == (33, 44)


# status


def test_status_lists_planned_and_pushed(isolated: Path) -> None:
    workout(isolated, "draft", name="Черновик А")
    workout(isolated, "approved", name="Одобрена Б")
    workout(isolated, "pushed", name="Отправлена В", garmin_workout_id=1, garmin_schedule_id=2)
    result = runner.invoke(main.app, ["status"])
    assert result.exit_code == 0
    for text in ("Черновик А", "Одобрена Б", "Отправлена В"):
        assert text in result.output


def test_status_shows_status_and_date(isolated: Path) -> None:
    workout(isolated, "approved", date="2026-03-14", name="Вело")
    result = runner.invoke(main.app, ["status"])
    assert "approved" in result.output
    assert "2026-03-14" in result.output


def test_status_does_not_need_garmin(isolated: Path, client: PushClient) -> None:
    workout(isolated, "approved")
    runner.invoke(main.app, ["status"])
    assert client.calls == []


def test_status_on_empty_database_is_ok(isolated: Path) -> None:
    result = runner.invoke(main.app, ["status"])
    assert result.exit_code == 0
