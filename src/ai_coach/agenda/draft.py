"""Проверка черновика события тренера: validate_draft и его пределы (KINDS, SURVEYS, PAST_DAYS…)."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from ai_coach.store.agenda import active_repeats
from ai_coach.store.plans import get_planned_workout
from ai_coach.store.practices import get_practice
from ai_coach.workload.config import CATEGORIES

KINDS = ("training", "practice", "rest", "sleep", "checkin", "task", "focus", "meal")
REST_KINDS = ("rest", "sleep")
SURVEYS = ("evening", "feel", "focus", "none", "who5")
REPEATS = ("daily", "weekly", "biweekly")
PAST_DAYS = 30
AHEAD_DAYS = 14
MAX_HOURS = 24
MAX_ALARM_MIN = 1440


class AgendaError(Exception):
    """Событие нельзя так создавать или менять. Текст - для консоли и MCP."""


def parse_moment(value: Any, name: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise AgendaError(f"{name}: нужно YYYY-MM-DDTHH:MM, получено: {value!r}") from None
    if moment.tzinfo is not None:
        raise AgendaError(f"{name}: время местное, без часового пояса.")
    return moment


def _category(kind: str, given: str | None) -> str | None:
    """Категория для нагрузки: у отдыха и сна по умолчанию rest; у задачи обязательна;
    у тренировки, практики и чек-ина нет."""
    if given is not None and given not in CATEGORIES:
        raise AgendaError(f"category должна быть из {list(CATEGORIES)}, получено: {given!r}")
    if kind in REST_KINDS:
        return given or "rest"
    if kind == "task":
        if given is None:
            raise AgendaError("У задачи нужна категория: work, hobby или personal.")
        return given
    if given is not None:
        raise AgendaError(f"category только у task, rest и sleep, а kind={kind}.")
    return None


def _survey(kind: str, given: str | None) -> str | None:
    """Опросник чек-ина (имя из SURVEYS); у остальных видов не задаётся. Без него - None."""
    if given is None:
        return None
    if kind != "checkin":
        raise AgendaError(f"survey только у checkin, а kind={kind}.")
    if given not in SURVEYS:
        raise AgendaError(f"survey должен быть из {list(SURVEYS)}, получено: {given!r}")
    return given


def _links(conn: sqlite3.Connection, workout_id: Any, practice_id: Any) -> None:
    if workout_id is not None:
        workout = get_planned_workout(conn, workout_id)
        if workout is None or workout["status"] == "cancelled":
            raise AgendaError(f"Тренировки {workout_id} нет или она отменена.")
    if practice_id is not None and get_practice(conn, practice_id) is None:
        raise AgendaError(f"Практики {practice_id} нет.")


def _clash(repeat: str, start: datetime, row: dict[str, Any]) -> bool:
    """Повтор row занимает то же время суток и пересекается по дням: daily - с любым, weekly и
    biweekly - с daily и с тем же днём недели."""
    if row["start_at"][11:16] != start.isoformat(timespec="seconds")[11:16]:
        return False
    if repeat == "daily" or row["repeat"] == "daily":
        return True
    return datetime.fromisoformat(row["start_at"]).weekday() == start.weekday()


def validate_draft(
    conn: sqlite3.Connection, values: dict[str, Any], today: date | None = None
) -> dict[str, Any]:
    """Проверенные значения черновика для add_event (без status, created_at). values: kind, title,
    start_at, end_at (местное время ISO); не обязательно all_day, note, category, alarm_min,
    repeat, survey (только у checkin), workout_id, practice_id. Начало раньше конца, событие не
    длиннее MAX_HOURS, день начала от PAST_DAYS назад до AHEAD_DAYS вперёд; repeat (daily,
    weekly, biweekly) только у checkin и не два активных на одно время суток с пересечением по
    дням; тренировка и практика живы; категория по умолчанию только у rest и sleep (rest)."""
    today = today or date.today()
    kind = values["kind"]
    if kind not in KINDS:
        raise AgendaError(f"kind должен быть из {list(KINDS)}, получено: {kind!r}")
    title = (values.get("title") or "").strip()
    if not title:
        raise AgendaError("Название события пустое.")
    start = parse_moment(values["start_at"], "start_at")
    end = parse_moment(values["end_at"], "end_at")
    if end <= start:
        raise AgendaError("Начало события должно быть раньше конца.")
    if end - start > timedelta(hours=MAX_HOURS):
        raise AgendaError(f"Событие не длиннее {MAX_HOURS} часов.")
    if not today - timedelta(days=PAST_DAYS) <= start.date() <= today + timedelta(days=AHEAD_DAYS):
        raise AgendaError(f"День начала от {PAST_DAYS} дней назад до {AHEAD_DAYS} дней вперёд.")
    alarm = values.get("alarm_min")
    if alarm is not None and not 0 <= alarm <= MAX_ALARM_MIN:
        raise AgendaError(f"alarm_min от 0 до {MAX_ALARM_MIN} минут, получено: {alarm}")
    repeat = values.get("repeat")
    if repeat is not None:
        if repeat not in REPEATS or kind != "checkin":
            raise AgendaError(f"repeat только {list(REPEATS)} и только у checkin.")
        clock = start.isoformat(timespec="seconds")[11:16]
        if any(_clash(repeat, start, row) for row in active_repeats(conn)):
            raise AgendaError(
                f"Повторяющийся чек-ин на {clock} уже есть (черновик или в календаре)."
            )
    _links(conn, values.get("workout_id"), values.get("practice_id"))
    note = (values.get("note") or "").strip() or None
    return {
        "kind": kind,
        "title": title,
        "date": start.date().isoformat(),
        "start_at": start.isoformat(timespec="seconds"),
        "end_at": end.isoformat(timespec="seconds"),
        "all_day": int(bool(values.get("all_day"))),
        "note": note,
        "category": _category(kind, values.get("category")),
        "survey": _survey(kind, values.get("survey")),
        "alarm_min": alarm,
        "repeat": repeat,
        "workout_id": values.get("workout_id"),
        "practice_id": values.get("practice_id"),
    }
