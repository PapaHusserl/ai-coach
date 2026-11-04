"""Запись todo.json: add_item, move_item, edit_item (шаг Н21)."""

import json
from datetime import date
from pathlib import Path

import pytest
from workload_fakes import todo_item, write_todo

from ai_coach.workload.todo import (
    MOVES,
    TodoError,
    add_item,
    edit_item,
    move_item,
    read_todo,
)

TODAY = date(2026, 11, 4)


def load(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_add_creates_file_and_directory(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "todo.json"
    assert add_item(path, "Купить X", "n", TODAY) == 1
    assert load(path) == [
        {
            "id": 1,
            "title": "Купить X",
            "note": "n",
            "state": "todo",
            "created": "2026-11-04",
            "updated": "2026-11-04",
        }
    ]
    assert "Купить" in path.read_text(encoding="utf-8")
    assert path.read_text(encoding="utf-8").startswith('[\n {\n  "id"')


def test_add_takes_max_plus_one(tmp_path: Path) -> None:
    path = write_todo(
        tmp_path / "t.json",
        [todo_item(3, "todo", "2026-10-01"), todo_item(7, "done", "2026-10-01")],
    )
    assert add_item(path, "Новый", "", TODAY) == 8


def test_add_empty_title_fails(tmp_path: Path) -> None:
    with pytest.raises(TodoError, match="пустое название"):
        add_item(tmp_path / "t.json", "  ", "", TODAY)


@pytest.mark.parametrize(
    ("source", "target"), [(s, t) for s, targets in MOVES.items() for t in targets]
)
def test_allowed_moves_set_state_and_updated(tmp_path: Path, source: str, target: str) -> None:
    path = write_todo(tmp_path / "t.json", [todo_item(1, source, "2026-10-01")])
    move_item(path, 1, target, TODAY)
    record = load(path)[0]
    assert record["state"] == target
    assert record["updated"] == "2026-11-04"


@pytest.mark.parametrize(
    ("source", "target"), [("done", "doing"), ("dropped", "done"), ("doing", "doing")]
)
def test_forbidden_move_fails_and_keeps_file(tmp_path: Path, source: str, target: str) -> None:
    path = write_todo(tmp_path / "t.json", [todo_item(1, source, "2026-10-01")])
    before = path.read_bytes()
    with pytest.raises(TodoError, match=f"Нельзя {source} -> {target}"):
        move_item(path, 1, target, TODAY)
    assert path.read_bytes() == before


def test_missing_id_and_missing_file(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "t.json", [todo_item(1, "todo", "2026-10-01")])
    with pytest.raises(TodoError, match="Нет задачи #9"):
        move_item(path, 9, "done", TODAY)
    with pytest.raises(TodoError, match="Нет задачи #1"):
        edit_item(tmp_path / "none.json", 1, "x", None)


def test_broken_file_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text("{не json", encoding="utf-8")
    with pytest.raises(TodoError):
        add_item(path, "x", "", TODAY)
    assert path.read_text(encoding="utf-8") == "{не json"
    path.write_text('{"id": 1}', encoding="utf-8")
    with pytest.raises(TodoError):
        move_item(path, 1, "done", TODAY)
    assert path.read_text(encoding="utf-8") == '{"id": 1}'


def test_foreign_fields_and_non_dict_records_are_kept(tmp_path: Path) -> None:
    item = todo_item(1, "todo", "2026-10-01") | {"extra": [1, 2]}
    path = tmp_path / "t.json"
    path.write_text(json.dumps([item, "строка", 5], ensure_ascii=False), encoding="utf-8")
    move_item(path, 1, "doing", TODAY)
    data = load(path)
    assert data[0]["extra"] == [1, 2]
    assert data[1:] == ["строка", 5]


def test_edit_changes_fields_but_not_updated(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "t.json", [todo_item(1, "done", "2026-10-01")])
    edit_item(path, 1, "Новое", "заметка")
    record = load(path)[0]
    assert record["title"] == "Новое"
    assert record["note"] == "заметка"
    assert record["updated"] == "2026-10-01"
    edit_item(path, 1, None, "другая")
    assert load(path)[0]["title"] == "Новое"
    with pytest.raises(TodoError, match="пустое название"):
        edit_item(path, 1, "", None)


def test_failed_replace_removes_tmp_and_keeps_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_todo(tmp_path / "t.json", [todo_item(1, "todo", "2026-10-01")])
    before = path.read_bytes()

    def boom(_src: object, _dst: object) -> None:
        raise OSError("диск")

    monkeypatch.setattr("ai_coach.workload.todo.os.replace", boom)
    with pytest.raises(OSError, match="диск"):
        move_item(path, 1, "done", TODAY)
    assert not (tmp_path / "t.json.tmp").exists()
    assert path.read_bytes() == before


def test_done_today_counts_in_todo_closed(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "t.json", [todo_item(1, "todo", "2026-10-01")])
    move_item(path, 1, "done", TODAY)
    counters = read_todo(path, TODAY, TODAY, TODAY)
    assert {c["kind"]: c["value"] for c in counters} == {"todo_closed": 1, "todo_open": 0}
