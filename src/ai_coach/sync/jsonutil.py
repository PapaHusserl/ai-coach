"""Общее для sync и import."""

import json
from typing import Any


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
