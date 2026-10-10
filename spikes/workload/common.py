"""Общее для скриптов спайка источников нагрузки. Одноразовый код, не продакшен."""

import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "out"
PREFIX = "SPIKE "


def save_json(name: str, data: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def say(text: str) -> None:
    """Обезличенная печать: только счётчики и категории."""
    print(PREFIX + text)
