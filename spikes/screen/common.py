"""Общее для скриптов спайка экранного времени. Одноразовый код, не продакшен."""

import json
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
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


def aw_post(path: str, body: Any) -> Any:
    """POST к aw-server (query API); ошибки — как в aw_get, без hostname и тела запроса."""
    req = urllib.request.Request(
        AW_URL + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"aw-server: HTTP {e.code} на запрос query")
        sys.exit(1)
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        print("aw-server не отвечает на 127.0.0.1:5600 — запущен ли ActivityWatch?")
        sys.exit(1)


# окна ∩ not-afk, слияние по app. Бакеты ищет сам сервер по префиксу (hostname в код не попадает);
# если хостов несколько, find_bucket берёт первый подходящий бакет.
SCREEN_QUERY = [
    'window = flood(query_bucket(find_bucket("aw-watcher-window_")));',
    'afk = flood(query_bucket(find_bucket("aw-watcher-afk_")));',
    'afk = filter_keyvals(afk, "status", ["not-afk"]);',
    "events = filter_period_intersect(window, afk);",
    'events = merge_events_by_keys(events, ["app"]);',
    "RETURN = sort_by_duration(events);",
]


def screen_seconds(periods: list[tuple[datetime, datetime]]) -> list[dict[str, float]]:
    """По каждому периоду: app -> секунды активного окна. События режутся по границам периода
    самим сервером; страховка — сумма не больше длины периода (иначе exit)."""
    body = {
        "query": SCREEN_QUERY,
        "timeperiods": [f"{a.isoformat()}/{b.isoformat()}" for a, b in periods],
    }
    result = []
    for (a, b), events in zip(periods, aw_post("/api/0/query/", body), strict=True):
        per_app: dict[str, float] = {}
        for e in events:
            app = (e.get("data") or {}).get("app") or ""
            per_app[app] = per_app.get(app, 0) + e.get("duration", 0)
        if sum(per_app.values()) > (b - a).total_seconds() + 1:
            print("сервер не обрезал события по границам периода — спайк неприменим")
            sys.exit(1)
        result.append(per_app)
    return result


def load_rules(path: Path | None = None) -> dict[str, set[str]]:
    """category (work/hobby/browser) -> множество app в нижнем регистре."""
    path = path or OUT / "screen_rules.toml"
    if not path.exists():
        print("нет spikes/out/screen_rules.toml — все приложения будут неразмеченными")
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {cat: {a.lower() for a in v.get("apps", [])} for cat, v in data.items()}


def classify(app: str, rules: dict[str, set[str]]) -> str:
    """work / hobby / browser / unmarked (неразмеченное)."""
    for cat in ("work", "hobby", "browser"):
        if app.lower() in rules.get(cat, set()):
            return cat
    return "unmarked"


def by_category(per_app: dict[str, float], rules: dict[str, set[str]]) -> dict[str, float]:
    out = {"work": 0.0, "hobby": 0.0, "browser": 0.0, "unmarked": 0.0}
    for app, sec in per_app.items():
        out[classify(app, rules)] += sec
    return out


def day_bounds(day: date, from_hour: int = 0) -> tuple[datetime, datetime]:
    """День по местному времени: [from_hour:00, from_hour:00 следующего дня)."""
    start = datetime.combine(day, time(from_hour)).astimezone()
    return start, datetime.combine(day + timedelta(days=1), time(from_hour)).astimezone()


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
