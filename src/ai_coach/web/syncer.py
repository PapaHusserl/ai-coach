"""Синк из пульта: поток-демон в процессе сервера, один запуск за раз (шаг П4, партия 3).
Успех и ошибка пишутся в sync_log самими run_sync/run_workload; error - текст сбоя Garmin."""

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_coach.garmin.client import GarminError, load_client
from ai_coach.store.db import open_db
from ai_coach.sync import sync as run_sync
from ai_coach.sync import sync_workload as run_workload

DAYS = 7
PAUSE = 0.5

_lock = threading.Lock()
_state: dict[str, Any] = {"running": False, "started_at": None, "error": None}


def status() -> dict[str, Any]:
    """running, started_at (начало последнего запуска), error (текст сбоя или None)."""
    with _lock:
        return dict(_state)


def _set(**values: Any) -> None:
    with _lock:
        _state.update(values)


def _run(db: str | Path | None) -> None:
    try:
        conn = open_db(db)
        try:
            try:
                run_sync(conn, load_client(), DAYS, pause=PAUSE)
            except GarminError as e:
                _set(error=str(e))
            run_workload(conn, DAYS)
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001 - поток не должен падать молча
        _set(error=str(e))
        traceback.print_exc(file=sys.stderr)
    finally:
        _set(running=False)


def start(db: str | Path | None) -> bool:
    """Запустить синк в фоне; False - уже идёт."""
    with _lock:
        if _state["running"]:
            return False
        _state.update(
            running=True,
            started_at=datetime.now().isoformat(timespec="seconds"),
            error=None,
        )
    threading.Thread(target=_run, args=(db,), daemon=True).start()
    return True
