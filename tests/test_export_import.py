import io
import json
import sqlite3
import time
import zipfile
from pathlib import Path

import pytest
from export_fakes import (
    BOTH_DAY,
    EMAIL,
    EXISTING_DAY,
    HRV_ONLY_DAY,
    NO_SCORE_DAY,
    RUN_ID,
    STRENGTH_ID,
    UNMATCHED_START,
    activity_fit,
    build_export,
    monitoring_fit,
)
from garmin_fakes import sync_log
from typer.testing import CliRunner

from ai_coach.cli import main
from ai_coach.store.garmin_data import (
    get_activity,
    get_daily_metrics,
    last_rest_hr,
    list_activities,
    list_strength_sets,
    upsert_activity,
    upsert_daily_metrics,
)
from ai_coach.sync.export_import import import_export
from ai_coach.sync.fit_import import FitImportError, collect_messages

runner = CliRunner()


@pytest.fixture
def export(tmp_path: Path) -> Path:
    folder = tmp_path / "downloads"
    folder.mkdir()
    return build_export(folder / "export.zip")


def add_sync_rows(conn: sqlite3.Connection) -> None:
    """Строки, как их оставил бы sync: бег с API-именем и день с одним сном."""
    upsert_activity(
        conn,
        {
            "activity_id": RUN_ID,
            "start_time_local": "2026-03-10 11:57:32",
            "start_time_gmt": "2026-03-10 06:57:32",
            "type_key": "running",
            "name": "Sync run",
            "raw_json": '{"from": "sync"}',
        },
    )
    upsert_daily_metrics(
        conn,
        {
            "date": EXISTING_DAY,
            "sleep_seconds": 111,
            "sleep_score": 22,
            "raw_json": '{"from": "sync"}',
        },
    )
    conn.commit()


def dump_db(conn: sqlite3.Connection) -> dict[str, list[tuple]]:  # type: ignore[type-arg]
    tables = ["activities", "strength_sets", "daily_metrics"]
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1, 2")] for t in tables}


def test_import_adds_matched_activities(conn: sqlite3.Connection, export: Path) -> None:
    result = import_export(conn, export)
    assert result.activities_added == 2
    assert get_activity(conn, RUN_ID) is not None
    assert get_activity(conn, STRENGTH_ID) is not None


def test_import_takes_activity_id_from_summarized_by_start_time(
    conn: sqlite3.Connection, export: Path
) -> None:
    import_export(conn, export)
    run = get_activity(conn, RUN_ID)
    assert run is not None
    assert run["start_time_gmt"] == "2026-03-10 06:57:32"


def test_import_saves_strength_sets(conn: sqlite3.Connection, export: Path) -> None:
    import_export(conn, export)
    assert len(list_strength_sets(conn, STRENGTH_ID)) == 3


def test_import_skips_non_activity_fit(conn: sqlite3.Connection, export: Path) -> None:
    result = import_export(conn, export)
    # 3 активности-FIT + monitoring_b: в базе только сопоставленные
    assert result.activities_added + result.activities_skipped + result.activities_unmatched == 3
    assert len(list_activities(conn, "2000-01-01", "2100-01-01")) == 2


def test_import_counts_unmatched_activity_and_does_not_save_it(
    conn: sqlite3.Connection, export: Path
) -> None:
    result = import_export(conn, export)
    assert result.activities_unmatched == 1
    starts = [a["start_time_gmt"] for a in list_activities(conn, "2000-01-01", "2100-01-01")]
    assert time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(UNMATCHED_START)) not in starts


def test_import_merges_sleep_and_hrv_into_one_row(conn: sqlite3.Connection, export: Path) -> None:
    import_export(conn, export)
    day = get_daily_metrics(conn, BOTH_DAY)
    assert day is not None
    assert day["sleep_seconds"] == 3600 + 14400 + 5400
    assert day["sleep_score"] == 81
    assert day["hrv_last_night"] == 62
    assert day["hrv_status"] == "BALANCED"
    assert day["hrv_weekly_avg"] is None


def test_import_sleep_without_scores_has_no_sleep_score(
    conn: sqlite3.Connection, export: Path
) -> None:
    import_export(conn, export)
    day = get_daily_metrics(conn, NO_SCORE_DAY)
    assert day is not None
    assert day["sleep_seconds"] == 3000 + 15000 + 6000
    assert day["sleep_score"] is None
    assert day["hrv_last_night"] is None


def test_import_hrv_only_day_has_no_sleep(conn: sqlite3.Connection, export: Path) -> None:
    import_export(conn, export)
    day = get_daily_metrics(conn, HRV_ONLY_DAY)
    assert day is not None
    assert day["hrv_last_night"] == 48
    assert day["hrv_status"] == "UNBALANCED"
    assert day["sleep_seconds"] is None


def test_import_daily_raw_json_keeps_source_elements(
    conn: sqlite3.Connection, export: Path
) -> None:
    import_export(conn, export)
    day = get_daily_metrics(conn, BOTH_DAY)
    assert day is not None
    json.loads(day["raw_json"])
    assert "overallScore" in day["raw_json"]
    assert "BALANCED" in day["raw_json"]


def test_import_counts_days(conn: sqlite3.Connection, export: Path) -> None:
    add_sync_rows(conn)
    result = import_export(conn, export)
    assert result.days_added == 3
    assert result.days_skipped == 1


def test_import_does_not_change_existing_day_from_sync(
    conn: sqlite3.Connection, export: Path
) -> None:
    add_sync_rows(conn)
    before = get_daily_metrics(conn, EXISTING_DAY)
    import_export(conn, export)
    assert get_daily_metrics(conn, EXISTING_DAY) == before


def test_import_does_not_fill_hrv_into_existing_day_from_sync(
    conn: sqlite3.Connection, export: Path
) -> None:
    add_sync_rows(conn)
    import_export(conn, export)
    day = get_daily_metrics(conn, EXISTING_DAY)
    assert day is not None
    assert day["hrv_last_night"] is None


def test_import_does_not_change_existing_activity_from_sync(
    conn: sqlite3.Connection, export: Path
) -> None:
    add_sync_rows(conn)
    before = get_activity(conn, RUN_ID)
    result = import_export(conn, export)
    assert get_activity(conn, RUN_ID) == before
    assert result.activities_added == 1
    assert result.activities_skipped == 1


def test_import_twice_does_not_change_database(conn: sqlite3.Connection, export: Path) -> None:
    import_export(conn, export)
    before = dump_db(conn)
    second = import_export(conn, export)
    assert dump_db(conn) == before
    assert second.activities_added == 0
    assert second.activities_skipped == 2
    assert second.days_added == 0
    assert second.days_skipped == 4


def test_import_writes_sync_log(conn: sqlite3.Connection, export: Path) -> None:
    import_export(conn, export)
    row = conn.execute("SELECT kind, status, message FROM sync_log").fetchall()
    assert [(r["kind"], r["status"]) for r in row] == [("import", "ok")]
    assert EMAIL not in row[0]["message"]


def test_import_does_not_unpack_archive_to_disk(
    conn: sqlite3.Connection, export: Path, tmp_path: Path
) -> None:
    before = set(tmp_path.rglob("*"))
    import_export(conn, export)
    after = {p for p in tmp_path.rglob("*") if not p.name.startswith("coach.db")}
    assert after == {p for p in before if not p.name.startswith("coach.db")}


def test_import_not_a_zip_is_clear_error_and_keeps_database(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    broken = tmp_path / f"{EMAIL}_export.zip"
    broken.write_bytes(b"not a zip at all")
    with pytest.raises(FitImportError) as error:
        import_export(conn, broken)
    assert EMAIL not in str(error.value)
    assert dump_db(conn) == {"activities": [], "strength_sets": [], "daily_metrics": []}


def test_import_broken_nested_zip_error_has_no_email(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    broken = build_export(tmp_path / "export.zip", nested=b"broken nested zip")
    with pytest.raises(FitImportError) as error:
        import_export(conn, broken)
    assert EMAIL not in str(error.value)


def write_zip(path: Path, files: dict[str, str | bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return path


def test_import_hr_metric_is_not_resting_hr(conn: sqlite3.Connection, export: Path) -> None:
    import_export(conn, export)
    assert last_rest_hr(conn, HRV_ONLY_DAY) is None


def test_import_sleep_null_seconds_count_as_zero(conn: sqlite3.Connection, tmp_path: Path) -> None:
    sleep = [{"calendarDate": BOTH_DAY, "deepSleepSeconds": None, "lightSleepSeconds": 100}]
    path = write_zip(
        tmp_path / "export.zip",
        {f"DI_CONNECT/DI-Connect-Wellness/{EMAIL}_sleepData.json": json.dumps(sleep)},
    )
    import_export(conn, path)
    day = get_daily_metrics(conn, BOTH_DAY)
    assert day is not None
    assert day["sleep_seconds"] == 100


@pytest.mark.parametrize("content", ["not json", "[]", '[{"summarizedActivitiesExport": 5}]'])
def test_import_broken_export_json_is_clear_error_without_email(
    conn: sqlite3.Connection, tmp_path: Path, content: str
) -> None:
    path = write_zip(
        tmp_path / "export.zip",
        {f"DI_CONNECT/DI-Connect-Fitness/{EMAIL}_summarizedActivities.json": content},
    )
    with pytest.raises(FitImportError) as error:
        import_export(conn, path)
    assert EMAIL not in str(error.value)


def test_import_zip_without_export_folders_is_error(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    path = write_zip(tmp_path / "other.zip", {"readme.txt": "hello"})
    with pytest.raises(FitImportError, match="Это не zip-экспорт Garmin Connect"):
        import_export(conn, path)


def test_import_counts_unreadable_fit(conn: sqlite3.Connection, tmp_path: Path) -> None:
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr(f"{EMAIL}_broken.fit", b"garbage that is not fit")
        z.writestr(f"{EMAIL}_monitoring.fit", monitoring_fit())
    result = import_export(conn, build_export(tmp_path / "export.zip", nested=inner.getvalue()))
    assert result.fit_unreadable == 1
    assert result.activities_added == 0


def test_import_no_unreadable_fit_in_normal_export(conn: sqlite3.Connection, export: Path) -> None:
    assert import_export(conn, export).fit_unreadable == 0


def test_collect_messages_only_activity_stops_after_non_activity_file_id() -> None:
    messages = collect_messages(io.BytesIO(monitoring_fit()), only_activity=True)
    assert list(messages) == ["file_id"]
    full = collect_messages(io.BytesIO(activity_fit(1773125852)), only_activity=True)
    assert "session" in full


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "cli.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    return db


def count(db: Path, table: str) -> int:
    if not db.exists():
        return 0
    c = sqlite3.connect(db)
    try:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        c.close()


def test_cli_import_zip_saves_and_prints_summary(isolated: Path, export: Path) -> None:
    result = runner.invoke(main.app, ["import", str(export)])
    assert result.exit_code == 0
    assert count(isolated, "activities") == 2
    assert count(isolated, "daily_metrics") == 4
    assert "2" in result.output
    assert EMAIL not in result.output


def test_cli_import_zip_writes_sync_log(isolated: Path, export: Path) -> None:
    runner.invoke(main.app, ["import", str(export)])
    assert [(r["kind"], r["status"]) for r in sync_log(isolated)] == [("import", "ok")]


def test_cli_import_zip_twice_does_not_change_database(isolated: Path, export: Path) -> None:
    runner.invoke(main.app, ["import", str(export)])
    result = runner.invoke(main.app, ["import", str(export)])
    assert result.exit_code == 0
    assert count(isolated, "activities") == 2
    assert count(isolated, "daily_metrics") == 4


def test_cli_import_zip_with_id_is_error_and_keeps_database(isolated: Path, export: Path) -> None:
    result = runner.invoke(main.app, ["import", str(export), "--id", "5"])
    assert result.exit_code == 1
    assert "--id" in result.output
    assert count(isolated, "activities") == 0
    assert count(isolated, "daily_metrics") == 0


def test_cli_import_broken_zip_shows_error_without_email(isolated: Path, tmp_path: Path) -> None:
    broken = tmp_path / f"{EMAIL}_export.zip"
    broken.write_bytes(b"not a zip at all")
    result = runner.invoke(main.app, ["import", str(broken)])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert count(isolated, "activities") == 0
