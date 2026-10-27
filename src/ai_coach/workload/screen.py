"""Экранное время из ActivityWatch: в базу идут только часы по категориям за день.

Запрос к aw-server (query API) отдаёт секунды по (приложение, категория); заголовки окон и
названия приложений дальше этого модуля не идут: читаем из ответа только app и $category,
в базу кладём часы (source='screen', raw_json пусто). День - 04:00→04:00 по местному времени
(как ручные часы), вечер - 19:00→04:00. День без событий окон счётчиков не получает.
"""

import json
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta
from typing import Any, Protocol, cast

from ai_coach.store.journal import EVENING_CUTOFF
from ai_coach.workload.config import TITLE_CATS, ScreenConfig, title_regex
from ai_coach.workload.service import EVENING_FROM, SECONDS_IN_HOUR

SOURCE = "screen"
QUERY_PATH = "/api/0/query/"
TIMEOUT = 30
UNMARKED_NOTE_FROM = 0.15  # доля неразмеченного, с которой sync пишет замечание
SLACK_SECONDS = 1
# окна ∩ not-afk. Бакеты ищет сам сервер по префиксу (hostname в код не попадает);
# если хостов несколько, find_bucket берёт первый подходящий бакет.
QUERY_HEAD = [
    'window = flood(query_bucket(find_bucket("aw-watcher-window_")));',
    'afk = flood(query_bucket(find_bucket("aw-watcher-afk_")));',
    'afk = filter_keyvals(afk, "status", ["not-afk"]);',
    "events = filter_period_intersect(window, afk);",
]

Period = tuple[datetime, datetime]
PerApp = dict[tuple[str, str], float]


class ScreenError(Exception):
    """Экранное время не прочитано (AW не отвечает, ответ не тот)."""


class ScreenReader(Protocol):
    """Что нужно sync от читателя экрана: AwReader или его подмена в тестах. На каждый период -
    секунды по (приложение, категория по заголовку: work/hobby или пусто)."""

    def fetch(self, periods: list[Period]) -> list[PerApp]: ...


def _query_literal(value: Any) -> str:
    """Литерал для query2. Парсер query2 не снимает экранирование JSON: `\\\\w` дошло бы до regex
    как `\\\\w` (литеральный слэш), поэтому слэши отдаём как есть. Кавычки в regex запрещены
    (конфиг), иначе `\\"` сломало бы разбор."""
    return json.dumps(value, ensure_ascii=False).replace("\\\\", "\\")


def query_head(config: ScreenConfig) -> list[str]:
    """QUERY_HEAD; с приложениями созвонов их окна считаются и во время afk: окна ∩ (not-afk ∪
    окна созвонов). Имена - как в конфиге: filter_keyvals сравнивает регистр точно."""
    if not config.meeting_names:
        return QUERY_HEAD
    meeting = json.dumps(list(config.meeting_names), ensure_ascii=False)
    return [
        *QUERY_HEAD[:3],
        f'meet = filter_keyvals(window, "app", {meeting});',
        "active = period_union(afk, meet);",
        "events = filter_period_intersect(window, active);",
    ]


def screen_query(config: ScreenConfig) -> list[str]:
    """Без [screen.title.*] - слияние по app. Приложения с разметкой по заголовку размечает сам
    сервер (categorize) и сливает по (app, $category)."""
    head = query_head(config)
    if not config.title:
        return [
            *head,
            'events = merge_events_by_keys(events, ["app"]);',
            "RETURN = sort_by_duration(events);",
        ]
    titled = json.dumps(list(config.title), ensure_ascii=False)
    lines = [
        *head,
        f'rest = exclude_keyvals(events, "app", {titled});',
        'rest = merge_events_by_keys(rest, ["app"]);',
        "res = rest;",
    ]
    for n, (app, cats) in enumerate(config.title.items()):
        classes = [
            [
                [cat],
                {"type": "regex", "regex": title_regex(cats[cat]), "select_keys": ["title"]},
            ]
            for cat in TITLE_CATS
            if cats.get(cat)
        ]
        lines += [
            f't{n} = filter_keyvals(events, "app", {json.dumps([app], ensure_ascii=False)});',
            f"t{n} = categorize(t{n}, {_query_literal(classes)});",
            f't{n} = merge_events_by_keys(t{n}, ["app", "$category"]);',
            f"res = concat(res, t{n});",
        ]
    lines.append("RETURN = sort_by_duration(res);")
    return lines


def _category_of(data: dict[str, Any]) -> str:
    """$category из ответа сервера ("" - приложение без разметки по заголовку)."""
    cat = data.get("$category")
    return "/".join(cast(list[str], cat)) if isinstance(cat, list) else ""


class AwReader:
    """Читает aw-server по HTTP: один POST на все периоды. Из ответа берутся только app и
    $category и длительность; заголовки окон не читаются и не хранятся."""

    def __init__(self, config: ScreenConfig) -> None:
        self.config = config

    def fetch(self, periods: list[Period]) -> list[PerApp]:
        body = {
            "query": screen_query(self.config),
            "timeperiods": [f"{a.isoformat()}/{b.isoformat()}" for a, b in periods],
        }
        request = urllib.request.Request(
            self.config.url.rstrip("/") + QUERY_PATH,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                answer = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ScreenError(f"aw-server: HTTP {e.code} на запрос query") from None
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            raise ScreenError("aw-server не отвечает - запущен ли ActivityWatch?") from None
        except ValueError:
            raise ScreenError("aw-server вернул не JSON") from None
        if not isinstance(answer, list) or len(cast(list[Any], answer)) != len(periods):
            raise ScreenError("aw-server вернул ответ не по числу периодов")
        result: list[PerApp] = []
        for events in cast(list[list[dict[str, Any]]], answer):
            per_app: PerApp = {}
            for event in events:
                data = cast(dict[str, Any], event.get("data") or {})
                key = (data.get("app") or "", _category_of(data))
                per_app[key] = per_app.get(key, 0) + event.get("duration", 0)
            result.append(per_app)
        return result


def classify(app: str, config: ScreenConfig) -> str:
    """work / hobby / browser / unmarked (неразмеченное). Приложение созвонов без другой
    разметки - work."""
    name = app.lower()
    for cat, apps in (("work", config.work), ("hobby", config.hobby), ("browser", config.browser)):
        if name in apps:
            return cat
    return "work" if name in config.meeting else "unmarked"


def by_category(per_app: PerApp, config: ScreenConfig) -> dict[str, float]:
    """Секунды по work/hobby/browser/unmarked: категория по заголовку от сервера (work/hobby),
    иначе classify(app)."""
    out = {"work": 0.0, "hobby": 0.0, "browser": 0.0, "unmarked": 0.0}
    for (app, cat), seconds in per_app.items():
        out[cat if cat in TITLE_CATS else classify(app, config)] += seconds
    return out


def _at(day: date, moment: time) -> datetime:
    return datetime.combine(day, moment).astimezone()


def read_screen(
    reader: ScreenReader,
    config: ScreenConfig,
    first: date,
    last: date,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Счётчики экрана за дни first..last включительно: screen_work_hours, screen_hobby_hours,
    screen_browser_hours и screen_evening_hours (всё за экраном 19:00→04:00) - часы с двумя
    знаками. Строки для upsert_counter: date, kind, value, source='screen', raw_json None.
    День без событий окон пропускается. Сумма за период больше его длины - ScreenError.
    Вторым значением - замечания для итога sync: неразмеченного больше 15 %."""
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    periods: list[Period] = []
    for day in days:
        end = _at(day + timedelta(days=1), EVENING_CUTOFF)
        periods += [(_at(day, EVENING_CUTOFF), end), (_at(day, EVENING_FROM), end)]
    results = reader.fetch(periods)
    if len(results) != len(periods):
        raise ScreenError("ответ не по числу периодов")
    for (start, end), per_app in zip(periods, results, strict=True):
        if sum(per_app.values()) > (end - start).total_seconds() + SLACK_SECONDS:
            raise ScreenError("сервер не обрезал события по границам периода")
    rows: list[dict[str, Any]] = []
    unmarked = total = 0.0
    for n, day in enumerate(days):
        whole, evening = results[2 * n], results[2 * n + 1]
        if not whole:
            continue
        cats = by_category(whole, config)
        unmarked += cats["unmarked"]
        total += sum(cats.values())
        hours = {
            "screen_work_hours": cats["work"],
            "screen_hobby_hours": cats["hobby"],
            "screen_browser_hours": cats["browser"],
            "screen_evening_hours": sum(evening.values()),
        }
        for kind, seconds in hours.items():
            value = round(seconds / SECONDS_IN_HOUR, 2)
            rows.append(
                {
                    "date": day.isoformat(),
                    "kind": kind,
                    "value": value,
                    "source": SOURCE,
                    "raw_json": None,
                }
            )
    notes: list[str] = []
    if total and unmarked / total > UNMARKED_NOTE_FROM:
        notes.append(f"экран: неразмеченное {round(unmarked / total * 100)} %")
    return rows, notes
