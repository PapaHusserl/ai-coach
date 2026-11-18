"""Разведка v2.9: слагаемые total_load против отклика (только чтение; вывод - ранговые корреляции и счёт)."""
import os, sqlite3, sys
from datetime import date, timedelta
from statistics import mean, median
from ai_coach.load import overload as ov, deviations as dv
from ai_coach.mcp_server import tools
from ai_coach.store.garmin_data import list_daily_metrics
from ai_coach.store.journal import list_wellbeing

DB = os.path.expanduser("~/.local/share/ai-coach/coach.db")
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
A, B = sys.argv[1], sys.argv[2]
tss = {r["date"]: r["tss"] for r in tools.load(conn, "2026-09-20", B)["rows"]}
ent = ov.day_entries(conn, A, B, tss)
met = {m["date"]: m for m in list_daily_metrics(conn, A, (date.fromisoformat(B) + timedelta(days=1)).isoformat())}
marks = list_wellbeing(conn, A, B)
wb = {}
for e in ent:
    wb[e["date"]] = dv.main_wellbeing([m for m in marks if m["date"] == e["date"]])

def rank(xs):
    s = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and xs[s[j + 1]] == xs[s[i]]: j += 1
        for k in range(i, j + 1): r[s[k]] = (i + j) / 2 + 1
        i = j + 1
    return r
def rho(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 8: return None, len(pairs)
    rx, ry = rank([p[0] for p in pairs]), rank([p[1] for p in pairs])
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry)); den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return (round(num / den, 2) if den else None), len(pairs)

nxt = lambda d: (date.fromisoformat(d) + timedelta(days=1)).isoformat()
comp = {
    "total": [e["total"] for e in ent],
    "work_h": [ov.hours(e, "work_hours") for e in ent],
    "hobby_h": [ov.hours(e, "hobby_hours") for e in ent],
    "tss": [e.get("tss") or 0 for e in ent],
    "todo_closed": [e.get("todo_closed") or 0 for e in ent],
    "grooming_done": [e.get("grooming_done") or 0 for e in ent],
    "screen_evening_h": [e.get("screen_evening_hours") for e in ent],
    "total_без_груминга": [round(e["total"] - ov.W_GROOMING * (e.get("grooming_done") or 0), 2) for e in ent],
}
out = {
    "стресс вечера (тот же день)": [wb[e["date"]]["stress"] if wb[e["date"]] else None for e in ent],
    "настроение вечера": [wb[e["date"]]["mood"] if wb[e["date"]] else None for e in ent],
    "readiness завтра": [(met.get(nxt(e["date"])) or {}).get("readiness_score") for e in ent],
    "HRV ночи завтра": [(met.get(nxt(e["date"])) or {}).get("hrv_last_night") for e in ent],
}
print(f"дней {len(ent)}; |rho| значим при p<0.05 примерно от {0.42 if len(ent)<25 else 0.33}")
for c, xs in comp.items():
    print(c, {o: rho(xs, ys) for o, ys in out.items()})
tot = comp["total"]; ng = comp["total_без_груминга"]
print("дней total>=порог:", sum(t >= ov.TOTAL_HIGH for t in tot), "; без груминга:", sum(t >= ov.TOTAL_HIGH for t in ng))
print("дней, где груминг > половины total:", sum(1 for e in ent if e["total"] and ov.W_GROOMING * (e.get("grooming_done") or 0) > e["total"] / 2))
print("дней с грумингом > 0:", sum(1 for e in ent if (e.get("grooming_done") or 0) > 0), "; с календарными вечерними рабочими часами > 0:", sum(1 for e in ent if (e.get("work_evening_hours") or 0) > 0), "; с календарными рабочими часами > 0:", sum(1 for e in ent if (e.get("work_hours") or 0) > 0))
wk = [e for e in ent if e.get("weekend")]
print("дней сб/вс:", len(wk), "; с работой >= WEEKEND_WORK_MIN:", sum(1 for e in wk if ov.hours(e, "work_hours") >= ov.WEEKEND_WORK_MIN))
print("медиана рабочих часов / день (доля порога TOTAL_HIGH):", round(median(comp["work_h"]) / ov.TOTAL_HIGH, 2))
