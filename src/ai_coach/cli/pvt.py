"""Команда `coach pvt`: утренний тест реакции PVT-B, 3 минуты, только в терминале."""

import json
import random
import sys
import time
from datetime import datetime

import typer

from ai_coach.cli.journal import fail, now
from ai_coach.pvt import (
    DURATION_S,
    STIMULUS,
    cbreak,
    format_summary,
    run_test,
    summarize,
    terminal_show,
    terminal_wait_key,
)
from ai_coach.store.db import open_db
from ai_coach.store.journal import add_pvt, wellbeing_day


def pvt() -> None:
    """Тест реакции (3 минуты): жми пробел, как только появится стимул. Только в терминале.
    Esc или Ctrl-C - прервать без записи. До 04:00 запись идёт на вчера."""
    if not sys.stdin.isatty():
        fail("Тест реакции идёт только в терминале.")
    typer.echo(f"Жми пробел, как только появится {STIMULUS}; старт - любая клавиша.")
    try:
        with cbreak(sys.stdin.fileno()):
            terminal_wait_key(None)
            started_at = now()
            trials = run_test(
                DURATION_S, random.Random(), time.perf_counter, terminal_wait_key, terminal_show
            )
    except KeyboardInterrupt:
        fail("Прервано, не записано.")
    summary = summarize(trials)
    values = {
        "date": wellbeing_day(datetime.fromisoformat(started_at)),
        "started_at": started_at,
        "duration_s": DURATION_S,
        **summary,
        "rts": json.dumps(trials),
    }
    conn = open_db()
    try:
        with conn:
            add_pvt(conn, values)
    finally:
        conn.close()
    typer.echo(f"{format_summary(summary)} - записано.")
