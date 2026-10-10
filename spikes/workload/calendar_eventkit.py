"""Спайк: чтение календаря через EventKit (только чтение, без save/remove).

Запуск Владом в своём терминале (будет промпт macOS):
    uv run --with pyobjc-framework-EventKit python spikes/workload/calendar_eventkit.py
Сырьё - в spikes/out/calendar_raw.json, в stdout - обезличенная сводка.
"""

import threading
from collections import Counter
from datetime import datetime, timedelta

import EventKit as EK
from Foundation import NSDate

from common import save_json, say

DAYS_BACK = 30
DAYS_AHEAD = 14

STATUS = {0: "none", 1: "confirmed", 2: "tentative", 3: "canceled"}
AVAIL = {-1: "notSupported", 0: "busy", 1: "free", 2: "tentative", 3: "unavailable"}
PART = {0: "unknown", 1: "pending", 2: "accepted", 3: "declined", 4: "tentative",
        5: "delegated", 6: "completed", 7: "inProcess"}
CAL_TYPE = {0: "local", 1: "calDAV", 2: "exchange", 3: "subscription", 4: "birthday"}


def py_dt(nsdate):
    return None if nsdate is None else datetime.fromtimestamp(nsdate.timeIntervalSince1970()).isoformat()


def auth_status() -> int:
    return int(EK.EKEventStore.authorizationStatusForEntityType_(EK.EKEntityTypeEvent))


def request_access(store) -> tuple[bool, str]:
    done = threading.Event()
    box = {}

    def handler(granted, error):
        box["granted"] = bool(granted)
        box["error"] = None if error is None else str(error)
        done.set()

    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(handler)
    else:
        store.requestAccessToEntityType_completion_(EK.EKEntityTypeEvent, handler)
    if not done.wait(120):
        return False, "timeout"
    return box["granted"], box["error"] or ""


def my_participation(event) -> str:
    for a in event.attendees() or []:
        if a.isCurrentUser():
            return PART.get(int(a.participantStatus()), "?")
    return "no_attendee_me"


def main() -> None:
    store = EK.EKEventStore.alloc().init()
    say(f"authorizationStatus до запроса: {auth_status()} (0 не спрашивали, 2 отказ, 3 полный, 4 только запись)")
    granted, err = request_access(store)
    say(f"доступ: granted={granted} error={'да' if err else 'нет'}")
    say(f"authorizationStatus после запроса: {auth_status()}")
    if err:
        say(f"ошибка (первые 80 символов): {err[:80]}")
    if not granted:
        return

    cals = list(store.calendarsForEntityType_(EK.EKEntityTypeEvent))
    cal_idx = {str(c.calendarIdentifier()): i for i, c in enumerate(cals, 1)}
    cal_info = []
    for i, c in enumerate(cals, 1):
        src = c.source()
        cal_info.append({
            "n": i,
            "id": str(c.calendarIdentifier()),
            "title": str(c.title()),
            "type": CAL_TYPE.get(int(c.type()), "?"),
            "source_title": str(src.title()) if src else None,
            "allowsModify": bool(c.allowsContentModifications()),
        })
    say(f"календарей: {len(cals)}; по типам: {dict(Counter(c['type'] for c in cal_info))}")

    now = datetime.now()
    start = NSDate.dateWithTimeIntervalSince1970_((now - timedelta(days=DAYS_BACK)).timestamp())
    end = NSDate.dateWithTimeIntervalSince1970_((now + timedelta(days=DAYS_AHEAD)).timestamp())
    pred = store.predicateForEventsWithStartDate_endDate_calendars_(start, end, cals)
    events = list(store.eventsMatchingPredicate_(pred))

    rows = []
    for e in events:
        org = e.organizer()
        tz = e.timeZone()
        rows.append({
            "eventIdentifier": e.eventIdentifier(),
            "calendarItemIdentifier": e.calendarItemIdentifier(),
            "calendar_n": cal_idx.get(str(e.calendar().calendarIdentifier())),
            "title": e.title(),
            "start": py_dt(e.startDate()),
            "end": py_dt(e.endDate()),
            "isAllDay": bool(e.isAllDay()),
            "status": STATUS.get(int(e.status()), "?"),
            "availability": AVAIL.get(int(e.availability()), "?"),
            "hasRecurrenceRules": bool(e.hasRecurrenceRules()),
            "isDetached": bool(e.isDetached()),
            "occurrenceDate": py_dt(e.occurrenceDate()),
            "my_participation": my_participation(e),
            "organizer_is_me": None if org is None else bool(org.isCurrentUser()),
            "has_organizer": org is not None,
            "attendees_count": len(e.attendees() or []),
            "timeZone": None if tz is None else str(tz.name()),
        })
    save_json("calendar_raw.json", {"calendars": cal_info, "events": rows})

    say(f"событий в окне -{DAYS_BACK}..+{DAYS_AHEAD} дней: {len(rows)}")
    for key in ("isAllDay", "status", "availability", "hasRecurrenceRules", "isDetached",
                "my_participation", "organizer_is_me", "has_organizer"):
        say(f"{key}: {dict(Counter(str(r[key]) for r in rows))}")
    say(f"timeZone задан: {sum(1 for r in rows if r['timeZone'])} из {len(rows)}")
    say(f"уникальных eventIdentifier: {len({r['eventIdentifier'] for r in rows})} из {len(rows)}")
    say(f"уникальных calendarItemIdentifier: {len({r['calendarItemIdentifier'] for r in rows})} из {len(rows)}")
    say("событий по календарям: " + ", ".join(
        f"календарь #{n}: {c}" for n, c in sorted(Counter(r["calendar_n"] for r in rows).items())))
    per_day = Counter(r["start"][:10] for r in rows if r["start"])
    say(f"дней с событиями: {len(per_day)}; максимум за день: {max(per_day.values(), default=0)}")
    evening = sum(1 for r in rows if not r["isAllDay"] and r["end"][11:16] > "18:30")
    say(f"не-all-day событий, заканчивающихся после 18:30 (по времени конца): {evening}")
    say("сырьё: spikes/out/calendar_raw.json (разметку календарей по категориям - вручную)")


if __name__ == "__main__":
    main()
