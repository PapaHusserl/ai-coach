"""coach todo list: активные пункты todo.json, только чтение (шаг Н13)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner
from workload_fakes import todo_item, write_config, write_todo

from ai_coach.cli import main
from ai_coach.workload.todo import active_items

runner = CliRunner()


@pytest.fixture
def todo_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "todo.json"
    config = write_config(tmp_path / "coach.toml", f'[paths]\ntodo = "{path}"\n')
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))
    monkeypatch.setenv("AI_COACH_DB", str(tmp_path / "coach.db"))
    return path


def run() -> object:
    return runner.invoke(main.app, ["todo", "list"])


def items() -> list[dict[str, object]]:
    return [
        todo_item(3, "todo", "2026-10-01"),
        todo_item(1, "todo", "2026-10-01"),
        todo_item(4, "done", "2026-10-02"),
        todo_item(2, "doing", "2026-10-03"),
        todo_item(5, "dropped", "2026-10-03"),
    ]


def test_active_items_are_printed_doing_first_then_by_id(todo_path: Path) -> None:
    write_todo(todo_path, items())
    result = run()
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert result.output.splitlines() == [  # type: ignore[attr-defined]
        "2  doing  Синтетическая задача 2",
        "1  todo  Синтетическая задача 1",
        "3  todo  Синтетическая задача 3",
    ]


def test_closed_items_are_not_printed(todo_path: Path) -> None:
    write_todo(todo_path, items())
    output = run().output  # type: ignore[attr-defined]
    assert "задача 4" not in output
    assert "задача 5" not in output


def test_no_file_prints_empty_message(todo_path: Path) -> None:
    result = run()
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert "Туду пусто" in result.output  # type: ignore[attr-defined]


def test_only_closed_items_print_empty_message(todo_path: Path) -> None:
    write_todo(todo_path, [todo_item(1, "done", "2026-10-01")])
    result = run()
    assert result.exit_code == 0  # type: ignore[attr-defined]
    assert "Туду пусто" in result.output  # type: ignore[attr-defined]


def test_broken_json_fails_with_message(todo_path: Path) -> None:
    todo_path.write_text("{не json", encoding="utf-8")
    result = run()
    assert result.exit_code == 1  # type: ignore[attr-defined]
    assert "todo не читается" in result.output  # type: ignore[attr-defined]


def test_root_not_a_list_fails(todo_path: Path) -> None:
    todo_path.write_text('{"id": 1}', encoding="utf-8")
    assert run().exit_code == 1  # type: ignore[attr-defined]


def test_file_is_not_changed(todo_path: Path) -> None:
    write_todo(todo_path, items())
    before = todo_path.read_bytes()
    run()
    assert todo_path.read_bytes() == before


def test_list_all_includes_closed(todo_path: Path) -> None:
    write_todo(todo_path, items())
    output = runner.invoke(main.app, ["todo", "list", "--all"]).output
    assert "4  done  Синтетическая задача 4" in output
    assert "5  dropped  Синтетическая задача 5" in output


def test_add_and_moves_print_and_write(todo_path: Path) -> None:
    result = runner.invoke(main.app, ["todo", "add", "Купить X", "--note", "n"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "+ #1 Купить X"
    for command, state in [
        ("start", "doing"),
        ("done", "done"),
        ("reopen", "todo"),
        ("drop", "dropped"),
    ]:
        result = runner.invoke(main.app, ["todo", command, "1"])
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f"#1 -> {state}"


def test_forbidden_move_and_missing_id_fail(todo_path: Path) -> None:
    write_todo(todo_path, [todo_item(1, "done", "2026-10-01")])
    before = todo_path.read_bytes()
    result = runner.invoke(main.app, ["todo", "start", "1"])
    assert result.exit_code == 1
    assert "Нельзя done -> doing (можно: todo)" in result.output
    result = runner.invoke(main.app, ["todo", "done", "9"])
    assert result.exit_code == 1
    assert "Нет задачи #9" in result.output
    assert todo_path.read_bytes() == before


def test_edit_changes_title_and_requires_option(todo_path: Path) -> None:
    write_todo(todo_path, [todo_item(1, "todo", "2026-10-01")])
    assert runner.invoke(main.app, ["todo", "edit", "1", "--title", "Новое"]).exit_code == 0
    assert "1  todo  Новое" in run().output  # type: ignore[attr-defined]
    assert runner.invoke(main.app, ["todo", "edit", "1"]).exit_code == 1


def test_add_to_broken_file_fails_and_keeps_it(todo_path: Path) -> None:
    todo_path.write_text("{не json", encoding="utf-8")
    result = runner.invoke(main.app, ["todo", "add", "X"])
    assert result.exit_code == 1
    assert todo_path.read_text(encoding="utf-8") == "{не json"


def test_add_into_existing_takes_next_id(todo_path: Path) -> None:
    write_todo(todo_path, [todo_item(3, "todo", "2026-10-01"), todo_item(7, "done", "2026-10-01")])
    result = runner.invoke(main.app, ["todo", "add", "Новый"])
    assert result.output.strip() == "+ #8 Новый"


def test_add_empty_title_fails(todo_path: Path) -> None:
    result = runner.invoke(main.app, ["todo", "add", "  "])
    assert result.exit_code == 1
    assert not todo_path.exists()


def test_active_items_returns_id_title_note_state(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "t.json", [todo_item(2, "todo", "2026-10-01")])
    assert active_items(path) == [
        {"id": 2, "title": "Синтетическая задача 2", "note": "", "state": "todo"}
    ]


def test_active_items_note_is_taken_from_file(tmp_path: Path) -> None:
    item = todo_item(2, "todo", "2026-10-01")
    item["note"] = "подробности"
    path = write_todo(tmp_path / "t.json", [item])
    assert active_items(path)[0]["note"] == "подробности"


def test_list_prints_three_fields_without_note(todo_path: Path) -> None:
    item = todo_item(2, "todo", "2026-10-01")
    item["note"] = "секретная-заметка"
    write_todo(todo_path, [item])
    result = runner.invoke(main.app, ["todo", "list"])
    assert result.exit_code == 0
    assert "секретная-заметка" not in result.output
    assert "Синтетическая задача 2" in result.output


def test_active_items_without_file_is_empty(tmp_path: Path) -> None:
    assert active_items(tmp_path / "missing.json") == []
