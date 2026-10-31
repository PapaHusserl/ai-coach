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


def test_active_items_returns_id_title_state(tmp_path: Path) -> None:
    path = write_todo(tmp_path / "t.json", [todo_item(2, "todo", "2026-10-01")])
    assert active_items(path) == [{"id": 2, "title": "Синтетическая задача 2", "state": "todo"}]


def test_active_items_without_file_is_empty(tmp_path: Path) -> None:
    assert active_items(tmp_path / "missing.json") == []
