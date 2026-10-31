"""Тест реакции PVT-B (3 минуты): проба за пробой, итоги и терминал. Без typer и без базы."""

import math
import os
import random
import select
import statistics
import sys
import termios
import time
import tty
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

DURATION_S = 180
ISI_MIN_MS = 1000
ISI_MAX_MS = 4000
LAPSE_MS = 355
FALSE_START_MS = 100
NO_RESPONSE_MS = 10000
FEEDBACK_S = 0.5
SLOW_SHARE = 0.1
STIMULUS = "●●●  ЖМИ  ●●●"
EARLY = "Рано"
INTERRUPT_KEYS = (b"\x1b", b"\x03")


def _trial(
    rng: random.Random,
    clock: Callable[[], float],
    wait_key: Callable[[float], bool],
    show: Callable[[str], None],
) -> int | None:
    """Одна проба: None - фальстарт, число - время реакции в мс (нет ответа - NO_RESPONSE_MS)."""
    pause_s = rng.randint(ISI_MIN_MS, ISI_MAX_MS) / 1000
    if wait_key(pause_s):
        show(EARLY)
        return None
    show(STIMULUS)
    shown = clock()
    if not wait_key(NO_RESPONSE_MS / 1000):
        show(f"{NO_RESPONSE_MS} мс")
        return NO_RESPONSE_MS
    rt = round((clock() - shown) * 1000)
    if rt < FALSE_START_MS:
        show(EARLY)
        return None
    show(f"{rt} мс")
    return rt


def run_test(
    duration_s: float,
    rng: random.Random,
    clock: Callable[[], float],
    wait_key: Callable[[float], bool],
    show: Callable[[str], None],
) -> list[int | None]:
    """Пробы, пока не прошло duration_s по clock. None - фальстарт, число - время реакции, мс."""
    start = clock()
    trials: list[int | None] = []
    while clock() - start < duration_s:
        trials.append(_trial(rng, clock, wait_key, show))
    return trials


def summarize(trials: list[int | None]) -> dict[str, Any]:
    """Итоги: счётчики по всем пробам, остальное - по пробам с временем реакции (без фальстартов).
    Нет ни одной такой пробы - None в mean_rt_ms, median_rt_ms, slow10_ms, speed."""
    rts = [t for t in trials if t is not None]
    result: dict[str, Any] = {
        "trials": len(trials),
        "false_starts": len(trials) - len(rts),
        "lapses": sum(1 for rt in rts if rt > LAPSE_MS),
        "mean_rt_ms": None,
        "median_rt_ms": None,
        "slow10_ms": None,
        "speed": None,
    }
    if rts:
        slowest = sorted(rts, reverse=True)[: math.ceil(round(len(rts) * SLOW_SHARE, 6))]
        result["mean_rt_ms"] = round(statistics.mean(rts))
        result["median_rt_ms"] = round(statistics.median(rts))
        result["slow10_ms"] = round(statistics.mean(slowest))
        result["speed"] = round(statistics.mean(1000 / rt for rt in rts), 2)
    return result


def format_summary(row: dict[str, Any]) -> str:
    """Строка итогов теста (ключи как у summarize)."""
    tail = f"фальстарты {row['false_starts']} (проб {row['trials']})"
    if row["median_rt_ms"] is None:
        return f"нет проб с ответом, {tail}"
    speed = f"{row['speed']:.2f}".replace(".", ",")
    return (
        f"медиана {row['median_rt_ms']} мс, среднее {row['mean_rt_ms']}, "
        f"медленные 10 % {row['slow10_ms']}, скорость {speed}/с, "
        f"провалы {row['lapses']}, {tail}"
    )


@contextmanager
def cbreak(fd: int) -> Generator[None]:
    """Терминал fd без построчного ввода; атрибуты возвращаются при выходе."""
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def terminal_wait_key(timeout_s: float | None, fd: int | None = None) -> bool:
    """Ждёт клавишу до timeout_s (None - без предела): True - нажата, False - время вышло.
    Esc и Ctrl-C - KeyboardInterrupt."""
    source = sys.stdin.fileno() if fd is None else fd
    if not select.select([source], [], [], timeout_s)[0]:
        return False
    if os.read(source, 1) in INTERRUPT_KEYS:
        raise KeyboardInterrupt
    return True


def terminal_show(text: str) -> None:
    """Строка на экран; после результата пробы - пауза FEEDBACK_S и сброс нажатий за это время."""
    print(text, flush=True)
    if text != STIMULUS:
        time.sleep(FEEDBACK_S)
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
