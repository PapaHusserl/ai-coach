"""Подключение к SQLite, миграции и общие помощники запросов.

Версия схемы — PRAGMA user_version. Миграции — файлы migrations/NNNN_*.sql в пакете,
применяются при открытии по порядку номеров, каждая в своей транзакции.
"""

import json
import os
import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any

DB_ENV = "AI_COACH_DB"
DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "ai-coach" / "coach.db"


def db_path(path: str | Path | None = None) -> Path:
    """Явный путь, иначе $AI_COACH_DB, иначе ~/.local/share/ai-coach/coach.db."""
    if path is not None:
        return Path(path)
    env = os.environ.get(DB_ENV)
    return Path(env) if env else DEFAULT_DB_PATH


def open_db(path: str | Path | None = None) -> sqlite3.Connection:
    """Открывает базу (создаёт каталог и файл) и применяет недостающие миграции."""
    target = db_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        migrate(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> None:
    version = schema_version(conn)
    folder = resources.files("ai_coach.store").joinpath("migrations")
    files = sorted((f for f in folder.iterdir() if f.name.endswith(".sql")), key=lambda f: f.name)
    for file in files:
        number = int(file.name.split("_")[0])
        if number <= version:
            continue
        sql = file.read_text(encoding="utf-8")
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
        except BaseException:
            conn.rollback()
            raise


def _dump_raw(values: dict[str, Any]) -> dict[str, Any]:
    """raw_json и *_json можно передавать объектом — сохраняется JSON-строкой, None — NULL."""
    return {
        k: json.dumps(v, ensure_ascii=False)
        if k.endswith("_json") and v is not None and not isinstance(v, str)
        else v
        for k, v in values.items()
    }


def insert(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> int:
    values = _dump_raw(values)
    cols = ", ".join(values)
    marks = ", ".join(f":{k}" for k in values)
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", values)
    assert cur.lastrowid is not None
    return cur.lastrowid


def upsert(conn: sqlite3.Connection, table: str, key: list[str], values: dict[str, Any]) -> None:
    """INSERT, а при совпадении естественного ключа — обновление остальных колонок
    (если передан только ключ — ничего не делает)."""
    values = _dump_raw(values)
    cols = ", ".join(values)
    marks = ", ".join(f":{k}" for k in values)
    sets = ", ".join(f"{k} = excluded.{k}" for k in values if k not in key)
    action = f"DO UPDATE SET {sets}" if sets else "DO NOTHING"
    conn.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({marks}) ON CONFLICT ({', '.join(key)}) {action}",
        values,
    )


def update(conn: sqlite3.Connection, table: str, row_id: int, values: dict[str, Any]) -> None:
    values = _dump_raw(values)
    sets = ", ".join(f"{k} = :{k}" for k in values)
    conn.execute(f"UPDATE {table} SET {sets} WHERE id = :row_id", {**values, "row_id": row_id})


def fetch_one(conn: sqlite3.Connection, sql: str, args: tuple[Any, ...]) -> dict[str, Any] | None:
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def fetch_all(conn: sqlite3.Connection, sql: str, args: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, args).fetchall()]
