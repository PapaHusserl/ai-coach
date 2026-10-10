from pathlib import Path

import pytest
from workload_fakes import write_config

from ai_coach.workload.config import WorkloadConfigError, load_config

FULL = """
[calendar]
work = ["Работа"]
personal = ["Дом ", "Семья"]
hobby = ["Хобби"]
rest = ["Отдых"]
ignore = ["Праздники"]

[paths]
todo = "/synthetic/todo.json"
hb_watch = "/synthetic/hb-watch"
"""


@pytest.fixture(autouse=True)
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_COACH_WORKLOAD_CONFIG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def test_categories_come_from_config(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", FULL))
    assert config.category("Работа") == "work"
    assert config.category("Семья") == "personal"
    assert config.category("Хобби") == "hobby"
    assert config.category("Отдых") == "rest"


def test_ignored_calendar_is_ignore(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", FULL))
    assert config.category("Праздники") == "ignore"


def test_unmarked_calendar_is_unknown(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", FULL))
    assert config.category("Неразмеченный") == "unknown"


def test_names_are_compared_by_strip(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", FULL))
    assert config.category("Дом") == "personal"
    assert config.category("  Работа  ") == "work"


def test_paths_come_from_config(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", FULL))
    assert config.todo_path == Path("/synthetic/todo.json")
    assert config.hb_watch_path == Path("/synthetic/hb-watch")


def test_config_without_paths_uses_defaults(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", '[calendar]\nwork = ["A"]\n'))
    home = tmp_path / "home"
    assert config.todo_path == home / ".claude" / "todo.json"
    assert config.hb_watch_path == home / "bin" / "hb-watch"


def test_config_with_calendars_is_configured(tmp_path: Path) -> None:
    assert load_config(write_config(tmp_path / "w.toml", FULL)).has_calendar


def test_config_with_only_paths_has_no_calendar(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", '[paths]\ntodo = "/synthetic/t.json"\n'))
    assert not config.has_calendar


def test_no_file_means_no_calendar_and_default_paths(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.toml")
    assert not config.has_calendar
    assert config.todo_path == tmp_path / "home" / ".claude" / "todo.json"
    assert config.hb_watch_path == tmp_path / "home" / "bin" / "hb-watch"


def test_broken_toml_is_clear_error(tmp_path: Path) -> None:
    path = write_config(tmp_path / "w.toml", "[calendar\nwork = ")
    with pytest.raises(WorkloadConfigError):
        load_config(path)


def test_env_overrides_default_location(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_config(tmp_path / "env.toml", FULL)
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(path))
    assert load_config().category("Работа") == "work"


def test_env_pointing_to_missing_file_means_no_calendar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(tmp_path / "nope.toml"))
    assert not load_config().has_calendar


def test_default_location_is_in_home_config_dir(tmp_path: Path) -> None:
    folder = tmp_path / "home" / ".config" / "ai-coach"
    folder.mkdir(parents=True)
    write_config(folder / "workload.toml", FULL)
    assert load_config().category("Работа") == "work"
