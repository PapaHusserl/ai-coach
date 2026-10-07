import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version
from ai_coach.store.garmin_data import last_threshold, upsert_threshold


def v4_db(path: Path) -> sqlite3.Connection:
    """База на версии 4: применены только миграции 0001-0004."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    for number in range(1, 5):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"000{number}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    return conn


def test_schema_version_is_at_least_5(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 5


def test_migration_moves_old_thresholds_as_run_from_garmin(tmp_path: Path) -> None:
    path = tmp_path / "v4.db"
    old = v4_db(path)
    old.execute("INSERT INTO thresholds VALUES ('2026-03-01', 165, '{\"a\": 1}')")
    old.execute("INSERT INTO thresholds VALUES ('2026-03-09', 168, '{}')")
    old.commit()
    old.close()

    conn = open_db(path)
    try:
        rows = conn.execute(
            "SELECT sport, calendar_date, lthr, source, raw_json FROM thresholds ORDER BY 2"
        ).fetchall()
        assert [tuple(r) for r in rows] == [
            ("run", "2026-03-01", 165, "garmin_lt", '{"a": 1}'),
            ("run", "2026-03-09", 168, "garmin_lt", "{}"),
        ]
    finally:
        conn.close()


def test_same_date_for_different_sports_is_allowed(conn: sqlite3.Connection) -> None:
    for sport in ("run", "bike", "swim"):
        upsert_threshold(
            conn,
            {
                "sport": sport,
                "calendar_date": "2026-03-01",
                "lthr": 160,
                "source": "garmin_zones",
                "raw_json": {},
            },
        )
    assert conn.execute("SELECT COUNT(*) FROM thresholds").fetchone()[0] == 3


def test_last_threshold_is_per_sport_and_not_after_end(conn: sqlite3.Connection) -> None:
    for sport, day, lthr in (("run", "2026-03-01", 170), ("bike", "2026-03-05", 165)):
        upsert_threshold(
            conn,
            {
                "sport": sport,
                "calendar_date": day,
                "lthr": lthr,
                "source": "garmin_zones",
                "raw_json": {},
            },
        )
    run = last_threshold(conn, "run", "2026-03-10")
    assert run is not None
    assert run["lthr"] == 170
    assert last_threshold(conn, "bike", "2026-03-04") is None


@pytest.mark.parametrize(
    ("sport", "source"), [("rowing", "garmin_lt"), ("run", "guess"), ("run", "derived")]
)
def test_garbage_sport_or_source_rejected_by_db(
    conn: sqlite3.Connection, sport: str, source: str
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        upsert_threshold(
            conn,
            {
                "sport": sport,
                "calendar_date": "2026-03-01",
                "lthr": 160,
                "source": source,
                "raw_json": {},
            },
        )


def test_lactate_and_zones_coexist_on_same_day(conn: sqlite3.Connection) -> None:
    for source in ("garmin_lt", "garmin_zones"):
        upsert_threshold(
            conn,
            {
                "sport": "run",
                "calendar_date": "2026-03-01",
                "lthr": 170,
                "source": source,
                "raw_json": {},
            },
        )
    assert conn.execute("SELECT COUNT(*) FROM thresholds").fetchone()[0] == 2
