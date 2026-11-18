"""Разведка v2.9, Р9: рабочий экран вечером (19:00→04:00) из ActivityWatch за окно. Только чтение AW и базы,
в базу ничего не пишется; печать - счёт дней."""
import os, sqlite3
from datetime import date, timedelta
from ai_coach.load import overload as ov
from ai_coach.mcp_server import tools
from ai_coach.store.journal import EVENING_CUTOFF
from ai_coach.workload.config import load_config
from ai_coach.workload.screen import AwReader, _at, by_category
from ai_coach.workload.service import EVENING_FROM

A, N = date(2026, 10, 10), 39  # два дня запаса перед окном 10-12…11-17 для серий
days = [A + timedelta(days=i) for i in range(N)]
cfg = load_config().screen
periods = [(_at(d, EVENING_FROM), _at(d + timedelta(days=1), EVENING_CUTOFF)) for d in days]
res = AwReader(cfg).fetch(periods)
work = [by_category(r, cfg)["work"] / 3600 if r else None for r in res]
allscr = [sum(r.values()) / 3600 if r else None for r in res]
win = work[2:]
print("дней окна:", len(win), "; с событиями окон вечером:", sum(w is not None for w in win))
conn = sqlite3.connect(f"file:{os.path.expanduser('~/.local/share/ai-coach/coach.db')}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
B = (A + timedelta(days=N - 1)).isoformat()
tss = {r["date"]: r["tss"] for r in tools.load(conn, "2026-09-20", B)["rows"]}
ent = ov.day_entries(conn, A.isoformat(), B, tss)
cal = [e.get("work_evening_hours") or 0 for e in ent]
print("календарь вечером > 0, дней окна:", sum(c > 0 for c in cal[2:]))
def streak3(fl): return sum(1 for i in range(2, len(fl)) if fl[i] and fl[i - 1] and fl[i - 2])
for th in (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
    fl = [(w or 0) > th if th == 0 else (w or 0) >= th for w in work]
    print(f"рабочий экран вечером {'> 0' if th == 0 else '>= ' + str(th)} ч: дней {sum(fl[2:])} из {len(win)}; дней с серией 3 подряд {streak3(fl)}")
share = [w / a for w, a in zip(win, allscr[2:]) if w is not None and a]
print("доля рабочего в экране вечера, средняя, %:", round(100 * sum(share) / len(share)) if share else None)
# вклад в total при Р6 (W_GROOMING 0.2, порог 12): экран главнее календаря
ov.W_GROOMING = 0.2
for wev in (0.0, 0.5, 1.0):
    tot = []
    for e, w in zip(ent, work):
        ev = w if w is not None else (e.get("work_evening_hours") or 0)
        t = ov.total_load({**e, "work_evening_hours": 0}) + wev * ev
        tot.append(t)
    fl = [t >= 12.0 for t in tot]
    print(f"W_EVENING={wev} по рабочему экрану вечера: дней total >= 12: {sum(fl[2:])}; total_streak {streak3(fl)}")
wd = [d.weekday() < 5 for d in days][2:]
print("рабочий экран вечером >= 1 ч: в будни", sum(1 for w, b in zip(win, wd) if b and (w or 0) >= 1), "из", sum(wd), "; в выходные", sum(1 for w, b in zip(win, wd) if not b and (w or 0) >= 1), "из", len(wd) - sum(wd))
