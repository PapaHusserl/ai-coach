"""Разведка v2.9, Р2 = «только третий»: правила illness против одного эпизода (третья серия). Только счёт."""
import os, sqlite3
from datetime import date, timedelta
from ai_coach.load import illness as il, deviations as dv
from ai_coach.store.garmin_data import list_recovery_days
from ai_coach.store.journal import list_wellbeing
conn = sqlite3.connect(f"file:{os.path.expanduser('~/.local/share/ai-coach/coach.db')}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
rows = list_recovery_days(conn, "2025-11-01", "2026-11-18"); by = {r["date"]: r for r in rows}
marks = list_wellbeing(conn, "2026-10-07", "2026-11-17")
A = [(date(2026, 10, 7) + timedelta(days=i)).isoformat() for i in range(42)]
bad = set()
for d in A:
    m = dv.main_wellbeing([x for x in marks if x["date"] == d])
    if m and (m["score"] <= 2 or dv.find_symptoms(m["texts"])): bad.add(d)
iso = lambda d, k: (date.fromisoformat(d) + timedelta(days=k)).isoformat()
starts = sorted(d for d in bad if iso(d, -1) not in bad and iso(d, -2) not in bad)
s3 = starts[-1]
ep = {d for d in bad if d >= s3}
zone = {iso(s3, k) for k in range(-3, 0)} | ep
print("кандидатов:", len(starts), "; дней третьей серии:", len(ep), "; зона (серия и 3 дня до):", len(zone), "; дней окна вне зоны:", len(set(A) - zone))
def streaked(on, n): return {d for d in on if all(iso(d, -i) in on for i in range(n))}
picks = (("И", lambda f: f["out"]), ("ИЛИ", lambda f: f["rhr_high"] or f["hrv_low"]), ("HRV", lambda f: f["hrv_low"]))
for k in (0.5, 0.75, 1.0):
    il.SWC_K = k
    fl = {d: il.day_flags(by.get(d, {}), il.corridor(rows, date.fromisoformat(d), "rhr"), il.corridor(rows, date.fromisoformat(d), "hrv")) for d in A}
    for name, pick in picks:
        for n in (1, 2):
            on = streaked({d for d, f in fl.items() if pick(f)}, n)
            hit = [d for d in sorted(on) if iso(s3, -3) <= d <= iso(s3, 7)]
            lead = (date.fromisoformat(s3) - date.fromisoformat(hit[0])).days if hit else None
            print(f"K={k} {name} {n}д: дней {len(on)}, в зоне {len(on & zone)}, вне зоны {len(on - zone)}, опережение {lead}")
