"""Маленький синтетический zip-экспорт Garmin Connect: та же структура, данные придуманы."""

import importlib.util
import io
import json
import struct
import zipfile
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
EMAIL = "user@example.com"
DAY = 86400

# id активностей из summarizedActivities.json
RUN_ID = 9100000001
STRENGTH_ID = 9100000002

# старты (UTC, секунды): бег и силовая есть в summarizedActivities, третья — нет
RUN_START = 1773125852
STRENGTH_START = RUN_START + DAY
UNMATCHED_START = RUN_START + 2 * DAY

# даты сна и HRV
BOTH_DAY = "2026-03-10"  # сон со score + HRV
NO_SCORE_DAY = "2026-03-11"  # сон без sleepScores
HRV_ONLY_DAY = "2026-03-12"  # только HRV
EXISTING_DAY = "2026-03-13"  # сон и HRV; в базе уже есть строка из sync


def _make_fit_module():  # noqa: ANN202
    spec = importlib.util.spec_from_file_location("make_fit", FIXTURES / "make_fit.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def activity_fit(start_unix: int, with_sets: bool = False) -> bytes:
    module = _make_fit_module()
    vars(module)["START_UNIX"] = start_unix
    return module.build(with_sets=with_sets)


def monitoring_fit() -> bytes:
    """FIT с file_id.type = monitoring_b (32): не активность."""
    module = _make_fit_module()
    body = module.definition(0, 0, [(0, 1, 0x00)]) + struct.pack("<BB", 0, 32)
    header = struct.pack("<BBHI4s", 14, 0x20, 2132, len(body), b".FIT")
    header += struct.pack("<H", module.crc16(header))
    data = header + body
    return data + struct.pack("<H", module.crc16(data))


def start_gmt_ms(start_unix: int) -> int:
    return start_unix * 1000


def summarized() -> list[dict]:  # type: ignore[type-arg]
    return [
        {
            "summarizedActivitiesExport": [
                {
                    "activityId": RUN_ID,
                    "startTimeGmt": start_gmt_ms(RUN_START),
                    "name": "Export run",
                },
                {
                    "activityId": STRENGTH_ID,
                    "startTimeGmt": start_gmt_ms(STRENGTH_START),
                    "name": "Export strength",
                },
            ]
        }
    ]


def sleep_data() -> list[dict]:  # type: ignore[type-arg]
    return [
        {
            "calendarDate": BOTH_DAY,
            "deepSleepSeconds": 3600,
            "lightSleepSeconds": 14400,
            "remSleepSeconds": 5400,
            "awakeSleepSeconds": 900,
            "sleepScores": {"overallScore": 81},
        },
        {
            "calendarDate": NO_SCORE_DAY,
            "deepSleepSeconds": 3000,
            "lightSleepSeconds": 15000,
            "remSleepSeconds": 6000,
        },
        {
            "calendarDate": EXISTING_DAY,
            "deepSleepSeconds": 1000,
            "lightSleepSeconds": 1000,
            "remSleepSeconds": 1000,
            "sleepScores": {"overallScore": 50},
        },
    ]


def health_status() -> list[dict]:  # type: ignore[type-arg]
    def day(date: str, value: int, status: str) -> dict:  # type: ignore[type-arg]
        return {
            "calendarDate": date,
            "metrics": [
                {"type": "HR", "value": 52, "status": "IN_RANGE"},
                {"type": "HRV", "value": value, "status": status},
            ],
        }

    return [
        day(BOTH_DAY, 62, "BALANCED"),
        day(HRV_ONLY_DAY, 48, "UNBALANCED"),
        day(EXISTING_DAY, 70, "BALANCED"),
    ]


def nested_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as inner:
        inner.writestr(f"{EMAIL}_run.fit", activity_fit(RUN_START))
        inner.writestr(f"{EMAIL}_strength.fit", activity_fit(STRENGTH_START, with_sets=True))
        inner.writestr(f"{EMAIL}_unmatched.fit", activity_fit(UNMATCHED_START))
        inner.writestr(f"{EMAIL}_monitoring.fit", monitoring_fit())
    return buffer.getvalue()


def build_export(path: Path, nested: bytes | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as export:
        export.writestr(
            f"DI_CONNECT/DI-Connect-Uploaded-Files/UploadedFiles_{EMAIL}_Part1.zip",
            nested if nested is not None else nested_zip(),
        )
        export.writestr(
            f"DI_CONNECT/DI-Connect-Fitness/{EMAIL}_summarizedActivities.json",
            json.dumps(summarized()),
        )
        export.writestr(
            f"DI_CONNECT/DI-Connect-Wellness/{EMAIL}_sleepData.json", json.dumps(sleep_data())
        )
        export.writestr(
            f"DI_CONNECT/DI-Connect-Wellness/{EMAIL}_healthStatusData.json",
            json.dumps(health_status()),
        )
    return path
