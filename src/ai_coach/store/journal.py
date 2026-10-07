"""Журналы: weight_log, food_log, wellbeing_log, sync_log."""

import sqlite3
from typing import Any

from ai_coach.store.db import fetch_all, fetch_one, insert


def add_weight(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: measured_at, weight_kg."""
    return insert(conn, "weight_log", values)


def list_weights(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Замеры с датой measured_at start..end включительно, по времени."""
    sql = (
        "SELECT * FROM weight_log WHERE substr(measured_at, 1, 10) BETWEEN ? AND ? "
        "AND deleted_at IS NULL ORDER BY measured_at, id"
    )
    return fetch_all(conn, sql, (start, end))


def add_food(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: logged_at, text (сырой текст; КБЖУ пусты до /coach-food)."""
    return insert(conn, "food_log", values)


def update_food(conn: sqlite3.Connection, food_id: int, values: dict[str, Any]) -> bool:
    """Запись КБЖУ (kcal, protein_g, fat_g, carbs_g) в запись, где оно ещё пусто.
    True — записано; False — записи нет, она удалена или КБЖУ уже посчитано."""
    sql = (
        "UPDATE food_log SET kcal = ?, protein_g = ?, fat_g = ?, carbs_g = ? "
        "WHERE id = ? AND kcal IS NULL AND deleted_at IS NULL"
    )
    args = (values["kcal"], values["protein_g"], values["fat_g"], values["carbs_g"], food_id)
    return conn.execute(sql, args).rowcount > 0


def list_food(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Записи с датой logged_at start..end включительно, по времени."""
    sql = (
        "SELECT * FROM food_log WHERE substr(logged_at, 1, 10) BETWEEN ? AND ? "
        "AND deleted_at IS NULL ORDER BY logged_at, id"
    )
    return fetch_all(conn, sql, (start, end))


def list_food_pending(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Записи без КБЖУ (kcal пуст), по времени."""
    sql = "SELECT * FROM food_log WHERE kcal IS NULL AND deleted_at IS NULL ORDER BY logged_at, id"
    return fetch_all(conn, sql, ())


def edit_weight(
    conn: sqlite3.Connection,
    weight_id: int,
    weight_kg: float | None = None,
    measured_at: str | None = None,
) -> bool:
    """Правка веса и/или времени замера (что не None). True - исправлено; False - записи нет
    или она удалена."""
    sql = (
        "UPDATE weight_log SET weight_kg = COALESCE(?, weight_kg), "
        "measured_at = COALESCE(?, measured_at) WHERE id = ? AND deleted_at IS NULL"
    )
    return conn.execute(sql, (weight_kg, measured_at, weight_id)).rowcount > 0


def delete_weight(conn: sqlite3.Connection, weight_id: int, deleted_at: str) -> bool:
    """Пометка удаления. True - удалена; False - записи нет или уже удалена."""
    sql = "UPDATE weight_log SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL"
    return conn.execute(sql, (deleted_at, weight_id)).rowcount > 0


def edit_food(
    conn: sqlite3.Connection,
    food_id: int,
    text: str | None = None,
    logged_at: str | None = None,
) -> bool:
    """Правка текста и/или времени записи еды (что не None). Новый текст сбрасывает КБЖУ в NULL
    (посчитает /coach-food), одно время - не трогает. True - исправлено; False - записи нет
    или она удалена."""
    if (
        conn.execute(
            "SELECT 1 FROM food_log WHERE id = ? AND deleted_at IS NULL", (food_id,)
        ).fetchone()
        is None
    ):
        return False
    if text is not None:
        sql = (
            "UPDATE food_log SET text = ?, kcal = NULL, protein_g = NULL, fat_g = NULL, "
            "carbs_g = NULL WHERE id = ?"
        )
        conn.execute(sql, (text, food_id))
    if logged_at is not None:
        conn.execute("UPDATE food_log SET logged_at = ? WHERE id = ?", (logged_at, food_id))
    return True


def delete_food(conn: sqlite3.Connection, food_id: int, deleted_at: str) -> bool:
    """Пометка удаления. True - удалена; False - записи нет или уже удалена."""
    sql = "UPDATE food_log SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL"
    return conn.execute(sql, (deleted_at, food_id)).rowcount > 0


def add_wellbeing(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: date, logged_at, score (1-5), text (может быть пуст). Только добавление."""
    return insert(conn, "wellbeing_log", values)


def list_wellbeing(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Записи с датой date start..end включительно, по времени (последняя за день — основная)."""
    sql = "SELECT * FROM wellbeing_log WHERE date BETWEEN ? AND ? ORDER BY logged_at, id"
    return fetch_all(conn, sql, (start, end))


def add_sync_log(conn: sqlite3.Connection, values: dict[str, Any]) -> int:
    """values: started_at, kind (sync/import), status, finished_at, message."""
    return insert(conn, "sync_log", values)


def last_sync_log(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Последняя запись sync_log (по id)."""
    return fetch_one(conn, "SELECT * FROM sync_log ORDER BY id DESC LIMIT 1", ())
