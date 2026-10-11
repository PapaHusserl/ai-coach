import sqlite3

from mcp_fakes import call, call_text, rows, tool_names

NOW = "2026-10-11 10:00:00"


def new_practice(
    conn: sqlite3.Connection,
    name: str = "дыхание 4-7-8",
    kind: str = "breathing",
    deleted: str | None = None,
) -> int:
    cursor = conn.execute(
        'INSERT INTO practice (name, kind, minutes, "trigger", steps, created_at, updated_at,'
        " deleted_at) VALUES (?, ?, 5, 'стресс 4+', 'вдох 4, выдох 8', ?, ?, ?)",
        (name, kind, NOW, NOW, deleted),
    )
    return int(cursor.lastrowid or 0)


def test_tool_exists(conn: sqlite3.Connection) -> None:
    assert "get_practices" in tool_names(conn)


def test_get_practices_on_empty_database(conn: sqlite3.Connection) -> None:
    assert call(conn, "get_practices") == {"rows": [], "truncated": False}


def test_get_practices_row_has_all_fields(conn: sqlite3.Connection) -> None:
    pid = new_practice(conn)
    row = rows(conn, "get_practices")[0]
    assert (row["id"], row["name"], row["kind"]) == (pid, "дыхание 4-7-8", "breathing")
    assert row["minutes"] == 5
    assert row["trigger"] == "стресс 4+"
    assert row["steps"] == "вдох 4, выдох 8"


def test_get_practices_has_no_deleted(conn: sqlite3.Connection) -> None:
    new_practice(conn, "дыхание")
    new_practice(conn, "прогулка", "walk", deleted=NOW)
    assert [r["name"] for r in rows(conn, "get_practices")] == ["дыхание"]


def test_get_practices_has_no_service_fields(conn: sqlite3.Connection) -> None:
    new_practice(conn)
    text = call_text(conn, "get_practices")
    assert "deleted_at" not in text
    assert "created_at" not in text


def test_get_practices_is_capped(conn: sqlite3.Connection) -> None:
    for number in range(100):
        new_practice(conn, f"практика {number}", "pause")
    result = call(conn, "get_practices")
    assert result["truncated"] is True
    assert len(result["rows"]) <= 60
