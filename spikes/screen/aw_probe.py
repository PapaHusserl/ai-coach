"""Спайк экранного времени, фаза А: что есть в ActivityWatch. Одноразовый код, не продакшен.

Запуск: uv run python spikes/screen/aw_probe.py
В stdout только счётчики и типы бакетов: без hostname, названий приложений и заголовков окон.
"""

from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import quote

from common import aw_get, save_json, say

DAYS = 7
MIN_AFK_HOURS = 2  # меньше данных — вердикт про чередование afk ложный, «рано судить»


def main() -> None:
    info = aw_get("/api/0/info")
    say(f"aw-server версия: {info.get('version')}")

    buckets = aw_get("/api/0/buckets/")
    save_json("aw_buckets.json", buckets)
    say(f"бакетов: {len(buckets)}")

    now = datetime.now().astimezone()
    start = (now - timedelta(days=DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    afk_total = Counter()  # общий, только для вердикта: status -> секунды
    has_afk = False

    for n, (bid, b) in enumerate(buckets.items(), 1):
        btype = b.get("type")
        events = aw_get(
            f"/api/0/buckets/{quote(bid, safe='')}/events",
            start=start.isoformat(),
            end=now.isoformat(),
            limit=-1,
        )
        per_day = Counter()
        for e in events:
            ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
            per_day[ts.astimezone().date()] += 1
        days = ", ".join(f"{d:%m-%d}={per_day[d]}" for d in sorted(per_day)) or "нет событий"
        say(f"бакет {n}: type={btype}, событий за {DAYS} дн: {len(events)} ({days})")

        if btype == "currentwindow":
            empty = sum(1 for e in events if not (e.get("data", {}).get("title") or "").strip())
            apps = {e["data"]["app"] for e in events if e.get("data", {}).get("app")}
            share = empty / len(events) * 100 if events else 0
            say(f"  пустых title: {empty} из {len(events)} ({share:.0f}%), различных app: {len(apps)}")
        elif btype == "afkstatus":
            has_afk = True
            b_total = Counter()  # status -> секунды, по этому бакету
            b_count = Counter()  # status -> интервалы
            for e in events:
                st = e.get("data", {}).get("status")
                b_total[st] += e.get("duration", 0)
                b_count[st] += 1
                afk_total[st] += e.get("duration", 0)
            for st in sorted(b_total, key=str):
                say(f"  status={st}: {b_total[st] / 3600:.1f} ч, интервалов: {b_count[st]}")

    if not has_afk:
        say("ВЕРДИКТ: afk не определяется — проверь Input Monitoring (afk-бакета нет)")
    elif not afk_total:
        say("ВЕРДИКТ: afk-бакет есть, но событий за 7 дней нет (норма в день 0)")
    elif sum(afk_total.values()) < MIN_AFK_HOURS * 3600:
        hours = sum(afk_total.values()) / 3600
        say(f"ВЕРДИКТ: рано судить — afk-данных {hours:.1f} ч, нужно от {MIN_AFK_HOURS} ч")
    elif afk_total.get("afk") and afk_total.get("not-afk"):
        say("ВЕРДИКТ: afk чередуется (есть и afk, и not-afk)")
    elif afk_total.get("afk"):
        say("ВЕРДИКТ: только afk, not-afk нет — странно, проверь watcher")
    else:
        say("ВЕРДИКТ: afk не определяется — проверь Input Monitoring (status всегда not-afk)")


main()
