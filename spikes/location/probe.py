"""Спайк П7 партии 0: даёт ли macOS место процессу Python (CoreLocation).

Запуск Владом в своём терминале (будет системное окно доступа к геолокации):
    uv run --with 'pyobjc-framework-CoreLocation==12.2.2' python spikes/location/probe.py main
    uv run --with 'pyobjc-framework-CoreLocation==12.2.2' python spikes/location/probe.py thread
Прогоны матрицы (--label): ghostty-main, ghostty-thread, trener-bang (из сессии тренер через !),
claude-code (процесс, запущенный Claude Code), после ручного включения, после отказа, без Wi-Fi.
Режим: main - менеджер и прокрутка NSRunLoop в главном потоке; thread - в фоновом потоке,
как вид пульта. Необязательно: --timeout N (секунд ожидания места, по умолчанию 90),
--label текст (метка прогона в выводе).
В stdout - статусы, коды ошибок и секунды; координаты не читаются и не печатаются.
"""

import argparse
import threading
import time

import CoreLocation as CL
import objc
from Foundation import NSBundle, NSDate, NSObject, NSRunLoop

PREFIX = "SPIKE "
STATUS = {
    0: "notDetermined",
    1: "restricted",
    2: "denied",
    3: "authorizedAlways",
    4: "authorizedWhenInUse",
}
ERROR = {0: "locationUnknown", 1: "denied", 2: "network", 18: "promptDeclined"}


def say(text: str) -> None:
    print(PREFIX + text, flush=True)


def status_name(manager) -> str:
    code = int(manager.authorizationStatus())
    return f"{code} {STATUS.get(code, '?')}"


class Delegate(NSObject):
    def init(self):
        self = objc.super(Delegate, self).init()
        self.start = time.monotonic()
        self.auth_changes = []  # (секунды, статус)
        self.location_at = None
        self.errors = []  # (секунды, код, домен)
        self.requested_at = 0.0
        return self

    def locationManagerDidChangeAuthorization_(self, manager):
        self.auth_changes.append((time.monotonic() - self.start, status_name(manager)))
        if int(manager.authorizationStatus()) in (3, 4):
            self.requested_at = time.monotonic() - self.start
            manager.requestLocation()

    def locationManager_didUpdateLocations_(self, manager, locations):
        # Координаты не читаем: только факт и время прихода.
        if self.location_at is None and locations:
            self.location_at = time.monotonic() - self.start

    def locationManager_didFailWithError_(self, manager, error):
        self.errors.append((time.monotonic() - self.start, int(error.code()), str(error.domain())))


def run(timeout: float) -> None:
    manager = CL.CLLocationManager.alloc().init()
    delegate = Delegate.alloc().init()
    manager.setDelegate_(delegate)
    manager.setDesiredAccuracy_(CL.kCLLocationAccuracyKilometer)
    say(f"thread={threading.current_thread().name}")
    say(f"services_enabled={bool(CL.CLLocationManager.locationServicesEnabled())}")
    say(f"status_before={status_name(manager)}")
    delegate.start = time.monotonic()
    if hasattr(manager, "requestWhenInUseAuthorization"):
        manager.requestWhenInUseAuthorization()
    manager.requestLocation()
    loop = NSRunLoop.currentRunLoop()
    reason = "timeout"
    while time.monotonic() - delegate.start < timeout:
        loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.2))
        if delegate.location_at is not None:
            reason = "received"
            break
        # Выход по ошибке - только когда статус уже не 0 и ошибка пришла после последнего запроса.
        answered = delegate.errors and delegate.errors[-1][0] > delegate.requested_at
        if int(manager.authorizationStatus()) != 0 and answered:
            reason = "error"
            break
    say(f"elapsed={time.monotonic() - delegate.start:.1f}s")
    for seconds, name in delegate.auth_changes:
        say(f"auth_change at {seconds:.1f}s -> {name}")
    for seconds, code, domain in delegate.errors:
        say(f"error code={code} {ERROR.get(code, '?')} domain={domain} at {seconds:.1f}s")
    say(f"status_after={status_name(manager)}")
    if reason == "received":
        say(f"location=received in {delegate.location_at:.1f}s")
    elif reason == "error":
        say("location=error (см. строки error)")
    else:
        say(f"location=timeout after {timeout:.0f}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["main", "thread"])
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    bundle = NSBundle.mainBundle()
    say(f"label={args.label} mode={args.mode}")
    say(f"bundle={bundle.bundleIdentifier()}")
    say(f"pyobjc={objc.__version__}")
    if args.mode == "main":
        run(args.timeout)
    else:
        worker = threading.Thread(target=run, args=(args.timeout,), name="probe-worker")
        worker.start()
        worker.join()


if __name__ == "__main__":
    main()
