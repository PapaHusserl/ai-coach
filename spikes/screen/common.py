"""Общее для скриптов спайка экранного времени. Одноразовый код, не продакшен."""

import json
import re
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


# окна ∩ not-afk. Бакеты ищет сам сервер по префиксу (hostname в код не попадает);
# если хостов несколько, find_bucket берёт первый подходящий бакет.
QUERY_HEAD = [
    'window = flood(query_bucket(find_bucket("aw-watcher-window_")));',
    'afk = flood(query_bucket(find_bucket("aw-watcher-afk_")));',
    'afk = filter_keyvals(afk, "status", ["not-afk"]);',
    "events = filter_period_intersect(window, afk);",
]
# Порядок классов в categorize. Решение 18: заголовок, подходящий под оба (например ~/projects/msa),
# считается hobby. Наблюдение на живом AW (v0.14.1, 2026-10-19): при равных классах побеждает
# ПОСЛЕДНИЙ в списке, поэтому hobby стоит последним; порядок менять нельзя.
TITLE_CATS = ("work", "hobby")
# work/hobby/browser -> set[app в нижнем регистре]; "title" -> {app: {cat: [regex]}}
Rules = dict[str, Any]


def title_regex(patterns: list[str]) -> str:
    """Одна regex на класс, без учёта регистра."""
    return "(?i)(?:" + "|".join(patterns) + ")"


def screen_query(rules: Rules) -> list[str]:
    """Без [title.*] — слияние по app. Приложения из [title.<app>] размечает сам сервер
    (categorize по title) и сливает по (app, $category)."""
    title = rules.get("title", {})
    if not title:
        return [*QUERY_HEAD, 'events = merge_events_by_keys(events, ["app"]);',
                "RETURN = sort_by_duration(events);"]
    lines = [
        *QUERY_HEAD,
        f"rest = exclude_keyvals(events, \"app\", {json.dumps(list(title))});",
        'rest = merge_events_by_keys(rest, ["app"]);',
        "res = rest;",
    ]
    for n, (app, cats) in enumerate(title.items()):
        classes = [
            [
                [cat],
                {"type": "regex", "regex": title_regex(cats[cat]), "select_keys": ["title"]},
            ]
            for cat in TITLE_CATS
            if cats.get(cat)
        ]
        lines += [
            f"t{n} = filter_keyvals(events, \"app\", {json.dumps([app])});",
            f"t{n} = categorize(t{n}, {json.dumps(classes, ensure_ascii=False)});",
            f't{n} = merge_events_by_keys(t{n}, ["app", "$category"]);',
            f"res = concat(res, t{n});",
        ]
    lines.append("RETURN = sort_by_duration(res);")
    return lines


def _category_of(data: dict[str, Any]) -> str:
    """$category из ответа сервера ("" — приложение без разметки по заголовку)."""
    cat = data.get("$category")
    return "/".join(cat) if isinstance(cat, list) else ""


def screen_seconds(
    periods: list[tuple[datetime, datetime]], rules: Rules | None = None
) -> list[dict[tuple[str, str], float]]:
    """По каждому периоду: (app, $category) -> секунды активного окна. События режутся по границам
    периода самим сервером; страховка — сумма не больше длины периода (иначе exit)."""
    body = {
        "query": screen_query(rules or {}),
        "timeperiods": [f"{a.isoformat()}/{b.isoformat()}" for a, b in periods],
    }
    result = []
    for (a, b), events in zip(periods, aw_post("/api/0/query/", body), strict=True):
        per_app: dict[tuple[str, str], float] = {}
        for e in events:
            # merge_events_by_keys оставляет в data заголовок первого события группы (проверено,
            # и без [title.*]); читаем только app и $category, остальное не трогаем и не храним
            data = e.get("data") or {}
            key = (data.get("app") or "", _category_of(data))
            per_app[key] = per_app.get(key, 0) + e.get("duration", 0)
        if sum(per_app.values()) > (b - a).total_seconds() + 1:
            print("сервер не обрезал события по границам периода — спайк неприменим")
            sys.exit(1)
        result.append(per_app)
    return result


def title_seconds(
    period: tuple[datetime, datetime], app: str, limit: int = 40
) -> list[tuple[float, str]]:
    """Заголовки окон app за период: (секунды, title), по убыванию. Только для tty."""
    query = [
        *QUERY_HEAD,
        f"events = filter_keyvals(events, \"app\", {json.dumps([app])});",
        'events = merge_events_by_keys(events, ["title"]);',
        "events = sort_by_duration(events);",
        f"RETURN = limit_events(events, {limit});",
    ]
    body = {"query": query, "timeperiods": [f"{period[0].isoformat()}/{period[1].isoformat()}"]}
    events = aw_post("/api/0/query/", body)[0]
    return [(e.get("duration", 0), (e.get("data") or {}).get("title") or "") for e in events]


def load_rules(path: Path | None = None) -> Rules:
    """work/hobby/browser -> app в нижнем регистре; title -> {app: {work|hobby: [regex]}}.
    Ошибка в regex — одна строка и exit до запроса."""
    path = path or OUT / "screen_rules.toml"
    if not path.exists():
        print("нет spikes/out/screen_rules.toml — все приложения будут неразмеченными")
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    rules: Rules = {
        cat: {a.lower() for a in v.get("apps", [])} for cat, v in data.items() if cat != "title"
    }
    rules["title"] = {}
    for app, cats in data.get("title", {}).items():
        for key in cats:
            if key not in TITLE_CATS:
                print(f'screen_rules.toml: в [title."{app}"] ключ {key!r} не из {list(TITLE_CATS)}')
                sys.exit(1)
        for cat in TITLE_CATS:
            if not cats.get(cat):
                continue
            try:
                re.compile(title_regex(cats[cat]))  # склеенная строка, как уйдёт на сервер
            except re.error as e:
                print(f'screen_rules.toml: плохая regex в [title."{app}"].{cat}: {e}')
                sys.exit(1)
        rules["title"][app] = {cat: list(cats.get(cat, [])) for cat in TITLE_CATS}
    return rules


def classify(app: str, rules: Rules) -> str:
    """work / hobby / browser / unmarked (неразмеченное)."""
    for cat in ("work", "hobby", "browser"):
        if app.lower() in rules.get(cat, set()):
            return cat
    return "unmarked"


def by_category(per_app: dict[tuple[str, str], float], rules: Rules) -> dict[str, float]:
    """Категория из разметки сервера по заголовку (work/hobby), иначе classify(app):
    cmux без совпадения попадает в [work].apps -> work."""
    out = {"work": 0.0, "hobby": 0.0, "browser": 0.0, "unmarked": 0.0}
    for (app, cat), sec in per_app.items():
        out[cat if cat in TITLE_CATS else classify(app, rules)] += sec
    return out


def title_split(per_app: dict[tuple[str, str], float], rules: Rules) -> dict[str, float]:
    """Приложения с правилами по заголовку: work / hobby / none (без правила), секунды."""
    out = {"work": 0.0, "hobby": 0.0, "none": 0.0}
    for (app, cat), sec in per_app.items():
        if app in rules.get("title", {}):
            out[cat if cat in TITLE_CATS else "none"] += sec
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
