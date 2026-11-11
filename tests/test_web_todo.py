"""Карточка «Туду» в пульте: todo_view и save_todo (шаг П5, партия 1)."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from workload_fakes import todo_item, write_todo

from ai_coach.web import todo as web_todo
from ai_coach.web.errors import MarkError
from ai_coach.web.todo import save_todo, todo_view
from ai_coach.workload import WorkloadConfigError

NOW = datetime(2026, 11, 11, 9, 30, 15)
DAY = NOW.date()
TODAY = "2026-11-11"


@pytest.fixture
def todo_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "todo.json"
    monkeypatch.setattr(web_todo, "load_config", lambda: SimpleNamespace(todo_path=path))
    return path


def view(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return todo_view(conn, DAY, NOW)["items"]


def four_states(path: Path) -> Path:
    items = [
        todo_item(1, "todo", "2026-10-01"),
        todo_item(2, "done", "2026-10-02"),
        todo_item(3, "doing", "2026-10-03"),
        todo_item(4, "dropped", "2026-10-04"),
    ]
    items[0]["note"] = "заметка"
    return write_todo(path, items)


def test_view_has_items_and_error_keys(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    assert set(todo_view(conn, DAY, NOW)) == {"items", "error"}


def test_view_error_is_none_for_normal_file(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    assert todo_view(conn, DAY, NOW)["error"] is None


def test_view_of_broken_file_is_empty_with_error_text(
    conn: sqlite3.Connection, todo_path: Path
) -> None:
    todo_path.write_text("{не json", encoding="utf-8")
    result = todo_view(conn, DAY, NOW)
    assert result["items"] == []
    assert "todo не читается" in result["error"]
    assert todo_path.read_text(encoding="utf-8") == "{не json"


def test_view_of_broken_config_is_empty_with_error_text(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken() -> Any:
        raise WorkloadConfigError("конфиг сломан")

    monkeypatch.setattr(web_todo, "load_config", broken)
    result = todo_view(conn, DAY, NOW)
    assert result["items"] == []
    assert "конфиг сломан" in result["error"]


def test_view_keeps_only_open_items(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    assert {item["id"] for item in view(conn)} == {1, 3}


def test_view_puts_doing_first(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    assert [item["id"] for item in view(conn)] == [3, 1]


def test_view_item_has_id_title_note_state_only(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    assert view(conn)[1] == {
        "id": 1,
        "title": "Синтетическая задача 1",
        "note": "заметка",
        "state": "todo",
    }


def test_view_without_file_is_empty(conn: sqlite3.Connection, todo_path: Path) -> None:
    assert view(conn) == []


def test_add_creates_item_with_next_id_and_today(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    assert save_todo(conn, {"op": "add", "title": "Новая", "note": "n"}, NOW) == {"id": 5}
    [item] = [i for i in view(conn) if i["id"] == 5]
    assert (item["title"], item["note"], item["state"]) == ("Новая", "n", "todo")
    record = json.loads(todo_path.read_text(encoding="utf-8"))[-1]
    assert (record["created"], record["updated"]) == (TODAY, TODAY)


def test_add_empty_title_is_mark_error(conn: sqlite3.Connection, todo_path: Path) -> None:
    with pytest.raises(MarkError, match="пустое название"):
        save_todo(conn, {"op": "add", "title": "  ", "note": ""}, NOW)
    assert not todo_path.exists()


def test_edit_changes_title_and_note(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    assert save_todo(conn, {"op": "edit", "id": 1, "title": "Другое", "note": "m"}, NOW) == {}
    item = [i for i in view(conn) if i["id"] == 1][0]
    assert (item["title"], item["note"]) == ("Другое", "m")


def test_edit_without_fields_is_mark_error(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    before = todo_path.read_bytes()
    with pytest.raises(MarkError, match="Нужен"):
        save_todo(conn, {"op": "edit", "id": 1}, NOW)
    assert todo_path.read_bytes() == before


def test_edit_unknown_id_is_mark_error(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    with pytest.raises(MarkError, match="Нет задачи #99"):
        save_todo(conn, {"op": "edit", "id": 99, "title": "X"}, NOW)


def test_move_to_done_sets_updated_and_leaves_card(
    conn: sqlite3.Connection, todo_path: Path
) -> None:
    four_states(todo_path)
    assert save_todo(conn, {"op": "move", "id": 1, "state": "done"}, NOW) == {}
    assert [i["id"] for i in view(conn)] == [3]
    record = [r for r in json.loads(todo_path.read_text(encoding="utf-8")) if r["id"] == 1][0]
    assert record["updated"] == TODAY


def test_move_to_dropped_leaves_card(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    save_todo(conn, {"op": "move", "id": 3, "state": "dropped"}, NOW)
    assert [i["id"] for i in view(conn)] == [1]


def test_move_doing_to_todo_is_ok(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    save_todo(conn, {"op": "move", "id": 3, "state": "todo"}, NOW)
    assert {i["id"]: i["state"] for i in view(conn)} == {1: "todo", 3: "todo"}


def test_move_todo_to_doing_is_ok(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    save_todo(conn, {"op": "move", "id": 1, "state": "doing"}, NOW)
    assert {i["id"]: i["state"] for i in view(conn)} == {1: "doing", 3: "doing"}


def test_move_from_closed_is_mark_error_and_file_unchanged(
    conn: sqlite3.Connection, todo_path: Path
) -> None:
    four_states(todo_path)
    before = todo_path.read_bytes()
    with pytest.raises(MarkError, match=r"Нельзя done -> doing \(можно: todo\)"):
        save_todo(conn, {"op": "move", "id": 2, "state": "doing"}, NOW)
    assert todo_path.read_bytes() == before


def test_move_same_state_is_mark_error(conn: sqlite3.Connection, todo_path: Path) -> None:
    four_states(todo_path)
    with pytest.raises(MarkError, match="Нельзя todo -> todo"):
        save_todo(conn, {"op": "move", "id": 1, "state": "todo"}, NOW)


@pytest.mark.parametrize("state", ["archived", "", None, 5])
def test_move_state_outside_four_is_mark_error(
    conn: sqlite3.Connection, todo_path: Path, state: object
) -> None:
    four_states(todo_path)
    before = todo_path.read_bytes()
    with pytest.raises(MarkError):
        save_todo(conn, {"op": "move", "id": 1, "state": state}, NOW)
    assert todo_path.read_bytes() == before


def test_move_reopen_from_card_is_refused(conn: sqlite3.Connection, todo_path: Path) -> None:
    """reopen в карточке недостижим: state=todo у закрытого — отказ по MOVES, не через API."""
    four_states(todo_path)
    before = todo_path.read_bytes()
    with pytest.raises(MarkError):
        save_todo(conn, {"op": "move", "id": 4, "state": "reopen"}, NOW)
    assert todo_path.read_bytes() == before


@pytest.mark.parametrize("op", ["delete", "", None])
def test_unknown_op_is_mark_error(conn: sqlite3.Connection, todo_path: Path, op: object) -> None:
    four_states(todo_path)
    before = todo_path.read_bytes()
    with pytest.raises(MarkError):
        save_todo(conn, {"op": op, "id": 1}, NOW)
    assert todo_path.read_bytes() == before


def test_config_error_is_mark_error(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken() -> Any:
        raise WorkloadConfigError("конфиг сломан")

    monkeypatch.setattr(web_todo, "load_config", broken)
    with pytest.raises(MarkError, match="конфиг сломан"):
        save_todo(conn, {"op": "add", "title": "X", "note": ""}, NOW)


def test_broken_todo_file_is_mark_error(conn: sqlite3.Connection, todo_path: Path) -> None:
    todo_path.write_text("{не json", encoding="utf-8")
    with pytest.raises(MarkError, match="todo не читается"):
        save_todo(conn, {"op": "add", "title": "X", "note": ""}, NOW)
    assert todo_path.read_text(encoding="utf-8") == "{не json"
