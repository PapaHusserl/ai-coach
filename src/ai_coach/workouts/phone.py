"""Тренировка на телефон без часов: сжатый payload во фрагменте ссылки на страницу-плеер."""

import base64
import json
import os
import re
import zlib
from typing import Any

PLAYER_VERSION = 1
MAX_FRAGMENT = 2000
PLAYER_URL = ""
PREFIX = f"v{PLAYER_VERSION}."


def player_url() -> str:
    """Адрес плеера: $AI_COACH_PLAYER_URL или PLAYER_URL."""
    url = os.environ.get("AI_COACH_PLAYER_URL") or PLAYER_URL
    if not url:
        raise ValueError("не задан адрес плеера")
    return url


def _num(value: float) -> float | int:
    """40.0 -> 40, чтобы в JSON не было лишних «.0»."""
    return int(value) if float(value) == int(value) else value


def _readable(code: str) -> str:
    """BARBELL_BACK_SQUAT -> Barbell back squat."""
    return code.replace("_", " ").capitalize()


def _clean(values: dict[str, Any]) -> dict[str, Any]:
    """Только непустые ключи."""
    return {key: value for key, value in values.items() if value not in (None, "", [], 0)}


def _strength_blocks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for item in spec["exercises"]:
        work = {"k": "work", "reps": item["reps"], "kg": _num(item["weight_kg"])}
        work = _clean(work | {"note": item.get("note")})
        steps = [work]
        if item["rest_seconds"]:
            steps.append({"k": "rest", "sec": _num(item["rest_seconds"])})
        title = item.get("title") or _readable(item["exercise"])
        blocks.append({"r": item["sets"], "t": title, "s": steps})
    return blocks


def _mobility_blocks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for item in spec["steps"]:
        title = item.get("title") or _readable(item["exercise"])
        work = _clean(
            {"k": "work", "sec": _num(item["seconds"]), "t": title, "note": item["description"]}
        )
        blocks.append({"r": 1, "s": [work]})
    return blocks


def _endurance_blocks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for item in spec["steps"]:
        kind = "work" if item["type"] == "interval" else item["type"]
        step = {"k": kind, "t": item.get("title"), "note": item.get("note")}
        if "meters" in item:
            step["m"] = _num(item["meters"])
        else:
            step["sec"] = _num(item["seconds"])
        if "pace_sec_per_km" in item:
            step["pace"] = [_num(x) for x in item["pace_sec_per_km"]]
        steps.append(_clean(step))
    return [{"r": 1, "s": steps}]


def player_payload(
    sport: str, spec: dict[str, Any], date: str, time: str | None = None
) -> dict[str, Any]:
    """Компактная форма v1 для плеера (только непустые ключи)."""
    if sport == "strength":
        blocks = _strength_blocks(spec)
    elif sport == "mobility":
        blocks = _mobility_blocks(spec)
    else:
        blocks = _endurance_blocks(spec)
    payload = {
        "v": PLAYER_VERSION,
        "n": spec["name"],
        "sp": sport,
        "d": date,
        "tm": time,
        "dur": spec.get("estimated_duration_secs"),
        "b": blocks,
    }
    return _clean(payload)


def encode_fragment(payload: dict[str, Any]) -> str:
    """JSON -> raw deflate -> base64url без «=» -> префикс v1."""
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = packer.compress(text.encode()) + packer.flush()
    fragment = PREFIX + base64.urlsafe_b64encode(packed).decode().rstrip("=")
    if len(fragment) > MAX_FRAGMENT:
        raise ValueError(
            f"ссылка {len(fragment)} символов, лимит {MAX_FRAGMENT}: "
            "сократи заметки/названия или раздели тренировку"
        )
    return fragment


def decode_fragment(fragment: str) -> dict[str, Any]:
    """Зеркало encode_fragment; мусор или другой префикс -> ValueError."""
    if not fragment.startswith(PREFIX):
        raise ValueError(f"фрагмент должен начинаться с {PREFIX}")
    body = fragment[len(PREFIX) :]
    try:
        packed = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        return json.loads(zlib.decompress(packed, -15).decode())
    except (ValueError, zlib.error) as e:
        raise ValueError(f"фрагмент не разобрать: {e}") from None


def workout_url(fragment: str, base_url: str) -> str:
    return f"{base_url}#{fragment}"


def workout_link_url(
    row: dict[str, Any] | None, workout_id: int, time: str | None = None
) -> dict[str, Any]:
    """Ответ со ссылкой на плеер для строки planned_workouts (None - такой нет); time - HH:MM."""
    if row is None:
        raise ValueError(f"Тренировки {workout_id} нет.")
    if row["status"] == "cancelled":
        raise ValueError(f"Тренировка {workout_id} отменена.")
    if time is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", time):
        raise ValueError(f"time должно быть HH:MM, получено: {time!r}")
    raw = row["workout_json"]
    spec = json.loads(raw) if isinstance(raw, str) else raw
    fragment = encode_fragment(player_payload(row["sport"], spec, row["date"], time))
    url = workout_url(fragment, player_url())
    return {
        "workout_id": workout_id,
        "name": row["name"],
        "date": row["date"],
        "url": url,
        "length": len(fragment),
    }
