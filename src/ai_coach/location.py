"""Место компьютера через CoreLocation (pyobjc): координаты округляются до 2 знаков сразу.

CoreLocation импортируется лениво, внутри `read_place`. Разрешение на геолокацию получает
приложение «Python» целиком (docs/research-location.md). Конфиг модуль не читает: запасное
место приходит в `resolve_place` готовым `Place`.
"""

import functools
import importlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

TIMEOUT = 10.0
DENIED_CODE = 1  # kCLErrorDenied


class LocationError(Exception):
    """Места нет. Причина (args[0]): unavailable / off / denied / timeout."""


@dataclass(frozen=True)
class Place:
    lat: float
    lon: float


def rounded(lat: float, lon: float) -> Place:
    """Место с координатами до 2 знаков: точнее координаты из модуля не выходят."""
    return Place(round(lat, 2), round(lon, 2))


def place_reason(enabled: bool, error_code: int | None) -> str:
    """Причина отказа: службы выключены - off, ошибка с кодом 1 - denied, иначе - timeout."""
    if not enabled:
        return "off"
    if error_code == DENIED_CODE:
        return "denied"
    return "timeout"


@functools.cache
def _delegate_class() -> Any:
    foundation = importlib.import_module("Foundation")
    objc = importlib.import_module("objc")

    class Delegate(foundation.NSObject):  # pyright: ignore[reportUntypedBaseClass]
        def init(self) -> Any:
            self = objc.super(Delegate, self).init()
            self.coords = None
            self.error_code = None
            self.status = 0
            return self

        def locationManagerDidChangeAuthorization_(self, manager: Any) -> None:
            # Статус до первого обратного вызова всегда 0: читаем его только здесь.
            self.status = int(manager.authorizationStatus())
            if self.status in (3, 4):
                manager.requestLocation()

        def locationManager_didUpdateLocations_(self, manager: Any, locations: Any) -> None:
            if locations:
                point = locations[-1].coordinate()
                self.coords = (float(point.latitude), float(point.longitude))

        def locationManager_didFailWithError_(self, manager: Any, error: Any) -> None:
            self.error_code = int(error.code())

    return Delegate


def read_place(timeout: float = TIMEOUT) -> Place:
    """Место от macOS или LocationError. Код 1 при статусе 0 (окна не было) не выход:
    ждём до таймаута, затем причина по `place_reason`."""
    try:
        core_location = importlib.import_module("CoreLocation")
        foundation = importlib.import_module("Foundation")
    except ImportError:
        raise LocationError("unavailable") from None
    manager_class = core_location.CLLocationManager
    enabled = bool(manager_class.locationServicesEnabled())
    if not enabled:
        raise LocationError(place_reason(False, None))
    manager = manager_class.alloc().init()
    delegate = _delegate_class().alloc().init()
    manager.setDelegate_(delegate)
    manager.setDesiredAccuracy_(core_location.kCLLocationAccuracyKilometer)
    manager.requestWhenInUseAuthorization()
    manager.requestLocation()
    loop = foundation.NSRunLoop.currentRunLoop()
    deadline = time.monotonic() + timeout
    while delegate.coords is None and time.monotonic() < deadline:
        loop.runUntilDate_(foundation.NSDate.dateWithTimeIntervalSinceNow_(0.2))
        if delegate.error_code is not None and delegate.status in (1, 2):
            break
    if delegate.coords is None:
        raise LocationError(place_reason(enabled, delegate.error_code))
    return rounded(*delegate.coords)


def resolve_place(
    fallback: Place | None, locate: Callable[[], Place] | None = None
) -> tuple[Place, str]:
    """Место и его источник: от macOS - "macos"; при отказе запасное - "config" (округлённое);
    нет запаса - исходная LocationError."""
    try:
        return (locate or read_place)(), "macos"
    except LocationError:
        if fallback is None:
            raise
        return rounded(fallback.lat, fallback.lon), "config"
