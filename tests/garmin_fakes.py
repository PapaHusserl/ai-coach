"""Подмена клиента Garmin для тестов: ответы из обезличенных фикстур, сети нет."""

import json
import sqlite3
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"
GARMIN = FIXTURES / "garmin"
FIXTURE_DAY = "2026-03-10"
RUN_ID = 9000000002


def load(name: str) -> Any:
    return json.loads((GARMIN / name).read_text(encoding="utf-8"))


def for_day(data: Any, day: str) -> Any:
    """Переносит фикстуру дня 2026-03-10 на другую дату."""
    return json.loads(json.dumps(data).replace(FIXTURE_DAY, day))


class FakeGarmin:
    """Методы повторяют garminconnect.Garmin.

    empty: {метод: набор дат}, на которых Garmin отвечает пусто (как в реальных днях без данных).
    missing: {метод: набор дат}, на которых Garmin отвечает 404.
    fail: {метод: исключение}, которое метод бросает при любом вызове.
    """

    def __init__(
        self,
        empty: dict[str, set[str]] | None = None,
        missing: dict[str, set[str]] | None = None,
        fail: dict[str, Exception] | None = None,
        with_run: bool = False,
    ) -> None:
        self.empty = empty or {}
        self.missing = missing or {}
        self.fail = fail or {}
        self.with_run = with_run
        self.calls: list[tuple[str, Any]] = []
        self.activities = load("activities_list.json")
        self.sets = load("activity_sets.json")
        self.lactate = load("lactate_threshold.json")

    def _enter(self, method: str, day: str) -> bool:
        self.calls.append((method, day))
        if method in self.fail:
            raise self.fail[method]
        if day in self.missing.get(method, set()):
            from garminconnect import GarminConnectNotFoundError

            raise GarminConnectNotFoundError("404")
        return day in self.empty.get(method, set())

    def get_sleep_data(self, cdate: str) -> Any:
        return (
            {}
            if self._enter("get_sleep_data", cdate)
            else for_day(load("sleep_2026-03-10.json"), cdate)
        )

    def get_hrv_data(self, cdate: str) -> Any:
        return (
            None
            if self._enter("get_hrv_data", cdate)
            else for_day(load("hrv_2026-03-10.json"), cdate)
        )

    def get_stress_data(self, cdate: str) -> Any:
        return (
            {}
            if self._enter("get_stress_data", cdate)
            else for_day(load("stress_2026-03-10.json"), cdate)
        )

    def get_body_battery(self, startdate: str, enddate: str | None = None) -> Any:
        if self._enter("get_body_battery", startdate):
            return []
        return for_day(load("body_battery_2026-03-10.json"), startdate)

    def get_training_readiness(self, cdate: str) -> Any:
        if self._enter("get_training_readiness", cdate):
            return []
        return for_day(load("training_readiness_2026-03-10.json"), cdate)

    def get_lactate_threshold(self, *, latest: bool = True) -> Any:
        self.calls.append(("get_lactate_threshold", latest))
        if "get_lactate_threshold" in self.fail:
            raise self.fail["get_lactate_threshold"]
        return self.lactate

    def get_activities_by_date(
        self, startdate: str, enddate: str | None = None, *a: Any, **k: Any
    ) -> Any:
        self.calls.append(("get_activities_by_date", (startdate, enddate)))
        if "get_activities_by_date" in self.fail:
            raise self.fail["get_activities_by_date"]
        end = enddate or startdate
        # активность «случилась» в последний день запрошенного периода
        found = [for_day(a, end) for a in self.activities]
        if self.with_run:
            run = for_day(self.activities[0], end)
            run.update(activityId=RUN_ID, activityName="Бег")
            run["activityType"]["typeKey"] = "running"
            found.append(run)
        return found

    def get_activity_exercise_sets(self, activity_id: int | str) -> Any:
        self.calls.append(("get_activity_exercise_sets", int(activity_id)))
        if "get_activity_exercise_sets" in self.fail:
            raise self.fail["get_activity_exercise_sets"]
        return self.sets


def snapshot(path: Path) -> dict[str, list[tuple[Any, ...]]]:
    """Содержимое базы (кроме sync_log), прочитанное новым соединением — только закоммиченное."""
    conn = sqlite3.connect(path)
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'sync_log'"
            )
        ]
        return {n: conn.execute(f"SELECT * FROM {n} ORDER BY 1, 2").fetchall() for n in names}
    finally:
        conn.close()


def sync_log(path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM sync_log ORDER BY id")]
    finally:
        conn.close()
