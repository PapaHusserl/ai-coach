"""Разведка Н8 (только чтение): переключения экрана и длинные рабочие отрезки, дни сигнала по порогам.

Запуск: uv run python spikes/calibration/switching.py 2026-10-12 2026-11-24
Печать - только счёт дней; значения, названия приложений и окон в терминал не выводятся (репо публичное).
"""
import json, os, sqlite3, statistics, sys, urllib.request
from datetime import date, datetime, time, timedelta

from ai_coach.workload.config import TITLE_CATS, load_config, title_regex
from ai_coach.workload.screen import _query_literal, classify, demand_of, query_head

A, B = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
cfg = load_config().screen
assert cfg is not None


def query():
    lines = [*query_head(cfg)]
    titled = json.dumps(list(cfg.title), ensure_ascii=False)
    lines += [f'res = exclude_keyvals(events, "app", {titled});']
    for n, (app, cats) in enumerate(cfg.title.items()):
        classes = [[[c], {"type": "regex", "regex": title_regex(cats[c]), "select_keys": ["title"]}]
                   for c in TITLE_CATS if cats.get(c)]
        lines += [f't{n} = filter_keyvals(events, "app", {json.dumps([app], ensure_ascii=False)});',
                  f"t{n} = categorize(t{n}, {_query_literal(classes)});", f"res = concat(res, t{n});"]
    lines.append("RETURN = sort_by_timestamp(res);")
    return lines


def at(d, t):
    return datetime.combine(d, t).astimezone()


days = [A + timedelta(days=i) for i in range((B - A).days + 1)]
periods = [(at(d, time(4)), at(d + timedelta(days=1), time(4))) for d in days]
body = {"query": query(), "timeperiods": [f"{a.isoformat()}/{b.isoformat()}" for a, b in periods]}
req = urllib.request.Request(cfg.url.rstrip("/") + "/api/0/query/", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
answer = json.loads(urllib.request.urlopen(req, timeout=120).read())


def cat_of(data):
    c = data.get("$category")
    c = "/".join(c) if isinstance(c, list) else ""
    return c if c in TITLE_CATS else classify(data.get("app") or "", cfg)


def timeline(events, six=False):
    """Отрезки (начало, конец, класс, созвон); при six работа делится на вызов/помеху/прочую."""
    out = []
    for e in events:
        data = e.get("data") or {}
        s = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        c = cat_of(data)
        if six and c == "work":
            c = demand_of(data.get("app") or "", cfg) or "work"
        out.append((s, s + timedelta(seconds=e["duration"]), c, (data.get("app") or "").lower() in cfg.meeting))
    return sorted(out)


def switches(tl, min_s):
    seq = [c for s, e, c, _ in tl if (e - s).total_seconds() >= min_s]
    return sum(a != b for a, b in zip(seq, seq[1:]))


def spans_of(tl, pause_min, cats):
    """Отрезки (мин) из событий cats; разрыв - промежуток без таких событий не короче pause_min."""
    spans = []
    start = reach = None
    for s, e, c, _ in tl:
        if c not in cats:
            continue
        if reach is None or (s - reach).total_seconds() >= pause_min * 60:
            if start is not None:
                spans.append((reach - start).total_seconds() / 60)
            start, reach = s, e
        else:
            reach = max(reach, e)
    if start is not None:
        spans.append((reach - start).total_seconds() / 60)
    return spans


def longest(tl, pause_min, cats):
    return max(spans_of(tl, pause_min, cats), default=0.0)


def signal_days(vals, k=None, pct=None, base=28, minimum=14):
    """(дней сигнала, дней с готовой базой): значение выше k*медианы (или перцентиля pct) base предыдущих дней."""
    fired = ready = 0
    for i, v in enumerate(vals):
        prev = [x for x in vals[max(0, i - base):i] if x is not None]
        if v is None or len(prev) < minimum:
            continue
        ready += 1
        if k is not None:
            fired += v >= k * statistics.median(prev)
        else:
            fired += v >= statistics.quantiles(prev, n=100)[pct - 1]
    return fired, ready


def rates(trs, min_s):
    return [switches(t, min_s) / active if active >= 1 else None for t, active in trs]


rows = []
for ev in answer:
    tl = timeline(ev)
    rows.append((tl, sum((e - s).total_seconds() for s, e, _, _ in tl) / 3600) if tl else None)
have = [r for r in rows if r]
print("дней окна", len(days), "; с событиями экрана", len(have), "; активных от 1 ч", sum(r[1] >= 1 for r in have),
      "; от 3 ч", sum(r[1] >= 3 for r in have))
print("неразмеченного больше 15 %, дней", sum(
    sum((e - s).total_seconds() for s, e, c, _ in tl if c == "unmarked") / 3600 / active > 0.15 for tl, active in have))
print("событий в день: до 1000 -", sum(len(r[0]) < 1000 for r in have), "; 1000-5000 -",
      sum(1000 <= len(r[0]) < 5000 for r in have), "; от 5000 -", sum(len(r[0]) >= 5000 for r in have))


def show(title, variants):
    print(f"--- {title}: дней сигнала / дней с готовой базой")
    for name, vals in variants:
        line = f"{name}:"
        for k in (1.25, 1.5, 2.0):
            line += f" >= {k} x медианы {signal_days(vals, k=k)};"
        print(line + f" >= p75 {signal_days(vals, pct=75)}; >= p90 {signal_days(vals, pct=90)}")


four = [r if r else (None, 0) for r in rows]
show("4 категории, в час", [(f"события от {m} с" if m else "все события", rates(four, m)) for m in (0, 5, 30)])
show("4 категории, за день", [("события от 5 с", [switches(r[0], 5) if r and r[1] >= 1 else None for r in rows])])
six = [(timeline(ev, True), r[1]) if r else (None, 0) for ev, r in zip(answer, rows)]
show("6 классов, в час", [(f"события от {m} с" if m else "все события", rates(six, m)) for m in (0, 5)])

# согласие с Claude-переключениями
DB = os.path.expanduser("~/.local/share/ai-coach/coach.db")
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cl = dict(conn.execute("select date, value from day_counters where kind='claude_switches' and date between ? and ?",
                       (A.isoformat(), B.isoformat())))
cvals = [cl.get(d.isoformat()) for d in days]
print("--- Claude: дней со счётчиком", sum(v is not None for v in cvals), "; с переключениями > 0",
      sum((v or 0) > 0 for v in cvals))
show("claude_switches за день", [("значение", cvals)])
pairs = [(a, b) for a, b in zip(rates(four, 5), cvals) if a is not None and b is not None]
if len(pairs) > 5:
    corr = statistics.correlation([a for a, _ in pairs], [b for _, b in pairs], method="ranked")
    print("пар экран+Claude", len(pairs), "; ранговая связь", "положительная" if corr > 0.2 else "нет/отрицательная")

print("--- длинные отрезки: дней, где самый длинный отрезок не короче порога; последняя колонка - дней сигнала против "
      "1,5 x медианы из дней с готовой базой")
for cats, name in ((("work", "challenge", "hindrance"), "работа"), (("work", "hobby", "browser", "unmarked"), "весь экран")):
    for pause in (3, 5, 10, 15):
        if name == "весь экран" and pause in (3, 15):
            continue
        tls = six if name == "работа" else four
        got = [longest(r[0], pause, cats) if r[0] else None for r in tls]
        line = f"{name:10s} пауза от {pause:2d} мин:"
        for lim in (60, 90, 120, 150, 180):
            line += f" >= {lim} мин: {sum(g is not None and g >= lim for g in got):2d};"
        print(line + f" против медианы: {signal_days(got, k=1.5)}")

# заходы в приложения-помехи без созвонов
visits = []
for tl, _ in six:
    if tl is None:
        visits.append(None)
        continue
    seq = ["h" if c == "hindrance" and not m else "x" for s, e, c, m in tl if (e - s).total_seconds() >= 5]
    visits.append(sum(a != "h" and b == "h" for a, b in zip(seq, seq[1:])))
got = [v for v in visits if v is not None]
print("--- заходы в помехи без созвонов: дней", len(got), "; больше нуля", sum(v > 0 for v in got),
      "; не больше 3", sum(v <= 3 for v in got), "; от 10", sum(v >= 10 for v in got), "; от 40", sum(v >= 40 for v in got))
for k in (1.25, 1.5):
    print("заходы >=", k, "x медианы:", signal_days(visits, k=k))

# календарь: окна между рабочими встречами короче 30 мин
ev = conn.execute("select date, start_at, end_at from calendar_events where all_day=0 and category='work' and "
                  "coalesce(status,'')!='cancelled' and coalesce(my_status,'')!='declined' and date between ? and ? "
                  "order by start_at", (A.isoformat(), B.isoformat())).fetchall()
byday = {}
for d, s, e in ev:
    byday.setdefault(d, []).append((datetime.fromisoformat(s), datetime.fromisoformat(e)))
short = sum(any(0 < (b[0] - a[1]).total_seconds() / 60 < 30 for a, b in zip(v, v[1:])) for v in byday.values())
print("--- календарь: дней с рабочими встречами", len(byday), "; с 2+ встречами", sum(len(v) >= 2 for v in byday.values()),
      "; с окном короче 30 мин", short)
