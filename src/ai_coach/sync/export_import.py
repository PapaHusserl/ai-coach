"""Импорт zip-экспорта Garmin Connect в базу (без сети): активности, сон, HRV.

Экспорт только добавляет: дни и активности, которые уже есть в базе (из sync), не меняются.
Архив читается в памяти, на диск не распаковывается.
"""

import io
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitdecode  # pyright: ignore[reportMissingTypeStubs]

from ai_coach.store.garmin_data import (
    get_activity,
    get_daily_metrics,
    upsert_activity,
    upsert_daily_metrics,
    upsert_strength_set,
)
from ai_coach.store.journal import add_sync_log
from ai_coach.sync.export_days import WELLNESS, names, read_days, read_json
from ai_coach.sync.fit_import import FitImportError, activity_row, collect_messages, set_row
from ai_coach.sync.jsonutil import dump

UPLOADED = "DI_CONNECT/DI-Connect-Uploaded-Files/"
FITNESS = "DI_CONNECT/DI-Connect-Fitness/"
EXPORT_FOLDERS = (UPLOADED, FITNESS, WELLNESS)


@dataclass
class ExportImportResult:
    activities_added: int = 0
    activities_skipped: int = 0
    activities_unmatched: int = 0
    days_added: int = 0
    days_skipped: int = 0
    fit_unreadable: int = 0


def activity_ids(archive: zipfile.ZipFile) -> dict[int, int]:
    """startTimeGmt (секунды) -> activityId из summarizedActivities."""
    ids: dict[int, int] = {}
    for name in names(archive, FITNESS, "_summarizedActivities.json"):
        for item in read_json(archive, name)[0]["summarizedActivitiesExport"]:
            ids[int(item["startTimeGmt"]) // 1000] = item["activityId"]
    return ids


def activity_fits(
    archive: zipfile.ZipFile,
) -> tuple[list[dict[str, list[dict[str, Any]]]], int]:
    """Сообщения всех FIT-активностей из вложенных zip (остальные FIT пропускаются)
    и число нечитаемых FIT."""
    unreadable = 0
    result: list[dict[str, list[dict[str, Any]]]] = []
    for name in names(archive, UPLOADED, ".zip"):
        with zipfile.ZipFile(io.BytesIO(archive.read(name))) as inner:
            for fit in inner.namelist():
                if not fit.lower().endswith(".fit"):
                    continue
                try:
                    messages = collect_messages(io.BytesIO(inner.read(fit)), only_activity=True)
                except fitdecode.FitError:
                    unreadable += 1
                    continue
                file_id = messages.get("file_id", [{}])[0]
                if file_id.get("type") == "activity" and "session" in messages:
                    result.append(messages)
    return result, unreadable


def read_activities(
    archive: zipfile.ZipFile,
) -> tuple[dict[int, tuple[dict[str, Any], list[dict[str, Any]]]], int, int]:
    """Активности по activityId (строка, подходы), число несопоставленных и нечитаемых FIT."""
    ids = activity_ids(archive)
    found: dict[int, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    unmatched = 0
    fits, unreadable = activity_fits(archive)
    for messages in fits:
        start = messages["session"][0].get("start_time")
        if start is None:
            unmatched += 1
            continue
        activity_id = ids.get(int(start.replace(tzinfo=UTC).timestamp()))
        if activity_id is None:
            unmatched += 1
            continue
        sets = [set_row(activity_id, s) for s in messages.get("set", [])]
        found[activity_id] = (activity_row(activity_id, messages), sets)
    return found, unmatched, unreadable


def import_export(conn: sqlite3.Connection, path: Path) -> ExportImportResult:
    """Читает zip-экспорт, добавляет отсутствующие активности и дни одной транзакцией."""
    started = datetime.now().isoformat(timespec="seconds")
    try:
        with zipfile.ZipFile(path) as archive:
            if not any(n.startswith(EXPORT_FOLDERS) for n in archive.namelist()):
                raise FitImportError("Это не zip-экспорт Garmin Connect")
            activities, unmatched, unreadable = read_activities(archive)
            days = read_days(archive)
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        raise FitImportError("Файл не читается как zip-экспорт Garmin Connect") from e
    result = ExportImportResult(activities_unmatched=unmatched, fit_unreadable=unreadable)
    with conn:
        for activity_id, (row, sets) in activities.items():
            if get_activity(conn, activity_id) is not None:
                result.activities_skipped += 1
                continue
            upsert_activity(conn, row)
            for set_values in sets:
                upsert_strength_set(conn, set_values)
            result.activities_added += 1
        for date, day in days.items():
            if get_daily_metrics(conn, date) is not None:
                result.days_skipped += 1
                continue
            values = {k: v for k, v in day.items() if k != "raw"}
            values["raw_json"] = dump(day["raw"])
            upsert_daily_metrics(conn, values)
            result.days_added += 1
        add_sync_log(
            conn,
            {
                "started_at": started,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "kind": "import",
                "status": "ok",
                "message": summary(result),
            },
        )
    return result


def summary(result: ExportImportResult) -> str:
    return (
        f"активностей добавлено {result.activities_added}, "
        f"пропущено (уже в базе) {result.activities_skipped}, "
        f"не сопоставлено {result.activities_unmatched}, "
        f"нечитаемых FIT {result.fit_unreadable}; "
        f"дней добавлено {result.days_added}, пропущено (уже в базе) {result.days_skipped}"
    )
