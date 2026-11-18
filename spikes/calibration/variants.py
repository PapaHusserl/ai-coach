"""Разведка v2.9: варианты весов и порогов перегруза на окне (только чтение, счёт дней)."""
import os, sqlite3
from datetime import date, timedelta
from ai_coach.load import overload as ov, deviations as dv
from ai_coach.mcp_server import tools
conn = sqlite3.connect(f"file:{os.path.expanduser('~/.local/share/ai-coach/coach.db')}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
A, B = "2026-10-12", "2026-11-17"
tss = {r["date"]: r["tss"] for r in tools.load(conn, "2026-09-20", B)["rows"]}
alld = [(date.fromisoformat(A) + timedelta(days=i)).isoformat() for i in range(37)]
def streak3(flags): return sum(1 for i in range(2, len(flags)) if flags[i] and flags[i-1] and flags[i-2])
base = (ov.W_HOBBY, ov.W_GROOMING, ov.W_TODO)
print("W_HOBBY W_GROOMING W_TODO | порог: дней >= порога / дней total_streak")
for wh, wg, wt in ((0.5, 0.5, 0.2), (0.5, 0.2, 0.2), (0.5, 0.1, 0.2), (0.5, 0.0, 0.2), (0.25, 0.2, 0.2), (0.0, 0.2, 0.2), (0.25, 0.1, 0.2)):
    ov.W_HOBBY, ov.W_GROOMING, ov.W_TODO = wh, wg, wt
    ent = ov.day_entries(conn, "2026-10-10", B, tss)
    tot = [e["total"] for e in ent]; win = tot[2:]
    s = sorted(win); p80 = s[int(0.8 * len(s))]
    cells = []
    for th in (8, 10, 12):
        fl = [t >= th for t in tot]
        cells.append(f"{th}: {sum(fl[2:])}/{streak3(fl)}")
    print(wh, wg, wt, "|", "; ".join(cells), f"| дней выше 80-го перцентиля окна: {sum(t >= p80 for t in win)}")
ov.W_HOBBY, ov.W_GROOMING, ov.W_TODO = base
# weekend_work
for wmin in (1.0, 2.0, 4.0, 6.0):
    ov.WEEKEND_WORK_MIN = wmin; n = 0
    for d in alld:
        n += any(s["kind"] == "weekend_work" for s in ov.overload_report(conn, d, tss)["signals"])
    print(f"WEEKEND_WORK_MIN={wmin}: дней с сигналом {n} из 37")
ov.WEEKEND_WORK_MIN = 1.0
for rd in (10, 15, 20):
    ov.READINESS_DROP = rd
    ov.RECOVERY_SIGNS = (("readiness_score", "readiness", 1, rd), ("mood", "mood", 1, ov.MOOD_DROP), ("stress", "stress", -1, ov.STRESS_RISE))
    n = sum(any(s["kind"] == "recovery_drop" and "readiness" in s["value"] for s in ov.overload_report(conn, d, tss)["signals"]) for d in alld)
    print(f"READINESS_DROP={rd}: дней recovery_drop по readiness {n} из 37")
for bd in (1, 2):
    dv.BELOW_DROP = bd; c = {"wellbeing_below": 0, "mood_below": 0}
    for d in alld:
        for x in tools.day_deviations(conn, d, None):
            if x["kind"] in c: c[x["kind"]] += 1
    print(f"BELOW_DROP={bd}: {c} из 37")
for tg in (5, 8, 10):
    ov.TODO_GROWTH_MIN = tg
    print(f"TODO_GROWTH_MIN={tg}: дней {sum(any(s['kind']=='todo_growth' for s in ov.overload_report(conn, d, tss)['signals']) for d in alld)} из 37")
