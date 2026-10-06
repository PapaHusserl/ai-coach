import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from ai_coach.store.db import open_db


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = open_db(tmp_path / "coach.db")
    yield connection
    connection.close()
