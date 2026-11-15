"""Формы тренера: forms (определения) и form_log (ответы). Функции записи НЕ делают commit."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert


def add_form(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
    """values: name, title, fields_json (объект или строка JSON), created_at."""
    insert(conn, "forms", values)


def get_form(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    """Форма по имени, в том числе снятая (archived_at не NULL)."""
    return fetch_one(conn, "SELECT * FROM forms WHERE name = ?", (name,))


def list_forms(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Активные (не снятые) формы по времени создания."""
    sql = "SELECT * FROM forms WHERE archived_at IS NULL ORDER BY created_at, name"
    return fetch_all(conn, sql, ())


def archive_form(conn: sqlite3.Connection, name: str, archived_at: str) -> bool:
    """Снять активную форму. False - формы нет или она уже снята."""
    sql = "UPDATE forms SET archived_at = ? WHERE name = ? AND archived_at IS NULL"
    return conn.execute(sql, (archived_at, name)).rowcount > 0


def add_form_entry(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: date, time, event_id, form, values_json; не обязательно text, wellbeing_id."""
    return insert(conn, "form_log", values)


def list_form_log(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Ответы с датой start..end включительно, по дате и времени. Оценка (score) и текст - из
    записи самочувствия, если ответ на неё ссылается; иначе score NULL, текст - свой."""
    sql = (
        "SELECT l.id, l.date, l.time, l.event_id, l.form, l.values_json, l.wellbeing_id, "
        "w.score, COALESCE(w.text, l.text) AS text "
        "FROM form_log l LEFT JOIN wellbeing_log w ON w.id = l.wellbeing_id "
        "WHERE l.date BETWEEN ? AND ? ORDER BY l.date, l.time, l.id"
    )
    return fetch_all(conn, sql, (start, end))
