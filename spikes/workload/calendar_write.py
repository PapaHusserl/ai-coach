"""Спайк v2.6: запись в календарь коуча через EventKit (создать/прочитать/удалить).

Запуск Владом в своём терминале (возможен промпт macOS на запись):
    uv run --with pyobjc-framework-EventKit python spikes/workload/calendar_write.py --calendar "<имя>"
    ... --calendar "<имя>" --keep          # не удалять, посмотреть в Calendar.app/iPhone
    ... --calendar "<имя>" --remove <eventIdentifier>   # позже: проверить id после синка и удалить
Трогает только события с заголовком "ai-coach spike" в указанном календаре.
"""

import argparse
import sys
import threading
import time
from datetime import datetime, timedelta

import EventKit as EK
from Foundation import NSDate, NSTimeZone

from common import say

TITLE = "ai-coach spike"
NOTE = "заметка спайка v2.6"
ALARM_SEC = -600


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


def ns_date(dt: datetime):
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def ts(nsdate) -> float:
    return float(nsdate.timeIntervalSince1970())


def find_calendar(store, name: str):
    found = [c for c in store.calendarsForEntityType_(EK.EKEntityTypeEvent)
             if str(c.title()).strip() == name.strip()]
    if len(found) != 1:
        say(f"ОШИБКА: календарей с таким названием найдено {len(found)}, нужен ровно один")
        sys.exit(1)
    return found[0]


def is_ours(event, cal) -> bool:
    """Защита: трогаем только событие с нашим заголовком в календаре коуча."""
    if event is None:
        return False
    same_cal = str(event.calendar().calendarIdentifier()) == str(cal.calendarIdentifier())
    return same_cal and str(event.title()) == TITLE


def describe(res) -> str:
    kind = type(res).__name__
    if isinstance(res, tuple):
        parts = [type(x).__name__ + "=" + ("None" if x is None else repr(x)[:60]) for x in res]
        return f"{kind} длиной {len(res)}: " + ", ".join(parts)
    return f"{kind}: {repr(res)[:60]}"


def save(store, event, span):
    res = store.saveEvent_span_commit_error_(event, span, True, None)
    say(f"saveEvent вернул: {describe(res)}")
    ok, err = res if isinstance(res, tuple) else (res, None)
    if not ok:
        say(f"ОШИБКА сохранения: {str(err)[:120]}")
        sys.exit(1)


def remove(store, event, cal, span) -> bool:
    if not is_ours(event, cal):
        say("ОТКАЗ: событие не наше (заголовок или календарь не совпали), не удаляю")
        return False
    res = store.removeEvent_span_commit_error_(event, span, True, None)
    say(f"removeEvent вернул: {describe(res)}")
    ok, err = res if isinstance(res, tuple) else (res, None)
    if not ok:
        say(f"ОШИБКА удаления: {str(err)[:120]}")
    return bool(ok)


def make_event(store, cal, start: datetime, note: str):
    ev = EK.EKEvent.eventWithEventStore_(store)
    ev.setCalendar_(cal)
    ev.setTitle_(TITLE)
    ev.setNotes_(note)
    ev.setStartDate_(ns_date(start))
    ev.setEndDate_(ns_date(start + timedelta(minutes=30)))
    ev.setTimeZone_(NSTimeZone.localTimeZone())
    ev.addAlarm_(EK.EKAlarm.alarmWithRelativeOffset_(ALARM_SEC))
    return ev


def ours_in_window(store, cal, start: datetime, end: datetime, note: str) -> list:
    pred = store.predicateForEventsWithStartDate_endDate_calendars_(ns_date(start), ns_date(end), [cal])
    return [e for e in store.eventsMatchingPredicate_(pred)
            if is_ours(e, cal) and str(e.notes() or "") == note]


def step_single(store, cal, keep: bool) -> None:
    say("шаг 3: создание одиночного события на завтра 10:00")
    start = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    ev = make_event(store, cal, start, NOTE)
    save(store, ev, EK.EKSpanThisEvent)
    eid = str(ev.eventIdentifier())
    say(f"eventIdentifier: {eid}")
    say(f"calendarItemExternalIdentifier: {ev.calendarItemExternalIdentifier()}")

    say("шаг 4: чтение назад по eventIdentifier и сверка полей")
    back = store.eventWithIdentifier_(eid)
    if back is None:
        say("ОШИБКА: событие по eventIdentifier не найдено")
        sys.exit(1)
    alarms = list(back.alarms() or [])
    tz = back.timeZone()
    checks = {
        "заголовок": str(back.title()) == TITLE,
        "календарь": is_ours(back, cal),
        "заметка": str(back.notes() or "") == NOTE,
        "начало": ts(back.startDate()) == start.timestamp(),
        "конец": ts(back.endDate()) == (start + timedelta(minutes=30)).timestamp(),
        "таймзона": tz is not None and str(tz.name()) == str(NSTimeZone.localTimeZone().name()),
        "будильник -10 мин": len(alarms) == 1 and float(alarms[0].relativeOffset()) == ALARM_SEC,
        "eventIdentifier тот же": str(back.eventIdentifier()) == eid,
    }
    for name, ok in checks.items():
        say(f"сверка {name}: {'ок' if ok else 'РАСХОДИТСЯ'}")
    say(f"таймзона события: {tz.name() if tz else None}")

    if keep:
        say("шаг 5: --keep, событие оставлено. Посмотри в Calendar.app/iPhone (замерь задержку), "
            f"потом: --calendar ... --remove {eid}")
        return
    say("шаг 6: удаление")
    if remove(store, back, cal, EK.EKSpanThisEvent):
        gone = store.eventWithIdentifier_(eid) is None
        say(f"после удаления по eventIdentifier найдено: {'нет (ок)' if gone else 'ДА (не исчезло)'}")


def step_recurring(store, cal) -> None:
    say("шаг 7: ежедневное повторяющееся на 3 дня, создание")
    note = f"повторяющееся спайк v2.6 {int(time.time())}"
    start = (datetime.now() + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
    ev = make_event(store, cal, start, note)
    rule = EK.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_(
        EK.EKRecurrenceFrequencyDaily, 1, EK.EKRecurrenceEnd.recurrenceEndWithOccurrenceCount_(3))
    ev.addRecurrenceRule_(rule)
    save(store, ev, EK.EKSpanFutureEvents)
    eid = str(ev.eventIdentifier())
    say(f"eventIdentifier повторяющегося: {eid}")
    win_start, win_end = start - timedelta(hours=2), start + timedelta(days=5)
    found = ours_in_window(store, cal, win_start, win_end, note)
    say(f"вхождений после создания: {len(found)} (ожидаем 3)")
    say(f"eventIdentifier вхождений: {len({str(e.eventIdentifier()) for e in found})} уникальных")

    master = store.eventWithIdentifier_(eid)
    say("удаление с EKSpanFutureEvents")
    remove(store, master, cal, EK.EKSpanFutureEvents)
    left = ours_in_window(store, cal, win_start, win_end, note)
    say(f"вхождений после удаления: {len(left)} (ожидаем 0)")


def step_remove_by_id(store, cal, eid: str) -> None:
    ev = store.eventWithIdentifier_(eid)
    if ev is None:
        say("по этому eventIdentifier события нет (id изменился после синка или уже удалено)")
        return
    say("по eventIdentifier событие найдено (id пережил синк)")
    if remove(store, ev, cal, EK.EKSpanFutureEvents):
        gone = store.eventWithIdentifier_(eid) is None
        say(f"после удаления найдено: {'нет (ок)' if gone else 'ДА (не исчезло)'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calendar", required=True)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--remove", metavar="EVENT_IDENTIFIER")
    args = ap.parse_args()

    store = EK.EKEventStore.alloc().init()
    say(f"шаг 1: authorizationStatus до запроса: {auth_status()} "
        "(0 не спрашивали, 2 отказ, 3 полный, 4 только запись)")
    granted, err = request_access(store)
    say(f"доступ: granted={granted} error={'да' if err else 'нет'}")
    say(f"authorizationStatus после запроса: {auth_status()}")
    if err:
        say(f"ошибка (первые 80 символов): {err[:80]}")
    if not granted:
        return

    cal = find_calendar(store, args.calendar)
    say(f"шаг 2: календарь найден, allowsContentModifications={bool(cal.allowsContentModifications())}")
    if not cal.allowsContentModifications():
        say("ОШИБКА: в календарь нельзя писать")
        sys.exit(1)

    if args.remove:
        step_remove_by_id(store, cal, args.remove)
        return
    step_single(store, cal, args.keep)
    step_recurring(store, cal)
    say("готово")


if __name__ == "__main__":
    main()
