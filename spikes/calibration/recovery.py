"""Разведка Н6 (только чтение): вечер дня D против ночи D+1. Печать - счёт дней и ранговые связи.

Запуск: uv run python spikes/calibration/recovery.py 2026-10-12 2026-11-23
Значения связей и разниц - только в терминал, в документы и репо не переносить (репо публичное).
"""
import os, sqlite3, sys
from datetime import date, timedelta
from statistics import mean, median
from ai_coach.load import overload as ov
from ai_coach.load.episode import sick_days
from ai_coach.load.illness import illness_report, form_texts
from ai_coach.mcp_server import tools
from ai_coach.store.garmin_data import list_daily_metrics, list_recovery_days
from ai_coach.store.journal import list_wellbeing
from ai_coach.store.workload import list_counters

DB = os.path.expanduser("~/.local/share/ai-coach/coach.db")
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
A, B = sys.argv[1], sys.argv[2]
nxt = lambda d, k=1: (date.fromisoformat(d) + timedelta(days=k)).isoformat()
tss = {r["date"]: r["tss"] for r in tools.load(conn, nxt(A, -22), B)["rows"]}
ent = ov.day_entries(conn, A, B, tss)
met = {m["date"]: m for m in list_daily_metrics(conn, A, nxt(B, 2))}
rec = {r["date"]: r for r in list_recovery_days(conn, A, nxt(B, 2))}
cl = {k: {c["date"]: c["value"] for c in list_counters(conn, A, B, k)} for k in ("claude_prompts_evening", "claude_prompts")}
scr = {c["date"]: c["value"] for c in list_counters(conn, A, B, "screen_evening_hours")}


def rank(xs):
    s = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and xs[s[j + 1]] == xs[s[i]]: j += 1
        for k in range(i, j + 1): r[s[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def rho(x, y):
    p = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(p) < 8: return None, len(p)
    rx, ry = rank([q[0] for q in p]), rank([q[1] for q in p]); mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry)); den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return (round(num / den, 2) if den else None), len(p)


# болезнь и коридор по дням: лестница illness_report (фаза и сигналы)
ill, out, streak2 = {}, {}, {}
for e in ent + [{"date": nxt(B)}]:
    d = e["date"]
    if d not in rec: continue
    rep = illness_report(conn, d, tss)
    kinds = {s["kind"] for s in rep["signals"]}
    ill[d] = bool(kinds & {"illness_risk", "illness_rest", "illness_return", "illness_light"}) or bool((rep.get("episode") or {}).get("phase"))
    out[d] = rep["out_today"]; streak2[d] = rep["streak"] >= 2
print("дней окна", len(ent), "; дней с эпизодом/сигналом болезни", sum(ill.values()), "; вне коридора", sum(1 for v in out.values() if v), "; коридора нет", sum(1 for v in out.values() if v is None), "; вне коридора 2+ подряд", sum(streak2.values()), "; из них в болезни", sum(1 for d in streak2 if streak2[d] and ill[d]))

# другое правило болезни: симптом в тексте
marks = list_wellbeing(conn, A, nxt(B)); texts = form_texts(conn, A, nxt(B))
for m in marks:
    if m["text"]: texts.setdefault(m["date"], []).append(m["text"])
sd = sick_days(texts, {m["date"] for m in marks})
symp = {d for d, v in sd.items() if v["symptoms"] or v["fever"] is not None}
phase = {d for d, v in ill.items() if v}
print("дней с симптомом в тексте:", len(symp), "; дней фазы/сигнала:", len(phase), "; симптом вне фазы:", len(symp - phase), "; фаза без симптома:", len(phase - symp))
for name, sick in (("фаза", phase), ("симптом", symp)):
    wl = [e for e in ent if e["date"] not in sick and nxt(e["date"]) not in sick]
    print(name, "пар без болезни:", len(wl), "; рабочих вечеров:", sum(ov.evening_hours(e) >= ov.EVENING_WORK_MIN for e in wl), "; тяжёлых дней total>=", ov.TOTAL_HIGH, ":", sum(e["total"] >= ov.TOTAL_HIGH for e in wl), "; ночей вне коридора после них:", sum(bool(out.get(nxt(e["date"]))) for e in wl))
print("тяжёлых дней всего:", sum(e["total"] >= ov.TOTAL_HIGH for e in ent), "; вне коридора вне фазы:", sum(1 for d, v in out.items() if v and d not in phase), "; вне коридора без симптома:", sum(1 for d, v in out.items() if v and d not in symp))

fac = {
    "work_evening (правило сигнала)": [ov.evening_hours(e) if e.get("screen_work_evening_hours") is not None else None for e in ent],
    "screen_evening весь": [scr.get(e["date"]) for e in ent],
    "claude_evening": [cl["claude_prompts_evening"].get(e["date"]) for e in ent],
    "claude_day": [cl["claude_prompts"].get(e["date"]) for e in ent],
    "work_h": [ov.hours(e, "work_hours") for e in ent],
    "total": [e["total"] for e in ent],
    "tss": [e.get("tss") or 0 for e in ent],
}


def resp(k):
    return {
        "hrv": [(rec.get(nxt(e["date"], k)) or {}).get("hrv") for e in ent],
        "rhr": [(rec.get(nxt(e["date"], k)) or {}).get("rhr") for e in ent],
        "sleep_s": [(met.get(nxt(e["date"], k)) or {}).get("sleep_seconds") or None for e in ent],
        "sleep_score": [(met.get(nxt(e["date"], k)) or {}).get("sleep_score") for e in ent],
        "readiness": [(met.get(nxt(e["date"], k)) or {}).get("readiness_score") for e in ent],
    }


well = [not ill.get(nxt(e["date"]), False) and not ill.get(e["date"], False) for e in ent]
print("пар вечер-ночь без болезни:", sum(well))
for k in (1, 2):
    r = resp(k)
    print(f"--- лаг {k}")
    for f, xs in fac.items():
        print(f, {o: rho(xs, ys) for o, ys in r.items()}, "| без болезни:", {o: rho([x if w else None for x, w in zip(xs, well)], ys) for o, ys in r.items()})
we = fac["work_evening (правило сигнала)"]; ce = fac["claude_evening"]
print("вечеров с данными экрана:", sum(w is not None for w in we), "; рабочих (>=", ov.EVENING_WORK_MIN, "ч):", sum(1 for w in we if w is not None and w >= ov.EVENING_WORK_MIN), "; без болезни рабочих:", sum(1 for w, g in zip(we, well) if g and w is not None and w >= ov.EVENING_WORK_MIN), "; без болезни спокойных:", sum(1 for w, g in zip(we, well) if g and w is not None and w < ov.EVENING_WORK_MIN))
print("вечеров с claude-счётчиком:", sum(c is not None for c in ce), "; с репликами вечером > 0:", sum(1 for c in ce if c), "; = 0:", sum(1 for c in ce if c == 0))
cm = median([c for c in ce if c is not None])
print("claude вечер выше медианы, без болезни:", sum(1 for c, g in zip(ce, well) if g and c is not None and c > cm), "; не выше:", sum(1 for c, g in zip(ce, well) if g and c is not None and c <= cm))
# разница медиан отклика: рабочий вечер против спокойного, без болезни
r1 = resp(1)


def split(xs, th, key):
    hi = [y for x, y, g in zip(xs, r1[key], well) if g and x is not None and y is not None and x >= th]
    lo = [y for x, y, g in zip(xs, r1[key], well) if g and x is not None and y is not None and x < th]
    return len(hi), len(lo), (round(median(hi) - median(lo), 1) if hi and lo else None)


for key in ("hrv", "rhr", "sleep_s", "sleep_score"):
    print("рабочий вечер vs спокойный,", key, split(we, ov.EVENING_WORK_MIN, key), "; claude вечер > медианы:", split(ce, cm + 0.001, key))
print("серий рабочих вечеров 3 подряд (evening_streak), дней:", sum(1 for i in range(2, len(we)) if all((we[j] or 0) >= ov.EVENING_WORK_MIN for j in (i, i - 1, i - 2))))
