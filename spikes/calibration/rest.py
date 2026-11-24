"""Разведка Н7 (только чтение): ответы об отдыхе, выходные по порогам работы, дни сигнала по окнам.

Запуск: uv run python spikes/calibration/rest.py 2026-10-12 2026-11-23
Печать - только счёт дней; значения часов в терминал не выводятся (репо публичное).
"""
import os, sqlite3, sys
from collections import Counter
from datetime import date, timedelta
from ai_coach.load import overload as ov

DB = os.path.expanduser("~/.local/share/ai-coach/coach.db")
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
A, B = sys.argv[1], sys.argv[2]
ent = ov.day_entries(conn, A, B, {})
print("дней", len(ent), "; сб/вс", sum(d["weekend"] for d in ent))

# ручной отдых
man = [d for d in ent if d["manual_rest_hours"] is not None]
print("ручной отдых: дней", len(man), "; больше нуля", sum(d["manual_rest_hours"] > 0 for d in man),
      "; ноль", sum(d["manual_rest_hours"] == 0 for d in man))
ci = {r[0] for r in conn.execute(
    "select distinct date from wellbeing_log where date between ? and ? and (mood is not null or stress is not null)",
    (A, B))}
print("дней с вечерним чек-ином", len(ci), "; ручные часы работы", sum(d["manual_work_hours"] is not None for d in ent),
      "; работа есть, отдыха нет", sum(d["manual_work_hours"] is not None and d["manual_rest_hours"] is None for d in ent))
wk, wkn = Counter(), Counter()
for d in ent:
    m = date.fromisoformat(d["date"]); mo = (m - timedelta(days=m.weekday())).isoformat()
    wkn[mo] += 1; wk[mo] += d["manual_rest_hours"] is not None
print("по неделям дней с ответом об отдыхе", [f"{wk[k]}/{wkn[k]}" for k in sorted(wkn)],
      "; недель с 4+", sum(v >= 4 for v in wk.values()), "; с 5+", sum(v >= 5 for v in wk.values()))
cal = [d for d in ent if d["rest_hours"] > 0]
print("календарь rest: дней", len(cal), "; не длиннее получаса", sum(d["rest_hours"] <= 0.5 for d in cal))

# серия «без отдыха»: None - «нет данных». Два счёта: только ручной ответ (Р2) и ручной ответ или календарь rest
man_st = [d["manual_rest_hours"] > 0 if d["manual_rest_hours"] is not None else None for d in ent]
cal_st = [s if s is not None else (True if d["rest_hours"] > 0 else None) for s, d in zip(man_st, ent)]
for origin, st in (("только ручные", man_st), ("ручные или календарь", cal_st)):
    for label, unk_breaks in (("без ответа = без отдыха", False), ("без ответа рвёт серию", True)):
        cur, fires = 0, Counter()
        for s in st:
            cur = 0 if s or (s is None and unk_breaks) else cur + 1
            for n in (3, 5, 7):
                fires[n] += cur >= n
        print("серия,", origin, ";", label, "; дней серий от N:", dict(fires))
print("ручной отдых меньше 1 ч", sum(d["manual_rest_hours"] < 1 for d in man),
      "; меньше 2 ч", sum(d["manual_rest_hours"] < 2 for d in man))


# выходной по порогу работы (лестница hours)
def work(d):
    return ov.hours(d, "work_hours")


src = Counter("ручные" if d["manual_work_hours"] is not None else "экран" if d["screen_work_hours"] is not None
              else "календарь" for d in ent)
print("источник работы, дней", dict(src))


def report(name, flags, only_weekend=False):
    f = [fl and (d["weekend"] or not only_weekend) for fl, d in zip(flags, ent)]
    longest = cur = 0
    fire = {7: 0, 10: 0, 14: 0}; ep = {7: 0, 10: 0}; prev = {7: False, 10: False}
    for i, x in enumerate(f):
        cur = 0 if x else cur + 1
        longest = max(longest, cur)
        for w in fire:
            a = i >= w - 1 and not any(f[i - w + 1:i + 1])
            fire[w] += a
            if w in ep:
                ep[w] += a and not prev[w]; prev[w] = a
    print(f"{name:34s} выходных {sum(f):2d}; длиннейший отрезок {longest:2d}; сигнал окно 7: {fire[7]:2d} "
          f"({ep[7]} отр.), окно 10: {fire[10]:2d} ({ep[10]}), окно 14: {fire[14]}")


for t in (0, 0.5, 1):
    report(f"работа <= порога {t}", [work(d) <= t for d in ent])
    report(f"работа <= порога {t}, только сб/вс", [work(d) <= t for d in ent], True)
print("будни, работа <= 1 ч:", sum(work(d) <= 1 for d in ent if not d["weekend"]))

# Claude и все источники сразу
for name, sel in (("все дни", ent), ("сб/вс", [d for d in ent if d["weekend"]])):
    print("Claude без реплик,", name, sum((d["claude_prompts"] or 0) == 0 for d in sel))
report("работа <= 0.5 и без Claude", [work(d) <= 0.5 and (d["claude_prompts"] or 0) == 0 for d in ent])
report("все источники <= 0.5", [all(v is None or v <= 0.5 for v in (d["manual_work_hours"], d["screen_work_hours"],
                                                                      d["work_hours"])) for d in ent])
both = [d for d in ent if d["manual_work_hours"] is not None and d["screen_work_hours"] is not None]
print("ручные и экран вместе", len(both), "; ручные 0, экран > 0.5", sum(
    d["manual_work_hours"] == 0 and d["screen_work_hours"] > 0.5 for d in both))
print("сб/вс с работой от 2 ч", sum(work(d) >= 2 for d in ent if d["weekend"]),
      "; дней без ручных часов и без экрана", sum(
          d["manual_work_hours"] is None and d["screen_work_hours"] is None for d in ent))
