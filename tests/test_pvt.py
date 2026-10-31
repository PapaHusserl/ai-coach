"""Тест реакции PVT-B: summarize, format_summary, run_test/_trial (фейки) и терминал (pty)."""

import itertools
import os
import pty
import random
import select
import termios
import tty
from collections.abc import Iterable, Iterator
from typing import Any

import pytest

from ai_coach import pvt


class Env:
    """Фейковые часы и клавиша: событие - None (клавиши не было до таймаута) или мс до нажатия."""

    def __init__(self, events: Iterable[float | None]) -> None:
        self.events: Iterator[float | None] = iter(events)
        self.now = 0.0
        self.timeouts: list[float] = []
        self.shown: list[str] = []

    def clock(self) -> float:
        return self.now

    def wait_key(self, timeout_s: float) -> bool:
        self.timeouts.append(timeout_s)
        event = next(self.events)
        if event is None:
            self.now += timeout_s
            return False
        self.now += event / 1000
        return True

    def run(self, duration_s: float, seed: int = 0) -> list[int | None]:
        return pvt.run_test(
            duration_s, random.Random(seed), self.clock, self.wait_key, self.shown.append
        )


def first_pause_s() -> float:
    return random.Random(0).randint(pvt.ISI_MIN_MS, pvt.ISI_MAX_MS) / 1000


# --- summarize ---


def test_summarize_full_example() -> None:
    assert pvt.summarize([250, 300, 400, None]) == {
        "trials": 4,
        "false_starts": 1,
        "lapses": 1,
        "mean_rt_ms": 317,
        "median_rt_ms": 300,
        "slow10_ms": 400,
        "speed": 3.28,
    }


@pytest.mark.parametrize(("count", "slow_count"), [(10, 1), (11, 2), (30, 3)])
def test_summarize_slowest_share_is_ceil(count: int, slow_count: int) -> None:
    rts: list[int | None] = [100 * (i + 1) for i in range(count)]
    expected = round(sum(100 * (count - i) for i in range(slow_count)) / slow_count)
    assert pvt.summarize(rts)["slow10_ms"] == expected


def test_summarize_no_response_counts_as_slow_and_in_speed() -> None:
    result = pvt.summarize([200, pvt.NO_RESPONSE_MS])
    assert result["slow10_ms"] == pvt.NO_RESPONSE_MS
    assert result["lapses"] == 1
    assert result["speed"] == 2.55


@pytest.mark.parametrize("trials", [[], [None, None]])
def test_summarize_without_rt_has_none(trials: list[int | None]) -> None:
    result = pvt.summarize(trials)
    assert (result["trials"], result["false_starts"], result["lapses"]) == (
        len(trials),
        len(trials),
        0,
    )
    for key in ("mean_rt_ms", "median_rt_ms", "slow10_ms", "speed"):
        assert result[key] is None


def test_summarize_lapse_is_strictly_above_threshold() -> None:
    assert pvt.summarize([pvt.LAPSE_MS])["lapses"] == 0
    assert pvt.summarize([pvt.LAPSE_MS + 1])["lapses"] == 1


# --- format_summary ---


def test_format_summary_full() -> None:
    row = pvt.summarize([250, 300, 400, None])
    assert pvt.format_summary(row) == (
        "медиана 300 мс, среднее 317, медленные 10 % 400, скорость 3,28/с, "
        "провалы 1, фальстарты 1 (проб 4)"
    )


def test_format_summary_without_rt() -> None:
    row = pvt.summarize([None, None, None])
    assert pvt.format_summary(row) == "нет проб с ответом, фальстарты 3 (проб 3)"


# --- run_test / _trial ---


def test_early_key_is_false_start_and_stimulus_not_shown() -> None:
    env = Env([500])
    assert pvt.run_test(0.001, random.Random(0), env.clock, env.wait_key, env.shown.append) == [
        None
    ]
    assert env.shown == ["Рано"]
    assert len(env.timeouts) == 1


def test_key_after_stimulus_gives_rt() -> None:
    env = Env([None, 280])
    assert env.run(0.001) == [280]
    assert env.shown == [pvt.STIMULUS, "280 мс"]


def test_no_response_is_ten_seconds_and_test_goes_on() -> None:
    env = Env([None, None, None, 300])
    assert env.run(first_pause_s() + 10.0 + 0.001) == [pvt.NO_RESPONSE_MS, 300]
    assert env.shown[:2] == [pvt.STIMULUS, "10000 мс"]
    assert env.timeouts[1] == pvt.NO_RESPONSE_MS / 1000


def test_rt_below_false_start_threshold_is_false_start() -> None:
    env = Env([None, pvt.FALSE_START_MS - 1])
    assert env.run(0.001) == [None]
    assert env.shown == [pvt.STIMULUS, "Рано"]


def test_rt_at_false_start_threshold_is_valid() -> None:
    env = Env([None, pvt.FALSE_START_MS])
    assert env.run(0.001) == [pvt.FALSE_START_MS]


def test_loop_ends_when_duration_reached_exactly() -> None:
    env = Env([None, 300, None, 300])
    assert len(env.run(first_pause_s() + 0.3)) == 1


def test_loop_continues_just_before_duration() -> None:
    env = Env([None, 300, None, 300])
    assert len(env.run(first_pause_s() + 0.3 + 0.001)) == 2


def test_zero_duration_runs_no_trials() -> None:
    env = Env([])
    assert env.run(0) == []
    assert env.timeouts == []


def test_pauses_within_isi_range_and_vary() -> None:
    env = Env(itertools.cycle([None, 300]))
    trials = env.run(60)
    assert len(trials) > 5
    pauses = env.timeouts[0::2]
    assert all(pvt.ISI_MIN_MS / 1000 <= p <= pvt.ISI_MAX_MS / 1000 for p in pauses)
    assert len(set(pauses)) > 1
    assert set(env.timeouts[1::2]) == {pvt.NO_RESPONSE_MS / 1000}


# --- терминал (pty) ---


@pytest.fixture
def raw_pty() -> Iterator[tuple[int, int]]:
    master, slave = pty.openpty()
    tty.setraw(slave)
    yield master, slave
    os.close(master)
    os.close(slave)


@pytest.fixture
def pty_pair() -> Iterator[tuple[int, int]]:
    master, slave = pty.openpty()
    yield master, slave
    os.close(master)
    os.close(slave)


def same_modes(a: list[Any], b: list[Any]) -> bool:
    # lflag сравниваем по ICANON и ECHO: ядро macOS добавляет служебный бит PENDIN
    flags = termios.ICANON | termios.ECHO
    return a[:3] == b[:3] and a[3] & flags == b[3] & flags and a[4:] == b[4:]


def test_cbreak_clears_icanon_and_restores(pty_pair: tuple[int, int]) -> None:
    _, slave = pty_pair
    before = termios.tcgetattr(slave)
    assert before[3] & termios.ICANON
    with pvt.cbreak(slave):
        assert not termios.tcgetattr(slave)[3] & termios.ICANON
    assert termios.tcgetattr(slave)[3] & termios.ICANON
    assert same_modes(termios.tcgetattr(slave), before)


def test_cbreak_restores_after_exception(pty_pair: tuple[int, int]) -> None:
    _, slave = pty_pair
    before = termios.tcgetattr(slave)
    with pytest.raises(RuntimeError), pvt.cbreak(slave):
        raise RuntimeError("boom")
    assert termios.tcgetattr(slave)[3] & termios.ICANON
    assert same_modes(termios.tcgetattr(slave), before)


def test_wait_key_true_when_byte_arrives(raw_pty: tuple[int, int]) -> None:
    master, slave = raw_pty
    os.write(master, b" ")
    assert pvt.terminal_wait_key(1.0, fd=slave) is True


def test_wait_key_false_on_timeout(raw_pty: tuple[int, int]) -> None:
    _, slave = raw_pty
    assert pvt.terminal_wait_key(0.05, fd=slave) is False


@pytest.mark.parametrize("byte", [b"\x1b", b"\x03"])
def test_wait_key_interrupt_keys(raw_pty: tuple[int, int], byte: bytes) -> None:
    master, slave = raw_pty
    os.write(master, byte)
    with pytest.raises(KeyboardInterrupt):
        pvt.terminal_wait_key(1.0, fd=slave)


def test_wait_key_without_limit_returns_buffered_key(raw_pty: tuple[int, int]) -> None:
    master, slave = raw_pty
    os.write(master, b"x")
    assert pvt.terminal_wait_key(None, fd=slave) is True


def test_wait_key_reads_one_byte(raw_pty: tuple[int, int]) -> None:
    master, slave = raw_pty
    os.write(master, b"ab")
    pvt.terminal_wait_key(1.0, fd=slave)
    assert pvt.terminal_wait_key(1.0, fd=slave) is True
    assert pvt.terminal_wait_key(0.05, fd=slave) is False


# --- terminal_show ---


@pytest.fixture
def show_fakes(
    monkeypatch: pytest.MonkeyPatch, raw_pty: tuple[int, int]
) -> Iterator[dict[str, Any]]:
    _, slave = raw_pty
    calls: dict[str, Any] = {"sleep": [], "flush": []}
    monkeypatch.setattr(pvt.time, "sleep", lambda s: calls["sleep"].append(s))
    monkeypatch.setattr(pvt.termios, "tcflush", lambda fd, q: calls["flush"].append((fd, q)))
    stdin = os.fdopen(os.dup(slave), "r", closefd=True)
    monkeypatch.setattr(pvt.sys, "stdin", stdin)
    calls["fd"] = stdin.fileno()
    yield calls
    stdin.close()


def test_show_stimulus_prints_without_pause_or_flush(
    show_fakes: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    pvt.terminal_show(pvt.STIMULUS)
    assert capsys.readouterr().out == pvt.STIMULUS + "\n"
    assert show_fakes["sleep"] == []
    assert show_fakes["flush"] == []


@pytest.mark.parametrize("text", ["312 мс", "Рано", "10000 мс"])
def test_show_result_pauses_and_flushes_input(
    show_fakes: dict[str, Any], capsys: pytest.CaptureFixture[str], text: str
) -> None:
    pvt.terminal_show(text)
    assert capsys.readouterr().out == text + "\n"
    assert show_fakes["sleep"] == [pvt.FEEDBACK_S]
    assert show_fakes["flush"] == [(show_fakes["fd"], termios.TCIFLUSH)]


def test_show_result_discards_pending_keys(
    monkeypatch: pytest.MonkeyPatch, raw_pty: tuple[int, int]
) -> None:
    master, slave = raw_pty
    monkeypatch.setattr(pvt, "FEEDBACK_S", 0)
    stdin = os.fdopen(os.dup(slave), "r", closefd=True)
    monkeypatch.setattr(pvt.sys, "stdin", stdin)
    try:
        os.write(master, b" ")
        assert select.select([slave], [], [], 1.0)[0]
        pvt.terminal_show("312 мс")
        assert not select.select([slave], [], [], 0.05)[0]
    finally:
        stdin.close()
