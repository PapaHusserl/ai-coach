"""Счётчики груминга из ~/bin/hb-watch/{done,pending}: только чтение, имён файлов в базе нет."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

SOURCE = "hb_watch"


class GroomingError(Exception):
    """Каталог hb-watch не читается."""


def read_grooming(root: Path, start: date, end: date, today: date) -> list[dict[str, Any]]:
    """Счётчики груминга: grooming_done за каждый день start..end включительно (в том числе 0)
    и grooming_pending снимком на today. Считаются все файлы по каталогам (содержимое не
    читается); день done - местная дата mtime. Нет каталога - пусто."""
    if not (root / "done").is_dir() or not (root / "pending").is_dir():
        return []
    try:
        stamps = [p.stat().st_mtime for p in (root / "done").iterdir() if p.is_file()]
        pending = sum(1 for p in (root / "pending").iterdir() if p.is_file())
    except OSError as e:
        raise GroomingError(f"hb-watch не читается: {type(e).__name__}") from None
    days = [datetime.fromtimestamp(s).date().isoformat() for s in stamps]
    counters: list[dict[str, Any]] = []
    for offset in range((end - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        counters.append(
            {"date": day, "kind": "grooming_done", "value": days.count(day), "source": SOURCE}
        )
    counters.append(
        {"date": today.isoformat(), "kind": "grooming_pending", "value": pending, "source": SOURCE}
    )
    return counters
