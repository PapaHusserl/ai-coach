"""Сон и HRV из zip-экспорта Garmin -> ряды daily_metrics."""

import json
import zipfile
from typing import Any

from ai_coach.sync.garmin_sync import obj

WELLNESS = "DI_CONNECT/DI-Connect-Wellness/"


def read_json(archive: zipfile.ZipFile, name: str) -> list[Any]:
    return json.loads(archive.read(name))


def names(archive: zipfile.ZipFile, folder: str, suffix: str) -> list[str]:
    return sorted(n for n in archive.namelist() if n.startswith(folder) and n.endswith(suffix))


def day_of(days: dict[str, dict[str, Any]], date: str) -> dict[str, Any]:
    return days.setdefault(date, {"date": date, "raw": {}})


def add_sleep(days: dict[str, dict[str, Any]], item: dict[str, Any]) -> None:
    day = day_of(days, item["calendarDate"])
    day["sleep_seconds"] = (
        (item.get("deepSleepSeconds") or 0)
        + (item.get("lightSleepSeconds") or 0)
        + (item.get("remSleepSeconds") or 0)
    )
    day["sleep_score"] = obj(item.get("sleepScores")).get("overallScore")
    day["raw"]["sleep"] = dict(item)


def add_hrv(days: dict[str, dict[str, Any]], item: dict[str, Any]) -> None:
    for metric in item.get("metrics", []):
        if metric.get("type") == "HRV":
            day = day_of(days, item["calendarDate"])
            day["hrv_last_night"] = metric.get("value")
            day["hrv_status"] = metric.get("status")
            day["raw"]["hrv"] = item
        if metric.get("type") == "HR":
            # ночной пульс покоя (48-77, как restingHeartRate из sync): кладём туда,
            # откуда его читает last_rest_hr
            day = day_of(days, item["calendarDate"])
            day["raw"].setdefault("sleep", {})["restingHeartRate"] = metric.get("value")


def read_days(archive: zipfile.ZipFile) -> dict[str, dict[str, Any]]:
    """Один ряд daily_metrics на дату: сон и HRV одного дня сливаются.
    Элементы без calendarDate (в экспорте бывают, только с retro) пропускаются."""
    days: dict[str, dict[str, Any]] = {}
    for name in names(archive, WELLNESS, "_sleepData.json"):
        for item in read_json(archive, name):
            if "calendarDate" in item:
                add_sleep(days, item)
    for name in names(archive, WELLNESS, "_healthStatusData.json"):
        for item in read_json(archive, name):
            if "calendarDate" in item:
                add_hrv(days, item)
    return days
