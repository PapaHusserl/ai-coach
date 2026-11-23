"""Подмена «сейчас» для тестов: в репо своей точки подмены времени нет, поэтому
datetime и date заменяются во всех модулях ai_coach.
Ограничение: freeze вызывать после импорта ai_coach.*; модули, импортируемые лениво
(внутри функций) уже после вызова, не покрываются.
Повторный вызов freeze в том же тесте заменяет прежнюю подмену: действует последний момент."""

import sys
from datetime import date, datetime

import pytest


def _is_real_or_frozen(current: object, real: type) -> bool:
    """Настоящий класс или подмена прежнего freeze (метка _fake_clock)."""
    return current is real or getattr(current, "_fake_clock", False) is True


def freeze(monkeypatch: pytest.MonkeyPatch, moment: str) -> None:
    fixed = datetime.fromisoformat(moment)

    class FakeDatetime(datetime):
        _fake_clock = True

        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return cls.fromtimestamp(fixed.timestamp(), tz)

    class FakeDate(date):
        _fake_clock = True

        @classmethod
        def today(cls):  # type: ignore[no-untyped-def]
            return cls(fixed.year, fixed.month, fixed.day)

    for name, module in list(sys.modules.items()):
        if not name.startswith("ai_coach") or module is None:
            continue
        if _is_real_or_frozen(getattr(module, "datetime", None), datetime):
            monkeypatch.setattr(module, "datetime", FakeDatetime)
        if _is_real_or_frozen(getattr(module, "date", None), date):
            monkeypatch.setattr(module, "date", FakeDate)
