"""Разведка v2.9, Р9: что изменит повторное чтение экрана за окно (coach screen --days N). Только чтение
AW и базы; печать - счёт дней, где счётчик в базе отличается от прочитанного сейчас."""
import os, sqlite3
from collections import Counter
from datetime import date
from ai_coach.workload.config import load_config
from ai_coach.workload.screen import AwReader, read_screen

cfg = load_config().screen
rows, notes = read_screen(AwReader(cfg), cfg, date(2026, 10, 12), date(2026, 11, 17))
conn = sqlite3.connect(f"file:{os.path.expanduser('~/.local/share/ai-coach/coach.db')}?mode=ro", uri=True)
have = {(d, k): v for d, k, v in conn.execute("select date, kind, value from day_counters where source='screen' and date between '2026-10-12' and '2026-11-17'")}
diff, new, same = Counter(), Counter(), Counter()
for r in rows:
    key = (r["date"], r["kind"])
    if key not in have: new[r["kind"]] += 1
    elif abs(have[key] - r["value"]) > 0.01: diff[r["kind"]] += 1
    else: same[r["kind"]] += 1
print("дней прочитано:", len({r["date"] for r in rows}), "; замечаний:", len(notes))
print("совпало:", dict(same)); print("отличается:", dict(diff)); print("нет в базе:", dict(new))
big = sum(1 for r in rows if r["kind"] == "screen_work_hours" and (r["date"], r["kind"]) in have and abs(have[(r["date"], r["kind"])] - r["value"]) >= 0.5)
print("дней, где screen_work_hours отличается на 0,5 ч и больше:", big)
