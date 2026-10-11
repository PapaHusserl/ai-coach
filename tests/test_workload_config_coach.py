"""[coach] calendar в workload.toml: календарь коуча (шаг v2.6)."""

from pathlib import Path

import pytest
from workload_fakes import write_config

from ai_coach.workload.config import WorkloadConfigError, load_config


@pytest.fixture(autouse=True)
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_COACH_WORKLOAD_CONFIG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def test_coach_calendar_comes_from_config(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", '[coach]\ncalendar = "Коуч"\n'))
    assert config.coach_calendar == "Коуч"


def test_coach_calendar_is_stripped(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", '[coach]\ncalendar = " Коуч "\n'))
    assert config.coach_calendar == "Коуч"


def test_no_coach_section_means_none(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", '[calendar]\nwork = ["A"]\n'))
    assert config.coach_calendar is None


def test_no_file_means_none(tmp_path: Path) -> None:
    assert load_config(tmp_path / "missing.toml").coach_calendar is None


def test_empty_coach_calendar_means_none(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path / "w.toml", '[coach]\ncalendar = "  "\n'))
    assert config.coach_calendar is None


def test_coach_calendar_not_a_string_is_error(tmp_path: Path) -> None:
    with pytest.raises(WorkloadConfigError):
        load_config(write_config(tmp_path / "w.toml", "[coach]\ncalendar = 5\n"))


def test_coach_section_not_a_table_is_error(tmp_path: Path) -> None:
    with pytest.raises(WorkloadConfigError):
        load_config(write_config(tmp_path / "w.toml", 'coach = "x"\n'))


def test_coach_calendar_category_is_coach(tmp_path: Path) -> None:
    text = '[calendar]\nwork = ["A"]\n[coach]\ncalendar = "Коуч"\n'
    config = load_config(write_config(tmp_path / "w.toml", text))
    assert config.category("Коуч") == "coach"
    assert config.category("A") == "work"


@pytest.mark.parametrize("section", ["work", "personal", "hobby", "rest", "ignore"])
def test_coach_calendar_in_other_section_is_error(tmp_path: Path, section: str) -> None:
    text = f'[calendar]\n{section} = ["Коуч"]\n[coach]\ncalendar = "Коуч"\n'
    with pytest.raises(WorkloadConfigError):
        load_config(write_config(tmp_path / "w.toml", text))


def test_conflict_is_found_after_strip(tmp_path: Path) -> None:
    text = '[calendar]\nwork = ["Коуч "]\n[coach]\ncalendar = "Коуч"\n'
    with pytest.raises(WorkloadConfigError):
        load_config(write_config(tmp_path / "w.toml", text))
