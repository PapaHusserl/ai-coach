"""Сторож личных значений в документах (шаг Г2): метрика Влада + число в тексте — красный тест."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_METRIC = r"(?<!\w)(?:пульс(?:\s+покоя)?|ЧСС|RHR|HRV|ВСР|вес)(?!\w)"
_PERIOD = r"(?:дн|дней|нед|час|мин|раз)"
_VALUE = re.compile(
    rf"{_METRIC}\s*[=:]?\s*\d+(?:[.,]\d+)?(?!\d|[.,]\d)(?!\s*{_PERIOD})",
    re.IGNORECASE,
)
_WEIGHT_UNIT = re.compile(r"(?<![\d.,])(?<!\d\s)\d+(?:[.,]\d+)?\s*кг(?!\w)", re.IGNORECASE)

SCOPE_GLOBS = (
    "docs/BACKLOG.md",
    "docs/done/*.md",
    "docs/handoff.md",
    "docs/ROADMAP.md",
    "NOTES.md",
    "README.md",
    "AGENTS.md",
    "docs/research-*.md",
    ".claude/agents/**/*.md",
    ".claude/skills/**/*.md",
)


def _hits(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if _VALUE.search(line):
            found.append((number, "метрика"))
        if _WEIGHT_UNIT.search(line):
            found.append((number, "вес"))
    return found


def _scope_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in SCOPE_GLOBS:
        files.update(path for path in ROOT.glob(pattern) if path.is_file())
    return sorted(files)


@pytest.mark.parametrize(
    "text",
    [
        "пульс покоя 50",
        "HRV 40",
        "HRV=40",
        "пульс 50, HRV 40",
        "вес 70,5 кг",
        "(70,5 кг)",
    ],
)
def test_hits_finds_personal_value(text):
    assert _hits(text)


@pytest.mark.parametrize(
    "text",
    [
        "HRV 2 дня подряд",
        "пульс покоя старше 14 дней",
        "HRV за 28 дней",
        "SpO2 ниже 92",
        "readiness < 33",
    ],
)
def test_hits_skips_threshold_or_period(text):
    assert _hits(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "HRV (BACKLOG 30)",
        "пульс покоя ✅ 2026-11-19",
        "`hrv_last_night`",
    ],
)
def test_hits_skips_reference_and_identifier(text):
    assert _hits(text) == []


@pytest.mark.parametrize("text", ["", "plain english text 42 and HRV-free line\n"])
def test_hits_empty_or_without_cyrillic(text):
    assert _hits(text) == []


def test_hits_reports_line_number():
    assert [number for number, _ in _hits("первая\nвторая\nHRV 40\n")] == [3]


def test_scope_lists_documents_and_excludes_plans_and_tests():
    names = {path.relative_to(ROOT).as_posix() for path in _scope_files()}
    assert {
        "docs/BACKLOG.md",
        "docs/handoff.md",
        "docs/ROADMAP.md",
        "NOTES.md",
        "README.md",
        "AGENTS.md",
    } <= names
    assert any(name.startswith("docs/done/") for name in names)
    assert any(name.startswith("docs/research-") for name in names)
    assert any(name.startswith(".claude/agents/") for name in names)
    assert any(name.startswith(".claude/skills/") for name in names)
    assert not any(name.startswith("tests/") or name.startswith("docs/plan-") for name in names)


def test_documents_have_no_personal_values():
    problems = [
        f"{path.relative_to(ROOT).as_posix()}:{number} ({kind})"
        for path in _scope_files()
        for number, kind in _hits(path.read_text(encoding="utf-8"))
    ]
    assert not problems, "личные значения в документах: " + ", ".join(problems)
