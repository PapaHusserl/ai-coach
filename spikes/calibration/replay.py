"""Разведка v2.9: прогон сигналов по истории живой базы (только чтение). Вывод - счёт, без личных значений."""
import os, sqlite3, sys
from collections import Counter
from datetime import date, timedelta
from statistics import median, quantiles

from ai_coach.load import overload as ov, sleep as sl, illness as il, deviations as dv
from ai_coach.mcp_server import tools

DB = os.path.expanduser("~/.local/share/ai-coach/coach.db")
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

def days(a, b):
    d = date.fromisoformat(a)
    while d.isoformat() <= b:
        yield d.isoformat(); d += timedelta(days=1)

FIRST, LAST = sys.argv[1], sys.argv[2]
try:
    rows = tools.load(conn, "2026-09-20", LAST)["rows"]
    tss = {r["date"]: r["tss"] for r in rows}
    loadrow = {r["date"]: r for r in rows}
except Exception as e:
    print("load error", e); tss, loadrow = {}, {}

sig = Counter(); n = 0; totals = []; parts = Counter(); src = Counter()
perday = {}
for d in days(FIRST, LAST):
    n += 1
    o = ov.overload_report(conn, d, tss)
    s = sl.sleep_report(conn, d)
    i = il.illness_report(conn, d, tss, s)
    de = tools.day_deviations(conn, d, loadrow.get(d))
    kinds = [x["kind"] for x in o["signals"]] + [x["kind"] for x in s["signals"]] + [x["kind"] for x in i["signals"]]
    for x in o["signals"]:
        if x["kind"] == "recovery_drop":
            for k in x["value"]: kinds.append("recovery_drop:" + k)
    kinds += ["dev:" + x["kind"] for x in de]
    if i["out_today"]: kinds.append("ill:out_day")
    if i["rhr_high"]: kinds.append("ill:rhr_high")
    if i["hrv_low"]: kinds.append("ill:hrv_low")
    if i["rhr_high"] or i["hrv_low"]: kinds.append("ill:any")
    if i["out_today"] is None: kinds.append("ill:nodata")
    if s["norm_h"] is None: kinds.append("sleep:nonorm")
    for k in set(kinds): sig[k] += 1
    perday[d] = set(kinds)
    e = ov.day_entries(conn, d, d, tss)[0]
    totals.append(e["total"])
    work = ov.hours(e, "work_hours")
    parts["tss"] += ov.W_TSS * (e.get("tss") or 0)
    parts["work"] += ov.W_WORK * work
    parts["hobby"] += ov.W_HOBBY * ov.hours(e, "hobby_hours")
    parts["evening"] += ov.W_EVENING * (e.get("work_evening_hours") or 0)
    parts["todo"] += ov.W_TODO * (e.get("todo_closed") or 0)
    parts["grooming"] += ov.W_GROOMING * (e.get("grooming_done") or 0)
    parts["weekend"] += ov.W_WEEKEND * work if e.get("weekend") else 0
    src["work:" + ("manual" if e.get("manual_work_hours") is not None else "screen" if e.get("screen_work_hours") is not None else "calendar")] += 1
    if (e.get("work_evening_hours") or 0) > 0: src["evening_cal>0"] += 1
    if (e.get("screen_evening_hours") or 0) > 1: src["screen_evening>1h"] += 1

print(f"дней {n} ({FIRST}..{LAST})")
for k, v in sorted(sig.items()): print(f"  {k}: {v}")
tot = sum(parts.values())
print("доля слагаемых total_load, %:", {k: round(100 * v / tot) for k, v in parts.items()})
print("источник часов работы:", dict(src))
qs = quantiles(totals, n=10)
high = sum(t >= ov.TOTAL_HIGH for t in totals)
print(f"total >= TOTAL_HIGH: {high} дней из {n}; медиана/порог = {median(totals)/ov.TOTAL_HIGH:.2f}; p90/порог = {qs[8]/ov.TOTAL_HIGH:.2f}; max/порог = {max(totals)/ov.TOTAL_HIGH:.2f}")
for thr in (0.6, 0.7, 0.8, 0.9):
    print(f"  порог ×{thr}: дней выше {sum(t >= thr*ov.TOTAL_HIGH for t in totals)}")
# совпадения: дни с симптомами / низким самочувствием против сигналов
bad = {d for d, k in perday.items() if "dev:symptoms" in k or "dev:wellbeing" in k}
print("дней с симптомами в тексте или оценкой <= 2:", len(bad))
for name in ("illness_risk", "ill:out_day", "ill:any", "ill:rhr_high", "ill:hrv_low", "dev:hrv", "short_night", "sleep_debt", "dev:wellbeing_below", "dev:mood_below", "recovery_drop", "total_streak"):
    on = {d for d, k in perday.items() if name in k}
    print(f"  {name}: дней {len(on)}, из них в плохие дни {len(on & bad)}, плохих дней без сигнала {len(bad - on)}")
if "--dates" in sys.argv:
    for d, k in perday.items(): print(d, sorted(x for x in k if not x.startswith("sleep:")))
