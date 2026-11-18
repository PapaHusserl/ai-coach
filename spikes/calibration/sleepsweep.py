"""Разведка v2.9: частота сигналов сна при разных порогах (только чтение, счёт ночей)."""
import os, sqlite3
from datetime import date, timedelta
from ai_coach.load import sleep as sl
conn = sqlite3.connect(f"file:{os.path.expanduser('~/.local/share/ai-coach/coach.db')}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
def run(a, b):
    out = []; d = date.fromisoformat(a)
    while d.isoformat() <= b:
        r = sl.sleep_report(conn, d.isoformat())
        if r["norm_h"] is not None and r["last_night_h"] is not None:
            out.append((d.isoformat(), r["norm_h"] - r["last_night_h"], r["debt_7_h"], r["debt_14_h"]))
        d += timedelta(days=1)
    return out
H = run("2026-03-01", "2026-11-17"); W = [x for x in H if x[0] >= "2026-10-12"]; API = [x for x in H if x[0] >= "2026-10-01"]; IMP = [x for x in H if x[0] < "2026-10-01"]
print("ночей: история", len(H), "импорт", len(IMP), "API", len(API), "окно 10-12..", len(W))
for short in (1.0, 1.5, 2.0):
    print(f"short_night >= {short}: история {sum(g >= short for _, g, _, _ in H)}, импорт {sum(g >= short for _, g, _, _ in IMP)}, API {sum(g >= short for _, g, _, _ in API)}, окно {sum(g >= short for _, g, _, _ in W)}")
for d7, d14 in ((3, 5), (4, 6), (5, 8), (6, 10), (3, 99), (4, 99), (5, 99)):
    f = lambda X: sum((a is not None and a >= d7) or (b is not None and b >= d14) for _, _, a, b in X)
    print(f"sleep_debt 7>={d7} или 14>={d14}: история {f(H)} ({100*f(H)//len(H)}%), импорт {f(IMP)}, API {f(API)}, окно {f(W)}")
