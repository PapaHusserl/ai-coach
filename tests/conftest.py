import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from ai_coach.store.db import open_db
from ai_coach.web import syncer

# Чистое состояние синка снято при импорте conftest, до первого запуска потока: копии ключей нет.
_CLEAN_SYNC = dict(syncer._state)  # pyright: ignore[reportPrivateUsage]


@pytest.fixture(autouse=True)
def no_real_workload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Нагрузка не читает настоящие календарь, туду и hb-watch: конфиг без календарей, пути tmp."""
    config = tmp_path / "no-workload.toml"
    paths = f'[paths]\ntodo = "{tmp_path / "no-todo.json"}"\nhb_watch = "{tmp_path / "no-hb"}"\n'
    paths += f'claude_projects = "{tmp_path / "no-claude"}"\n'
    config.write_text(paths, encoding="utf-8")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))


@pytest.fixture(autouse=True)
def no_real_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Код без явного пути к базе (мутант, забытый аргумент) пишет в tmp, не в базу Влада."""
    monkeypatch.setenv("AI_COACH_DB", str(tmp_path / "default-coach.db"))


@pytest.fixture(autouse=True)
def clean_syncer_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Состояние синка пульта модульное: ошибка одного теста не должна попасть в другие."""
    monkeypatch.setattr(syncer, "_state", dict(_CLEAN_SYNC))  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = open_db(tmp_path / "coach.db")
    yield connection
    connection.close()
