"""Сторож личных значений (шаг Г2, только чтение): сверка отслеживаемых файлов с живой базой.

Запуск: uv run python spikes/privacy/scan.py   (через `make personal`)
Ищет вес (точное совпадение с weight_log и profile_log), пульс покоя и HRV (значение рядом с датой того же дня
или пара значений одного дня; в .py пара не проверяется). Единицы (мин, ч, ккал, %) после числа снимают вес.
Печатает `файл:строка (вид)`, значений не печатает. Диапазоны и агрегаты не видит.
Базы нет - «пропуск: базы нет», код 0. Совпадения есть - код 1.
"""
import re, sqlite3, subprocess, sys
from ai_coach.store.db import db_path
from ai_coach.store.garmin_data import list_recovery_days
from ai_coach.store.journal import list_weights

SKIP = ("uv.lock", "player/vendor/")
PULSE = re.compile(r"(?:пульс|ЧСС|RHR)[^\d\n]{0,12}(\d+)", re.IGNORECASE)
HRV = re.compile(r"(?:HRV|ВСР)[^\d\n]{0,12}(\d+)", re.IGNORECASE)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def weight_patterns(conn):
    values = {f"{r['weight_kg']:g}" for r in list_weights(conn, "0000-01-01", "9999-12-31")}
    values |= {r[0].rstrip("0").rstrip(".") for r in conn.execute("SELECT value FROM profile_log WHERE key = 'weight'")}
    forms = {v for x in values for v in (x, x.replace(".", ","))}
    return [re.compile(rf"(?<![\d.,]){re.escape(v)}(?!\d|[.,]\d|\s*(?:мин|ч|ккал)\b|\s*%)") for v in forms if "." in v or "," in v]


def day_hits(line, days, pair=True):
    pulse = {int(m) for m in PULSE.findall(line)}
    hrv = {int(m) for m in HRV.findall(line)}
    dates = set(DATE.findall(line))
    for day in days:
        has = {"rhr": day["rhr"] in pulse, "hrv": day["hrv"] in hrv}
        if (day["date"] in dates and (has["rhr"] or has["hrv"])) or (pair and has["rhr"] and has["hrv"]):
            return True
    return False


def main():
    path = db_path()
    if not path.exists():
        print("пропуск: базы нет")
        return 0
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    weights = weight_patterns(conn)
    days = [d for d in list_recovery_days(conn, "0000-01-01", "9999-12-31") if d["rhr"] and d["hrv"]]
    days = [{"date": d["date"], "rhr": round(d["rhr"]), "hrv": round(d["hrv"])} for d in days]
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], capture_output=True, text=True, check=True).stdout.splitlines()
    found = []
    for name in files:
        if name.endswith(SKIP) or name.startswith(SKIP):
            continue
        try:
            text = open(name, encoding="utf-8").read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if any(p.search(line) for p in weights):
                found.append(f"{name}:{number} (вес)")
            if day_hits(line, days, pair=not name.endswith(".py")):  # в коде пара round-чисел - сценарий теста
                found.append(f"{name}:{number} (пульс/HRV)")
    print("\n".join(found) if found else "совпадений нет")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
