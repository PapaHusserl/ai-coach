"""Общее для скриптов спайка экранного времени. Одноразовый код, не продакшен."""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "out"
PREFIX = "SPIKE "
AW_URL = "http://127.0.0.1:5600"


def save_json(name: str, data: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def say(text: str) -> None:
    """Обезличенная печать: только счётчики и категории."""
    print(PREFIX + text)


def aw_get(path: str, **params: Any) -> Any:
    """GET к aw-server; если не отвечает — одна строка и exit 1, без трейсбэка."""
    url = AW_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # эндпоинт без id бакета (id содержит hostname)
        parts = path.split("/")
        shown = "/".join(parts[:4] + (["<bucket>"] + parts[5:] if len(parts) > 4 and parts[3] == "buckets" else parts[4:]))
        print(f"aw-server: HTTP {e.code} на {shown}")
        sys.exit(1)
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        print("aw-server не отвечает на 127.0.0.1:5600 — запущен ли ActivityWatch?")
        sys.exit(1)
