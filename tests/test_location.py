import sys

import pytest

# Настоящие функции снимаем при импорте: autouse-фикстура conftest подменяет атрибуты модуля.
from ai_coach.location import (
    LocationError,
    Place,
    place_reason,
    read_place,
    resolve_place,
    rounded,
)

MACOS_PLACE = Place(52.52, 13.41)
FALLBACK = Place(52.5234, 13.4114)


def failing(reason: str):
    def locate(*args: object, **kwargs: object) -> Place:
        raise LocationError(reason)

    return locate


def test_rounded_keeps_two_digits() -> None:
    assert rounded(52.5234, 13.4114) == Place(52.52, 13.41)


def test_rounded_rounds_up_by_third_digit() -> None:
    assert rounded(52.5278, -13.4151) == Place(52.53, -13.42)


def test_read_place_without_corelocation_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "CoreLocation", None)
    with pytest.raises(LocationError) as caught:
        read_place(1)
    assert caught.value.args[0] == "unavailable"


def test_place_reason_services_off() -> None:
    assert place_reason(False, None) == "off"


def test_place_reason_services_off_wins_over_code() -> None:
    assert place_reason(False, 1) == "off"


def test_place_reason_code_one_is_denied() -> None:
    assert place_reason(True, 1) == "denied"


def test_place_reason_no_error_is_timeout() -> None:
    assert place_reason(True, None) == "timeout"


def test_place_reason_code_zero_is_timeout() -> None:
    assert place_reason(True, 0) == "timeout"


def test_resolve_place_macos_place_wins() -> None:
    place, source = resolve_place(FALLBACK, locate=lambda *a, **k: MACOS_PLACE)
    assert (place, source) == (MACOS_PLACE, "macos")


def test_resolve_place_does_not_touch_fallback_when_macos_answers() -> None:
    place, _ = resolve_place(Place(10.0, 20.0), locate=lambda *a, **k: MACOS_PLACE)
    assert place == MACOS_PLACE


def test_resolve_place_denied_uses_rounded_fallback() -> None:
    place, source = resolve_place(FALLBACK, locate=failing("denied"))
    assert (place, source) == (Place(52.52, 13.41), "config")


def test_resolve_place_denied_without_fallback_raises_same_error() -> None:
    with pytest.raises(LocationError) as caught:
        resolve_place(None, locate=failing("denied"))
    assert caught.value.args[0] == "denied"


def test_resolve_place_timeout_without_fallback_keeps_reason() -> None:
    with pytest.raises(LocationError) as caught:
        resolve_place(None, locate=failing("timeout"))
    assert caught.value.args[0] == "timeout"
