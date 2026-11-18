"""Разведка v2.9: перебор порогов illness и сна по истории (только чтение, вывод - счёт дней)."""
import os, sqlite3
from datetime import date, timedelta
from ai_coach.load import illness as il, sleep as sl, deviations as dv
from ai_coach.store.garmin_data import list_recovery_days, list_sleep_nights
from ai_coach.store.journal import list_wellbeing

DB = os.path.expanduser("~/.local/share/ai-coach/coach.db")
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row

def days(a, b):
    d = date.fromisoformat(a)
    while d.isoformat() <= b:
        yield d; d += timedelta(days=1)

rows = list_recovery_days(conn, "2025-11-01", "2026-11-18")
extra = {r["date"]: dict(r) for r in conn.execute(
    "select date, json_extract(raw_json,'$.sleep.avgSkinTempDeviationC') skin, "
    "json_extract(raw_json,'$.sleep.dailySleepDTO.averageRespirationValue') resp from daily_metrics where date>='2026-10-01'")}
for r in rows:
    r.update({"skin": None, "resp": None}); r.update(extra.get(r["date"], {}))
by = {r["date"]: r for r in rows}

marks = list_wellbeing(conn, "2026-10-01", "2026-11-18")
bad = set()
for d in days("2026-10-27", "2026-11-17"):
    m = dv.main_wellbeing([x for x in marks if x["date"] == d.isoformat()])
    if m and (m["score"] <= 2 or dv.find_symptoms(m["texts"])): bad.add(d.isoformat())
first_bad = min(bad)
pre = {(date.fromisoformat(first_bad) - timedelta(days=k)).isoformat() for k in (1, 2, 3)}
print("плохих дней", len(bad), "; эпизодов подряд:", sum(1 for d in bad if (date.fromisoformat(d)-timedelta(days=1)).isoformat() not in bad))

def flags(a, b, k):
    il.SWC_K = k
    out = {}
    for d in days(a, b):
        f = il.day_flags(by.get(d.isoformat(), {}), il.corridor(rows, d, "rhr"), il.corridor(rows, d, "hrv"))
        out[d.isoformat()] = f
    return out

def streaked(on, n):
    return {d for d in on if all((date.fromisoformat(d) - timedelta(days=i)).isoformat() in on for i in range(n))}

A = ("2026-10-27", "2026-11-17"); B = ("2026-01-10", "2026-09-30")
print("правило | окно A: дней, в плохие, за 1-3 дня до первого плохого, прочие (ложные) | история B: дней из N с данными (%)")
for k in (0.5, 0.75, 1.0, 1.5):
    fa, fb = flags(*A, k), flags(*B, k)
    nb = sum(1 for f in fb.values() if f["out"] is not None)
    for name, pick in (("И", lambda f: f["out"]), ("ИЛИ", lambda f: f["rhr_high"] or f["hrv_low"]), ("HRV", lambda f: f["hrv_low"]), ("пульс", lambda f: f["rhr_high"])):
        for n in (1, 2):
            a_on = streaked({d for d, f in fa.items() if pick(f)}, n)
            b_on = streaked({d for d, f in fb.items() if pick(f)}, n)
            first = min((d for d in a_on if d >= min(pre)), default="-")
            lead = (date.fromisoformat(first_bad) - date.fromisoformat(first)).days if first != "-" else None
            print(f"K={k} {name} {n}д | {len(a_on)}, {len(a_on & bad)}, {len(a_on & pre)}, {len(a_on - bad - pre)}; первый сигнал за {lead} дн до первого плохого | {len(b_on)} из {nb} ({100*len(b_on)/nb:.0f}%)")
il.SWC_K = 0.5
# Кожа и дыхание (API, с 10-01): тот же коридор
for key in ("skin", "resp"):
    for k in (0.5, 1.0, 1.5):
        il.SWC_K = k; on = set(); nd = 0
        for d in days(*A):
            c = il.corridor(rows, d, key); v = by.get(d.isoformat(), {}).get(key)
            if c is None or v is None: continue
            nd += 1
            if v > round(c["mean7"] + c["swc"], 1 if key == "resp" else 2): on.add(d.isoformat())
        print(f"{key} K={k}: дней с коридором {nd}, выше {len(on)}, в плохие {len(on & bad)}, за 1-3 дня до {len(on & pre)}, прочие {len(on - bad - pre)}")
il.SWC_K = 0.5
# Сон: частота сигналов на истории
def sleep_rate(a, b, short, d7, d14):
    sl.SHORT_NIGHT_H, sl.DEBT_7_H, sl.DEBT_14_H = short, d7, d14
    n = sn = sd = 0
    for d in days(a, b):
        r = sl.sleep_report(conn, d.isoformat())
        if r["norm_h"] is None or r["last_night_h"] is None: continue
        n += 1; kinds = {s["kind"] for s in r["signals"]}
        sn += "short_night" in kinds; sd += "sleep_debt" in kinds
    return n, sn, sd
for short, d7, d14 in ((1.0, 3.0, 5.0), (0.75, 2.0, 4.0), (0.5, 2.0, 3.0), (1.0, 1.5, 3.0)):
    print(f"сон short={short} d7={d7} d14={d14}: окно A (ночей, short, debt) {sleep_rate(*A, short, d7, d14)}; история 2026-03-01..11-17 {sleep_rate('2026-03-01','2026-11-17', short, d7, d14)}")
