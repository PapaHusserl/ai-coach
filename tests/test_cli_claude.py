"""coach claude [--days N]: счётчики Claude Code из транскриптов в day_counters (шаг Н5).

Только Claude: Garmin и sync_log не трогаются. Транскрипты - синтетические jsonl в tmp_path,
пояс процесса - UTC, «сейчас» подменено.
"""

import json
import os
import sqlite3
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fake_clock import freeze
from garmin_fakes import sync_log
from typer.testing import CliRunner
from workload_fakes import write_config

from ai_coach.cli import main
from ai_coach.workload.claude import ClaudeError

runner = CliRunner()
ALPHA = "/synthetic/home/alpha"
BETA = "/synthetic/home/beta"


@pytest.fixture(autouse=True)
def utc_zone() -> Iterator[None]:
    old = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "coach.db"
    monkeypatch.setenv("AI_COACH_DB", str(db))
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))

    def no_garmin(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("claude не должен ходить в Garmin")

    monkeypatch.setattr(main, "load_client", no_garmin)
    paths = f'[paths]\nclaude_projects = "{tmp_path / "projects"}"\n'
    monkeypatch.setenv("AI_COACH_WORKLOAD_CONFIG", str(write_config(tmp_path / "w.toml", paths)))
    return db


def prompt(ts: str, cwd: str = ALPHA) -> dict[str, Any]:
    message = {"role": "user", "content": "синтетическая реплика"}
    return {"type": "user", "timestamp": ts, "message": message, "cwd": cwd}


def question(ts: str, count: int) -> dict[str, Any]:
    block = {"type": "tool_use", "name": "AskUserQuestion", "input": {"questions": [{}] * count}}
    return {"type": "assistant", "timestamp": ts, "message": {"content": [block]}}


def write(tmp_path: Path, folder: str, name: str, records: list[dict[str, Any]]) -> None:
    directory = tmp_path / "projects" / folder
    directory.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in records]
    path = directory / f"{name}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    moment = datetime(2026, 10, 12).timestamp()
    os.utime(path, (moment, moment))


def sessions(tmp_path: Path) -> None:
    write(
        tmp_path,
        "-a",
        "s1",
        [
            prompt("2026-10-11T10:00:00Z"),
            question("2026-10-11T10:05:00Z", 3),
            prompt("2026-10-11T20:00:00Z"),
        ],
    )
    write(tmp_path, "-b", "s2", [prompt("2026-10-11T10:30:00Z", BETA)])


def counters(db: Path) -> dict[tuple[str, str], tuple[float, str]]:
    conn = sqlite3.connect(db)
    try:
        sql = "SELECT date, kind, value, source FROM day_counters"
        return {(d, k): (v, s) for d, k, v, s in conn.execute(sql)}
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


def test_claude_writes_counters_for_wellbeing_day(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions(tmp_path)
    freeze(monkeypatch, "2026-10-11 21:00:00")
    result = runner.invoke(main.app, ["claude"])
    assert result.exit_code == 0
    assert counters(isolated) == {
        ("2026-10-11", "claude_prompts"): (3.0, "claude"),
        ("2026-10-11", "claude_prompts_evening"): (1.0, "claude"),
        ("2026-10-11", "claude_decisions"): (3.0, "claude"),
        ("2026-10-11", "claude_repos"): (2.0, "claude"),
        ("2026-10-11", "claude_switches"): (2.0, "claude"),
    }


def test_claude_prints_numbers_without_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions(tmp_path)
    freeze(monkeypatch, "2026-10-11 21:00:00")
    result = runner.invoke(main.app, ["claude"])
    assert result.output.strip() == (
        "Claude 2026-10-11: реплик 3 (вечером 1), решений 3, репо 2, переключений 2."
    )
    for forbidden in ("alpha", "beta", "/synthetic", "синтетическая"):
        assert forbidden not in result.output


def test_claude_at_0359_goes_to_yesterday(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions(tmp_path)
    freeze(monkeypatch, "2026-10-12 03:59:00")
    result = runner.invoke(main.app, ["claude"])
    assert {d for d, _ in counters(isolated)} == {"2026-10-11"}
    assert "Claude 2026-10-11:" in result.output


def test_claude_at_0400_goes_to_today(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions(tmp_path)
    freeze(monkeypatch, "2026-10-12 04:00:00")
    result = runner.invoke(main.app, ["claude"])
    assert {d for d, _ in counters(isolated)} == {"2026-10-12"}
    assert "Claude 2026-10-12:" in result.output


def test_claude_default_is_one_day(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions(tmp_path)
    freeze(monkeypatch, "2026-10-11 21:00:00")
    runner.invoke(main.app, ["claude"])
    assert {d for d, _ in counters(isolated)} == {"2026-10-11"}


def test_claude_days_writes_all_days_prints_only_today(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions(tmp_path)
    freeze(monkeypatch, "2026-10-11 21:00:00")
    result = runner.invoke(main.app, ["claude", "--days", "3"])
    assert {d for d, _ in counters(isolated)} == {"2026-10-09", "2026-10-10", "2026-10-11"}
    assert counters(isolated)[("2026-10-10", "claude_prompts")] == (0.0, "claude")
    assert len(result.output.strip().splitlines()) == 1
    assert "2026-10-11" in result.output


def test_claude_repeated_run_replaces_values(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions(tmp_path)
    freeze(monkeypatch, "2026-10-11 21:00:00")
    runner.invoke(main.app, ["claude"])
    write(
        tmp_path,
        "-b",
        "s2",
        [prompt("2026-10-11T10:30:00Z", BETA), prompt("2026-10-11T11:00:00Z", BETA)],
    )
    runner.invoke(main.app, ["claude"])
    found = counters(isolated)
    assert found[("2026-10-11", "claude_prompts")] == (4.0, "claude")
    assert len(found) == 5


def test_claude_without_directory_says_no_transcripts(
    isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")
    result = runner.invoke(main.app, ["claude"])
    assert result.exit_code == 0
    assert "транскриптов нет" in result.output
    assert counters(isolated) == {}


def test_claude_error_exits_with_code_1(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, "2026-10-11 21:00:00")

    def broken(*args: Any, **kwargs: Any) -> None:
        raise ClaudeError("каталог транскриптов не читается")

    monkeypatch.setattr(main, "read_claude", broken)
    result = runner.invoke(main.app, ["claude"])
    assert result.exit_code == 1
    assert "каталог транскриптов не читается" in result.output
    assert "Traceback" not in result.output
    assert counters(isolated) == {}


def test_claude_does_not_touch_sync_log(
    isolated: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sessions(tmp_path)
    freeze(monkeypatch, "2026-10-11 21:00:00")
    runner.invoke(main.app, ["claude"])
    assert sync_log(isolated) == []
