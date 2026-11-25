"""Шаг П8, партия 2: миграция 0043, intake_log принимает kind = 'med'."""

import sqlite3
from importlib import resources
from pathlib import Path

import pytest

from ai_coach.store.db import open_db, schema_version

DAY = "'2026-10-08'"
STAMP = "'2026-10-08 10:00:00'"


def migrate_from_42(tmp_path: Path) -> sqlite3.Connection:
    """База версии 42 с одним приёмом добавки."""
    folder = resources.files("ai_coach.store").joinpath("migrations")
    old = sqlite3.connect(tmp_path / "v42.db")
    for number in range(1, 43):
        name = next(
            f for f in sorted(p.name for p in folder.iterdir()) if f.startswith(f"{number:04d}")
        )
        sql = folder.joinpath(name).read_text(encoding="utf-8")
        old.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
    old.execute(
        "INSERT INTO intake_log (kind, item_id, date, taken_at, dose, note) "
        f"VALUES ('supplement', 3, {DAY}, {STAMP}, 2.5, 'с водой')"
    )
    old.commit()
    old.close()
    return open_db(tmp_path / "v42.db")


def intake(kind: str) -> str:
    return (
        "INSERT INTO intake_log (kind, item_id, date, taken_at) "
        f"VALUES ('{kind}', 1, {DAY}, {STAMP})"
    )


def test_schema_version_is_at_least_43(conn: sqlite3.Connection) -> None:
    assert schema_version(conn) >= 43


def test_intake_kind_med_is_allowed(conn: sqlite3.Connection) -> None:
    conn.execute(intake("med"))


@pytest.mark.parametrize("kind", ["protocol", ""])
def test_intake_bad_kind_is_refused(conn: sqlite3.Connection, kind: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(intake(kind))


def test_old_intake_row_survives_with_all_fields(tmp_path: Path) -> None:
    conn = migrate_from_42(tmp_path)
    try:
        row = conn.execute(
            "SELECT kind, item_id, date, taken_at, dose, note, deleted_at FROM intake_log"
        ).fetchone()
        assert tuple(row) == (
            "supplement",
            3,
            "2026-10-08",
            "2026-10-08 10:00:00",
            2.5,
            "с водой",
            None,
        )
    finally:
        conn.close()


def test_date_index_exists_on_intake_log(conn: sqlite3.Connection) -> None:
    [index] = conn.execute(
        "SELECT name, tbl_name FROM sqlite_master WHERE type = 'index' AND name = 'intake_log_date'"
    ).fetchall()
    assert index["tbl_name"] == "intake_log"
