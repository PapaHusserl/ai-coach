from pathlib import Path

import pytest
from workload_fakes import write_config

from ai_coach.workload.config import ScreenConfig, WorkloadConfigError, load_config

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


def screen_of(tmp_path: Path, text: str) -> ScreenConfig:
    config = load_config(write_config(tmp_path / "s.toml", text))
    assert config.screen is not None
    return config.screen


def test_no_screen_section_means_no_screen(tmp_path: Path) -> None:
    assert load_config(write_config(tmp_path / "w.toml", FULL)).screen is None


def test_no_file_means_no_screen(tmp_path: Path) -> None:
    assert load_config(tmp_path / "missing.toml").screen is None


def test_empty_screen_section_is_configured_with_defaults(tmp_path: Path) -> None:
    screen = screen_of(tmp_path, "[screen]\n")
    assert screen.url == "http://127.0.0.1:5600"
    assert screen.work == screen.hobby == screen.browser == screen.meeting == frozenset()
    assert screen.title == {}


def test_screen_url_comes_from_config(tmp_path: Path) -> None:
    assert screen_of(tmp_path, '[screen]\nurl = "http://127.0.0.1:5999"\n').url == (
        "http://127.0.0.1:5999"
    )


def test_screen_apps_are_lowercased(tmp_path: Path) -> None:
    screen = screen_of(
        tmp_path,
        '[screen]\nwork = ["Alpha Editor"]\nhobby = ["BetaGame"]\n'
        'browser = ["Gamma Browser"]\nmeeting = ["DeltaCall"]\n',
    )
    assert screen.work == {"alpha editor"}
    assert screen.hobby == {"betagame"}
    assert screen.browser == {"gamma browser"}
    assert screen.meeting == {"deltacall"}


def test_meeting_names_keep_case_for_the_server_query(tmp_path: Path) -> None:
    screen = screen_of(tmp_path, '[screen]\nmeeting = ["DeltaCall", "epsilon"]\n')
    assert screen.meeting_names == ("DeltaCall", "epsilon")


def test_screen_title_rules_are_read(tmp_path: Path) -> None:
    text = '[screen.title.alpha]\nwork = ["proj-a", "proj-b"]\nhobby = ["fun"]\n'
    assert screen_of(tmp_path, text).title == {
        "alpha": {"work": ["proj-a", "proj-b"], "hobby": ["fun"]}
    }


def test_screen_title_with_one_class_is_allowed(tmp_path: Path) -> None:
    title = screen_of(tmp_path, '[screen.title.alpha]\nwork = ["x"]\n').title
    assert title["alpha"].get("hobby", []) == []


def test_screen_title_app_keeps_case_as_in_toml(tmp_path: Path) -> None:
    assert list(screen_of(tmp_path, '[screen.title.AlphaEdit]\nwork = ["x"]\n').title) == [
        "AlphaEdit"
    ]


def test_screen_does_not_break_calendar_and_paths(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", FULL + '\n[screen]\nwork = ["a"]\n'))
    assert config.category("Работа") == "work"
    assert config.todo_path == Path("/synthetic/todo.json")


def test_screen_bad_regex_is_config_error(tmp_path: Path) -> None:
    path = write_config(tmp_path / "s.toml", "[screen.title.alpha]\nwork = ['(unclosed']\n")
    with pytest.raises(WorkloadConfigError):
        load_config(path)


def test_screen_bad_regex_in_hobby_is_config_error(tmp_path: Path) -> None:
    path = write_config(tmp_path / "s.toml", "[screen.title.alpha]\nhobby = ['ok', '[bad']\n")
    with pytest.raises(WorkloadConfigError):
        load_config(path)


def test_screen_quote_in_regex_is_config_error(tmp_path: Path) -> None:
    path = write_config(tmp_path / "s.toml", "[screen.title.alpha]\nwork = ['a\"b']\n")
    with pytest.raises(WorkloadConfigError):
        load_config(path)


def test_screen_unknown_key_in_title_is_config_error(tmp_path: Path) -> None:
    path = write_config(tmp_path / "s.toml", '[screen.title.alpha]\nwork = ["x"]\nrest = ["y"]\n')
    with pytest.raises(WorkloadConfigError):
        load_config(path)


@pytest.mark.parametrize("key", ["work", "hobby", "browser", "meeting"])
def test_screen_apps_must_be_a_list(tmp_path: Path, key: str) -> None:
    path = write_config(tmp_path / "s.toml", f'[screen]\n{key} = "alpha"\n')
    with pytest.raises(WorkloadConfigError):
        load_config(path)


def test_screen_apps_must_be_strings(tmp_path: Path) -> None:
    path = write_config(tmp_path / "s.toml", "[screen]\nwork = [1, 2]\n")
    with pytest.raises(WorkloadConfigError):
        load_config(path)


@pytest.mark.parametrize("cat", ["work", "hobby"])
def test_screen_title_rules_must_be_a_list(tmp_path: Path, cat: str) -> None:
    path = write_config(tmp_path / "s.toml", f'[screen.title.alpha]\n{cat} = "x"\n')
    with pytest.raises(WorkloadConfigError):
        load_config(path)


def test_screen_url_must_be_a_string(tmp_path: Path) -> None:
    with pytest.raises(WorkloadConfigError):
        load_config(write_config(tmp_path / "s.toml", "[screen]\nurl = 5600\n"))


def test_screen_title_app_must_be_a_table(tmp_path: Path) -> None:
    path = write_config(tmp_path / "s.toml", '[screen.title]\nalpha = "x"\n')
    with pytest.raises(WorkloadConfigError):
        load_config(path)


def test_broken_toml_with_screen_section_is_clear_error(tmp_path: Path) -> None:
    with pytest.raises(WorkloadConfigError):
        load_config(write_config(tmp_path / "s.toml", "[screen\nwork = "))


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
