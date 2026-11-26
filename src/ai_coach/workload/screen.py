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
from ai_coach.workload.config import DEMANDS, TITLE_CATS, ScreenConfig, title_regex
from ai_coach.workload.service import EVENING_FROM, SECONDS_IN_HOUR
from ai_coach.workload.timeline import Segment, counter_row, timeline_rows

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

    def timeline(self, periods: list[Period]) -> list[list[Segment]]: ...


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


def _title_lines(config: ScreenConfig, merge: bool) -> list[str]:
    """Строки запроса для приложений с разметкой по заголовку: categorize на сервере; merge -
    слияние событий (для часов), без него события остаются как есть (для ленты)."""
    titled = json.dumps(list(config.title), ensure_ascii=False)
    rest = f'rest = exclude_keyvals(events, "app", {titled});'
    lines = [rest, 'rest = merge_events_by_keys(rest, ["app"]);'] if merge else [rest]
    lines.append("res = rest;")
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
        ]
        if merge:
            lines.append(f't{n} = merge_events_by_keys(t{n}, ["app", "$category"]);')
        lines.append(f"res = concat(res, t{n});")
    return lines


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
    return [*head, *_title_lines(config, True), "RETURN = sort_by_duration(res);"]


def timeline_query(config: ScreenConfig) -> list[str]:
    """Как screen_query, но без слияния: события по порядку времени."""
    head = query_head(config)
    if not config.title:
        return [*head, "RETURN = sort_by_timestamp(events);"]
    return [*head, *_title_lines(config, False), "RETURN = sort_by_timestamp(res);"]


def _category_of(data: dict[str, Any]) -> str:
    """$category из ответа сервера ("" - приложение без разметки по заголовку)."""
    cat = data.get("$category")
    return "/".join(cast(list[str], cat)) if isinstance(cat, list) else ""


class AwReader:
    """Читает aw-server по HTTP: один POST на все периоды. Из ответа берутся только app и
    $category и длительность; заголовки окон не читаются и не хранятся."""

    def __init__(self, config: ScreenConfig, timeout: float = TIMEOUT) -> None:
        self.config = config
        self.timeout = timeout

    def _post(self, query: list[str], periods: list[Period]) -> list[list[dict[str, Any]]]:
        body = {
            "query": query,
            "timeperiods": [f"{a.isoformat()}/{b.isoformat()}" for a, b in periods],
        }
        request = urllib.request.Request(
            self.config.url.rstrip("/") + QUERY_PATH,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                answer = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ScreenError(f"aw-server: HTTP {e.code} на запрос query") from None
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            raise ScreenError("aw-server не отвечает - запущен ли ActivityWatch?") from None
        except ValueError:
            raise ScreenError("aw-server вернул не JSON") from None
        if not isinstance(answer, list) or len(cast(list[Any], answer)) != len(periods):
            raise ScreenError("aw-server вернул ответ не по числу периодов")
        return cast(list[list[dict[str, Any]]], answer)

    def fetch(self, periods: list[Period]) -> list[PerApp]:
        result: list[PerApp] = []
        for events in self._post(screen_query(self.config), periods):
            per_app: PerApp = {}
            for event in events:
                data = cast(dict[str, Any], event.get("data") or {})
                key = (data.get("app") or "", _category_of(data))
                per_app[key] = per_app.get(key, 0) + event.get("duration", 0)
            result.append(per_app)
        return result

    def timeline(self, periods: list[Period]) -> list[list[Segment]]:
        """Лента (начало, конец, класс) на каждый период; из событий читаются timestamp,
        duration, app и $category, заголовки не читаются."""
        answer = self._post(timeline_query(self.config), periods)
        return [[self._segment(event) for event in events] for events in answer]

    def _segment(self, event: dict[str, Any]) -> Segment:
        data = cast(dict[str, Any], event.get("data") or {})
        try:
            start = datetime.fromisoformat(event["timestamp"])
        except (KeyError, TypeError, ValueError):
            raise ScreenError("aw-server вернул событие ленты без времени") from None
        end = start + timedelta(seconds=event.get("duration", 0))
        return (start, end, segment_class(data.get("app") or "", _category_of(data), self.config))


def classify(app: str, config: ScreenConfig) -> str:
    """work / hobby / browser / unmarked (неразмеченное). Приложение созвонов без другой
    разметки - work."""
    name = app.lower()
    for cat, apps in (("work", config.work), ("hobby", config.hobby), ("browser", config.browser)):
        if name in apps:
            return cat
    return "work" if name in config.meeting else "unmarked"


def demand_of(app: str, config: ScreenConfig) -> str | None:
    """challenge / hindrance (приложение из [screen] challenge/hindrance) или None."""
    name = app.lower()
    if name in config.challenge:
        return "challenge"
    return "hindrance" if name in config.hindrance else None


def by_category(per_app: PerApp, config: ScreenConfig) -> dict[str, float]:
    """Секунды по work/hobby/browser/unmarked: категория по заголовку от сервера (work/hobby),
    иначе classify(app). challenge/hindrance - части work: секунды приложения из списков."""
    out = {"work": 0.0, "hobby": 0.0, "browser": 0.0, "unmarked": 0.0}
    out.update(dict.fromkeys(DEMANDS, 0.0))
    for (app, cat), seconds in per_app.items():
        cls = cat if cat in TITLE_CATS else classify(app, config)
        out[cls] += seconds
        demand = demand_of(app, config)
        if cls == "work" and demand:
            out[demand] += seconds
    return out


def segment_class(app: str, category: str, config: ScreenConfig) -> str:
    """Класс окна ленты: hobby / browser / unmarked как у by_category, работа - challenge /
    hindrance (по demand_of) или work."""
    cls = category if category in TITLE_CATS else classify(app, config)
    return (demand_of(app, config) or "work") if cls == "work" else cls


def _at(day: date, moment: time) -> datetime:
    return datetime.combine(day, moment).astimezone()


def read_screen(
    reader: ScreenReader,
    config: ScreenConfig,
    first: date,
    last: date,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Счётчики экрана за дни first..last включительно: screen_work_hours, screen_hobby_hours,
    screen_browser_hours и screen_evening_hours (всё за экраном 19:00→04:00) и
    screen_work_evening_hours (рабочая часть этого вечера) - часы с двумя
    знаками; при непустых challenge/hindrance в конфиге ещё screen_challenge_hours и
    screen_hindrance_hours (части работы). Дню с событиями и непустой лентой - ещё
    screen_stretch_hours (самый длинный рабочий отрезок, ч) и, если активного экрана не меньше
    часа, screen_switches_hour (переключений в час). Строки для upsert_counter: date, kind,
    value, source='screen', raw_json None.
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
    timelines = reader.timeline(periods[::2])
    if len(timelines) != len(days):
        raise ScreenError("лента не по числу периодов")
    rows: list[dict[str, Any]] = []
    marked = bool(config.challenge or config.hindrance)
    unmarked = total = 0.0
    for n, day in enumerate(days):
        whole, evening = results[2 * n], results[2 * n + 1]
        if not whole:
            continue
        cats = by_category(whole, config)
        unmarked += cats["unmarked"]
        total += cats["work"] + cats["hobby"] + cats["browser"] + cats["unmarked"]
        hours = {
            "screen_work_hours": cats["work"],
            "screen_hobby_hours": cats["hobby"],
            "screen_browser_hours": cats["browser"],
            "screen_evening_hours": sum(evening.values()),
            "screen_work_evening_hours": by_category(evening, config)["work"],
        }
        if marked:
            hours["screen_challenge_hours"] = cats["challenge"]
            hours["screen_hindrance_hours"] = cats["hindrance"]
        rows += [counter_row(day, k, round(sec / SECONDS_IN_HOUR, 2)) for k, sec in hours.items()]
        rows += timeline_rows(day, timelines[n])
    notes: list[str] = []
    if total and unmarked / total > UNMARKED_NOTE_FROM:
        notes.append(f"экран: неразмеченное {round(unmarked / total * 100)} %")
    if rows and not marked:
        notes.append("экран: вызов/помеха не размечены")
    return rows, notes
