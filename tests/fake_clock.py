"""Подмена «сейчас» для тестов: в репо своей точки подмены времени нет, поэтому
datetime и date заменяются во всех модулях ai_coach.
Ограничение: freeze вызывать после импорта ai_coach.*; модули, импортируемые лениво
(внутри функций) уже после вызова, не покрываются."""

import sys
from datetime import date, datetime

import pytest


def freeze(monkeypatch: pytest.MonkeyPatch, moment: str) -> None:
    fixed = datetime.fromisoformat(moment)

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return cls.fromtimestamp(fixed.timestamp(), tz)

    class FakeDate(date):
        @classmethod
        def today(cls):  # type: ignore[no-untyped-def]
            return cls(fixed.year, fixed.month, fixed.day)

    for name, module in list(sys.modules.items()):
        if not name.startswith("ai_coach") or module is None:
            continue
        if getattr(module, "datetime", None) is datetime:
            monkeypatch.setattr(module, "datetime", FakeDatetime)
        if getattr(module, "date", None) is date:
            monkeypatch.setattr(module, "date", FakeDate)
