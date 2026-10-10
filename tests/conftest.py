import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from ai_coach.store.db import open_db


@pytest.fixture(autouse=True)
def no_real_workload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Нагрузка не читает настоящие календарь, туду и hb-watch: конфиг без календарей, пути tmp."""
    config = tmp_path / "no-workload.toml"
    paths = f'[paths]\ntodo = "{tmp_path / "no-todo.json"}"\nhb_watch = "{tmp_path / "no-hb"}"\n'
    config.write_text(paths, encoding="utf-8")
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(config))


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = open_db(tmp_path / "coach.db")
    yield connection
    connection.close()
