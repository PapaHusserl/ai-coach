"""Конфиг нагрузки вне репо: разметка календарей по категориям и пути туду и hb-watch."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

CONFIG_ENV = "AI_COACH_WORKLOAD_CONFIG"
CATEGORIES = ("work", "personal", "hobby", "rest")
IGNORE = "ignore"
UNKNOWN = "unknown"
COACH = "coach"


class WorkloadConfigError(Exception):
    """Конфиг нагрузки не читается (битый toml)."""


@dataclass(frozen=True)
class WorkloadConfig:
    """categories: название календаря (strip) -> категория; ignore - названия, которые
    пропускаем; todo_path и hb_watch_path - откуда читать туду и груминг; coach_calendar -
    название календаря коуча (None - не задан), его события пишет и читает тренер."""

    categories: dict[str, str]
    ignore: frozenset[str]
    todo_path: Path
    hb_watch_path: Path
    coach_calendar: str | None = None

    @property
    def has_calendar(self) -> bool:
        """Календари размечены (в конфиге есть хоть одно название); нет - календарь не читаем."""
        return bool(self.categories or self.ignore or self.coach_calendar)

    def category(self, calendar: str) -> str:
        """Категория по названию календаря без крайних пробелов: work/personal/hobby/rest,
        coach (календарь коуча), ignore (пропустить) или unknown (не размечен)."""
        name = calendar.strip()
        if name == self.coach_calendar:
            return COACH
        if name in self.ignore:
            return IGNORE
        return self.categories.get(name, UNKNOWN)


def default_config() -> WorkloadConfig:
    """Календарей нет, пути по умолчанию (домашний каталог берётся при вызове)."""
    home = Path.home()
    return WorkloadConfig(
        {}, frozenset(), home / ".claude" / "todo.json", home / "bin" / "hb-watch"
    )


def config_path(path: str | Path | None = None) -> Path:
    """Явный путь, иначе $AI_COACH_WORKLOAD_CONFIG, иначе ~/.config/ai-coach/workload.toml."""
    if path is not None:
        return Path(path)
    env = os.environ.get(CONFIG_ENV)
    return Path(env) if env else Path.home() / ".config" / "ai-coach" / "workload.toml"


def _table(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise WorkloadConfigError(f"Конфиг нагрузки: [{key}] должен быть таблицей.")
    return cast(dict[str, Any], value)


def _names(section: dict[str, Any], key: str) -> list[str]:
    """Названия календарей категории без крайних пробелов; не список строк - ошибка."""
    value = section.get(key, [])
    if not isinstance(value, list) or not all(isinstance(n, str) for n in cast(list[Any], value)):
        raise WorkloadConfigError(f"Конфиг нагрузки: calendar.{key} должен быть списком строк.")
    return [n.strip() for n in cast(list[str], value)]


def _path(paths: dict[str, Any], key: str, default: Path) -> str | Path:
    value = paths.get(key, default)
    if not isinstance(value, (str, Path)):
        raise WorkloadConfigError(f"Конфиг нагрузки: paths.{key} должен быть строкой.")
    return value


def _coach_calendar(section: dict[str, Any], marked: set[str]) -> str | None:
    """Название календаря коуча без крайних пробелов; нет или пустое - None. Не строка или уже
    размеченное в [calendar] - ошибка."""
    value = section.get("calendar", "")
    if not isinstance(value, str):
        raise WorkloadConfigError("Конфиг нагрузки: coach.calendar должен быть строкой.")
    name = value.strip()
    if not name:
        return None
    if name in marked:
        raise WorkloadConfigError(
            "Конфиг нагрузки: календарь коуча (coach.calendar) указан и в [calendar]."
        )
    return name


def load_config(path: str | Path | None = None) -> WorkloadConfig:
    """Читает конфиг. Нет файла - default_config(); битый toml - WorkloadConfigError."""
    target = config_path(path)
    fallback = default_config()
    if not target.is_file():
        return fallback
    try:
        data = tomllib.loads(target.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise WorkloadConfigError(f"Конфиг нагрузки не читается ({target.name}): {e}") from None
    section = _table(data, "calendar")
    paths = _table(data, "paths")
    categories = {n: c for c in CATEGORIES for n in _names(section, c)}
    ignore = frozenset(_names(section, "ignore"))
    coach = _coach_calendar(_table(data, "coach"), set(categories) | ignore)
    todo = Path(_path(paths, "todo", fallback.todo_path)).expanduser()
    hb_watch = Path(_path(paths, "hb_watch", fallback.hb_watch_path)).expanduser()
    return WorkloadConfig(categories, ignore, todo, hb_watch, coach)
