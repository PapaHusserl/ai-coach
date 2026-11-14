"""Шаг П11, партия 1: опросники чек-ина — отметки (marks_of), «красное» (checkin_due), сторож JS."""

import re
from pathlib import Path
from typing import Any

import pytest

from ai_coach.web.marks import due
from ai_coach.web.survey import SURVEY_MARKS, checkin_due, marks_of

STATIC = Path(__file__).parent.parent / "src" / "ai_coach" / "web" / "static"


def marks(**fields: Any) -> dict[str, Any]:
    return {"ratings": [], "feel": [], "slips": [], "done": None, "food": []} | fields


FEEL = {"score": 4, "text": None, "mood": None, "stress": None, "logged_at": "x"}
RATED = {"focus": 4, "fatigue": 2, "effort": 3, "text": None, "logged_at": "x"}
DONE = {"done": 1, "logged_at": "x"}


def test_survey_marks_table() -> None:
    assert SURVEY_MARKS == {
        "evening": ("checkin",),
        "feel": ("feel",),
        "focus": ("rating",),
        "none": ("done",),
        "who5": ("who5",),
    }


@pytest.mark.parametrize(
    ("survey", "expected"),
    [
        ("evening", ("checkin",)),
        ("feel", ("feel",)),
        ("focus", ("rating",)),
        ("none", ("done",)),
        ("who5", ("who5",)),
        (None, ("checkin",)),
        ("мусор", ()),
    ],
)
def test_marks_of(survey: str | None, expected: tuple[str, ...]) -> None:
    assert tuple(marks_of(survey)) == expected


def test_feel_is_due_without_own_feel() -> None:
    assert checkin_due("feel", marks(), evening=True) is True


def test_feel_is_not_due_with_own_feel() -> None:
    assert checkin_due("feel", marks(feel=[FEEL]), evening=False) is False


def test_focus_is_due_without_rating() -> None:
    assert checkin_due("focus", marks(), evening=True) is True


def test_focus_is_not_due_with_rating() -> None:
    assert checkin_due("focus", marks(ratings=[RATED]), evening=False) is False


def test_none_is_due_without_mark() -> None:
    assert checkin_due("none", marks(), evening=True) is True


@pytest.mark.parametrize("done", [1, 0])
def test_none_is_not_due_with_done_or_skipped(done: int) -> None:
    assert checkin_due("none", marks(done={**DONE, "done": done}), evening=False) is False


@pytest.mark.parametrize("survey", ["evening", None])
def test_evening_and_null_follow_evening_flag(survey: str | None) -> None:
    assert checkin_due(survey, marks(), evening=False) is True
    assert checkin_due(survey, marks(), evening=True) is False


def test_due_checkin_uses_survey_and_only_when_past() -> None:
    assert due("checkin", marks(), True, True, survey="feel") is True
    assert due("checkin", marks(feel=[FEEL]), False, True, survey="feel") is False
    assert due("checkin", marks(), True, False, survey="feel") is False


def test_due_checkin_none_survey_ignores_evening() -> None:
    assert due("checkin", marks(), True, True, survey="none") is True
    assert due("checkin", marks(done=DONE), False, True, survey="none") is False


def test_due_checkin_without_survey_is_evening() -> None:
    assert due("checkin", marks(), False, True) is True
    assert due("checkin", marks(), True, True) is False


def test_due_survey_does_not_touch_other_kinds() -> None:
    assert due("task", marks(), True, True, survey="feel") is True
    assert due("task", marks(ratings=[RATED]), True, True, survey="feel") is False


def test_survey_tabs_in_js_equal_survey_marks_in_python() -> None:
    script = (STATIC / "marks-model.js").read_text(encoding="utf-8")
    block = script.split("const SURVEY_TABS = {", 1)[1].split("};", 1)[0]
    found = {
        key: tuple(re.findall(r'"([^"]+)"', tabs))
        for key, tabs in re.findall(r"(\w+):\s*\[([^\]]*)\]", block)
    }
    assert found == {k: tuple(v) for k, v in SURVEY_MARKS.items()}
