import json
import sqlite3
from pathlib import Path

import pytest

from ai_coach.store import db
from ai_coach.store.db import (
    DB_ENV,
    DEFAULT_DB_PATH,
    db_path,
    fetch_all,
    fetch_one,
    insert,
    migrate,
    open_db,
    schema_version,
    update,
    upsert,
)

TABLES = {
    "daily_metrics",
    "activities",
    "strength_sets",
    "weight_log",
    "goals",
    "phases",
    "goal_events",
    "planned_workouts",
    "plan_actual",
    "food_log",
    "sync_log",
}


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_default_path_is_outside_repo_in_local_share() -> None:
    assert Path.home() / ".local" / "share" / "ai-coach" / "coach.db" == DEFAULT_DB_PATH


def test_db_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DB_ENV, raising=False)
    assert db_path() == DEFAULT_DB_PATH


def test_db_path_env_overrides_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(DB_ENV, str(tmp_path / "env.db"))
    assert db_path() == tmp_path / "env.db"


def test_db_path_explicit_overrides_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(DB_ENV, str(tmp_path / "env.db"))
    assert db_path(tmp_path / "arg.db") == tmp_path / "arg.db"


def test_db_path_accepts_str(tmp_path: Path) -> None:
    assert db_path(str(tmp_path / "s.db")) == tmp_path / "s.db"


def test_db_path_empty_env_means_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DB_ENV, "")
    assert db_path() == DEFAULT_DB_PATH


def test_open_db_uses_env_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(DB_ENV, str(tmp_path / "from_env.db"))
    open_db().close()
    assert (tmp_path / "from_env.db").exists()


def test_open_db_does_not_touch_real_home_when_path_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(DB_ENV, raising=False)
    open_db(tmp_path / "x.db").close()
    assert (tmp_path / "x.db").exists()


def test_open_db_creates_missing_directories(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "coach.db"
    open_db(target).close()
    assert target.exists()


def test_open_db_creates_all_tables(conn: sqlite3.Connection) -> None:
    assert table_names(conn) >= TABLES


def test_open_db_sets_version_to_latest_migration(conn: sqlite3.Connection) -> None:
    migrations = db.resources.files("ai_coach.store").joinpath("migrations").iterdir()
    latest = max(int(f.name.split("_")[0]) for f in migrations)
    assert schema_version(conn) == latest
    assert schema_version(conn) >= 1


def test_open_db_returns_rows_by_name(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT 1 AS one").fetchone()
    assert row["one"] == 1


def test_open_db_enables_foreign_keys(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_raw_json_column_in_garmin_tables(conn: sqlite3.Connection) -> None:
    for table in ("daily_metrics", "activities", "strength_sets"):
        assert "raw_json" in column_names(conn, table)


def test_raw_json_is_required(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO daily_metrics (date) VALUES ('2026-01-01')")


def test_reopen_migrated_db_keeps_version_and_data(tmp_path: Path) -> None:
    path = tmp_path / "coach.db"
    first = open_db(path)
    version = schema_version(first)
    with first:
        upsert(first, "daily_metrics", ["date"], {"date": "2026-01-01", "raw_json": {}})
    first.close()
    second = open_db(path)
    assert schema_version(second) == version
    assert len(fetch_all(second, "SELECT * FROM daily_metrics", ())) == 1
    second.close()


def test_migrate_twice_is_noop(conn: sqlite3.Connection) -> None:
    version = schema_version(conn)
    migrate(conn)
    assert schema_version(conn) == version
    assert table_names(conn) >= TABLES


def test_migrate_on_empty_connection_creates_schema() -> None:
    raw = sqlite3.connect(":memory:")
    assert schema_version(raw) == 0
    migrate(raw)
    assert schema_version(raw) >= 1
    assert table_names(raw) >= TABLES
    raw.close()


def test_migrate_applies_only_newer_migrations(tmp_path: Path) -> None:
    # База "из будущего": версия выше последней миграции, таблиц нет — migrate их не создаёт.
    raw = sqlite3.connect(tmp_path / "future.db")
    raw.execute("PRAGMA user_version = 9999")
    migrate(raw)
    assert schema_version(raw) == 9999
    assert table_names(raw) == set()
    raw.close()


def test_insert_returns_new_id_and_stores_row(conn: sqlite3.Connection) -> None:
    first = insert(conn, "weight_log", {"measured_at": "2026-01-01T07:00", "weight_kg": 80.5})
    second = insert(conn, "weight_log", {"measured_at": "2026-01-02T07:00", "weight_kg": 80.1})
    assert second == first + 1
    row = fetch_one(conn, "SELECT * FROM weight_log WHERE id = ?", (first,))
    assert row == {"id": first, "measured_at": "2026-01-01T07:00", "weight_kg": 80.5}


def test_insert_dumps_json_object_in_json_columns(conn: sqlite3.Connection) -> None:
    values = {"date": "2026-01-01", "raw_json": {"name": "Бег", "n": [1, 2]}}
    upsert(conn, "daily_metrics", ["date"], values)
    row = fetch_one(conn, "SELECT raw_json FROM daily_metrics", ())
    assert row is not None
    assert json.loads(row["raw_json"]) == {"name": "Бег", "n": [1, 2]}


def test_json_dump_keeps_non_ascii_readable(conn: sqlite3.Connection) -> None:
    upsert(conn, "daily_metrics", ["date"], {"date": "2026-01-01", "raw_json": {"k": "Бег"}})
    row = fetch_one(conn, "SELECT raw_json FROM daily_metrics", ())
    assert row is not None
    assert "Бег" in row["raw_json"]


def test_json_string_is_stored_as_is(conn: sqlite3.Connection) -> None:
    upsert(conn, "daily_metrics", ["date"], {"date": "2026-01-01", "raw_json": '{"a": 1}'})
    row = fetch_one(conn, "SELECT raw_json FROM daily_metrics", ())
    assert row is not None
    assert row["raw_json"] == '{"a": 1}'


def test_non_json_columns_are_not_dumped(conn: sqlite3.Connection) -> None:
    insert(conn, "food_log", {"logged_at": "2026-01-01T08:00", "text": "каша"})
    row = fetch_one(conn, "SELECT text FROM food_log", ())
    assert row is not None
    assert row["text"] == "каша"


def test_upsert_same_key_updates_without_duplicate(conn: sqlite3.Connection) -> None:
    upsert(conn, "daily_metrics", ["date"], {"date": "d", "stress_avg": 10, "raw_json": "{}"})
    upsert(conn, "daily_metrics", ["date"], {"date": "d", "stress_avg": 20, "raw_json": "[]"})
    rows = fetch_all(conn, "SELECT * FROM daily_metrics", ())
    assert len(rows) == 1
    assert rows[0]["stress_avg"] == 20
    assert rows[0]["raw_json"] == "[]"


def test_upsert_different_keys_make_two_rows(conn: sqlite3.Connection) -> None:
    upsert(conn, "daily_metrics", ["date"], {"date": "a", "raw_json": "{}"})
    upsert(conn, "daily_metrics", ["date"], {"date": "b", "raw_json": "{}"})
    assert len(fetch_all(conn, "SELECT * FROM daily_metrics", ())) == 2


def test_update_changes_only_given_row_and_columns(conn: sqlite3.Connection) -> None:
    a = insert(conn, "weight_log", {"measured_at": "t1", "weight_kg": 80.0})
    b = insert(conn, "weight_log", {"measured_at": "t2", "weight_kg": 81.0})
    update(conn, "weight_log", a, {"weight_kg": 79.0})
    row_a = fetch_one(conn, "SELECT * FROM weight_log WHERE id = ?", (a,))
    row_b = fetch_one(conn, "SELECT * FROM weight_log WHERE id = ?", (b,))
    assert row_a == {"id": a, "measured_at": "t1", "weight_kg": 79.0}
    assert row_b == {"id": b, "measured_at": "t2", "weight_kg": 81.0}


def test_update_dumps_json_object(conn: sqlite3.Connection) -> None:
    pid = insert(
        conn,
        "planned_workouts",
        {"date": "2026-01-01", "sport": "run", "name": "n", "workout_json": {}},
    )
    update(conn, "planned_workouts", pid, {"workout_json": {"a": 1}})
    row = fetch_one(conn, "SELECT workout_json FROM planned_workouts WHERE id = ?", (pid,))
    assert row is not None
    assert json.loads(row["workout_json"]) == {"a": 1}


def test_fetch_one_returns_none_when_empty(conn: sqlite3.Connection) -> None:
    assert fetch_one(conn, "SELECT * FROM weight_log", ()) is None


def test_fetch_all_returns_plain_dicts(conn: sqlite3.Connection) -> None:
    insert(conn, "weight_log", {"measured_at": "t", "weight_kg": 1.0})
    rows = fetch_all(conn, "SELECT * FROM weight_log", ())
    assert type(rows[0]) is dict
    assert fetch_all(conn, "SELECT * FROM weight_log WHERE id = ?", (999,)) == []


def test_upsert_key_only_inserts_row_on_empty_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE t (k TEXT PRIMARY KEY, v TEXT)")
    upsert(conn, "t", ["k"], {"k": "a"})
    assert fetch_all(conn, "SELECT * FROM t", ()) == [{"k": "a", "v": None}]


def test_upsert_key_only_keeps_existing_row_untouched(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE t (k TEXT PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t VALUES ('a', 'keep')")
    upsert(conn, "t", ["k"], {"k": "a"})
    assert fetch_all(conn, "SELECT * FROM t", ()) == [{"k": "a", "v": "keep"}]


def test_open_db_closes_connection_and_reraises_when_migrate_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[sqlite3.Connection] = []

    def broken_migrate(connection: sqlite3.Connection) -> None:
        seen.append(connection)
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "migrate", broken_migrate)
    with pytest.raises(RuntimeError, match="boom"):
        open_db(tmp_path / "coach.db")
    assert len(seen) == 1
    with pytest.raises(sqlite3.ProgrammingError):
        seen[0].execute("SELECT 1")


def fake_migrations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, files: dict[str, str]) -> None:
    folder = tmp_path / "migrations"
    folder.mkdir()
    for name, body in files.items():
        (folder / name).write_text(body, encoding="utf-8")
    monkeypatch.setattr(db.resources, "files", lambda _package: tmp_path)


def test_migrate_failing_migration_rolls_back_and_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_migrations(
        monkeypatch,
        tmp_path,
        {
            "0001_ok.sql": "CREATE TABLE a (x INTEGER);",
            "0002_bad.sql": "CREATE TABLE b (x INTEGER); INSERT INTO no_such_table VALUES (1);",
        },
    )
    raw = sqlite3.connect(tmp_path / "m.db")
    with pytest.raises(sqlite3.Error):
        migrate(raw)
    assert not raw.in_transaction
    assert schema_version(raw) == 1
    assert table_names(raw) == {"a"}
    raw.close()


def test_migrate_ignores_non_sql_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_migrations(
        monkeypatch,
        tmp_path,
        {"0001_ok.sql": "CREATE TABLE a (x INTEGER);", "README.txt": "notes", "__init__.py": ""},
    )
    raw = sqlite3.connect(tmp_path / "m.db")
    migrate(raw)
    assert schema_version(raw) == 1
    assert table_names(raw) == {"a"}
    raw.close()


def new_event(conn: sqlite3.Connection, payload: object) -> int:
    goal_id = insert(conn, "goals", {"title": "g"})
    values = {"goal_id": goal_id, "event_type": "x", "occurred_at": "t", "payload_json": payload}
    return insert(conn, "goal_events", values)


def test_json_none_is_stored_as_sql_null(conn: sqlite3.Connection) -> None:
    eid = new_event(conn, None)
    row = fetch_one(conn, "SELECT payload_json FROM goal_events WHERE id = ?", (eid,))
    assert row == {"payload_json": None}


def test_json_none_is_stored_as_sql_null_on_update(conn: sqlite3.Connection) -> None:
    eid = new_event(conn, {})
    update(conn, "goal_events", eid, {"payload_json": None})
    row = fetch_one(conn, "SELECT payload_json FROM goal_events WHERE id = ?", (eid,))
    assert row == {"payload_json": None}


@pytest.mark.parametrize("table", ["daily_metrics", "activities"])
def test_raw_json_none_violates_not_null(conn: sqlite3.Connection, table: str) -> None:
    values = (
        {"date": "2026-03-10"}
        if table == "daily_metrics"
        else {
            "activity_id": 1,
            "start_time_local": "2026-03-10 07:00:00",
            "type_key": "running",
        }
    )
    with pytest.raises(sqlite3.IntegrityError):
        upsert(conn, table, list(values)[:1], values | {"raw_json": None})
