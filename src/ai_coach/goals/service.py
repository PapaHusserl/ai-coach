"""Цели и фазы. Любое изменение цели пишется событием в goal_events."""

import json
import sqlite3
from datetime import datetime
from typing import Any

from ai_coach.store.db import fetch_all
from ai_coach.store.goals import (
    add_goal,
    add_goal_event,
    add_phase,
    add_phase_event,
    add_phase_goal,
    delete_phase_goals,
    get_goal,
    get_phase,
    list_goal_events,
    list_goals,
    list_phase_events,
    list_phase_goal_ids,
    list_phases,
)
from ai_coach.store.goals import update_goal as update_goal_row
from ai_coach.store.goals import update_phase as update_phase_row

STATUSES = ("active", "done", "cancelled")
FIELDS = ("title", "kind", "priority", "target", "target_date", "status")


__all__ = [
    "accept_phase",
    "create_goal",
    "get_goal",
    "get_phase",
    "goal_history",
    "goals_on",
    "list_goals",
    "list_phases",
    "phases_on",
    "propose_phase",
    "reject_phase",
    "update_goal",
    "update_phase",
]


def _now(now: str | None) -> str:
    """Время события: переданная ISO-строка (проверяется и приводится к секундам) или текущее."""
    moment = datetime.fromisoformat(now) if now else datetime.now()
    return moment.isoformat(timespec="seconds")


def create_goal(
    conn: sqlite3.Connection, title: str, *, now: str | None = None, **fields: Any
) -> int:
    """Новая цель (status=active) и событие created с полным снимком.
    fields — необязательные kind, priority, target, target_date.
    При исключении вызывающий делает rollback."""
    if not title:
        raise ValueError("у цели должно быть название")
    unknown = set(fields) - {"kind", "priority", "target", "target_date"}
    if unknown:
        raise ValueError(f"нельзя задать поля: {sorted(unknown)}")
    stamp = _now(now)
    values = {
        "title": title,
        "kind": None,
        "priority": 0,
        "target": None,
        "target_date": None,
        **fields,
        "status": "active",
    }
    goal_id = add_goal(conn, {**values, "created_at": stamp, "updated_at": stamp})
    add_goal_event(
        conn,
        {"goal_id": goal_id, "event_type": "created", "payload_json": values, "occurred_at": stamp},
    )
    return goal_id


def update_goal(
    conn: sqlite3.Connection, goal_id: int, changes: dict[str, Any], now: str | None = None
) -> None:
    """Меняет поля цели. Событие updated хранит новые значения только изменившихся полей;
    если ничего не изменилось — события нет. now раньше последнего события цели — ValueError.
    При исключении вызывающий делает rollback."""
    if not changes:
        raise ValueError("нет изменений")
    unknown = set(changes) - set(FIELDS)
    if unknown:
        raise ValueError(f"нельзя менять поля: {sorted(unknown)}")
    if "title" in changes and not changes["title"]:
        raise ValueError("у цели должно быть название")
    if "status" in changes and changes["status"] not in STATUSES:
        raise ValueError(f"статус должен быть один из {STATUSES}")
    goal = get_goal(conn, goal_id)
    if goal is None:
        raise LookupError(f"цели {goal_id} нет")
    changed = {k: v for k, v in changes.items() if goal[k] != v}
    if not changed:
        return
    stamp = _now(now)
    if stamp < list_goal_events(conn, goal_id)[-1]["occurred_at"]:
        raise ValueError("время изменения раньше последнего события цели")
    update_goal_row(conn, goal_id, {**changed, "updated_at": stamp})
    add_goal_event(
        conn,
        {
            "goal_id": goal_id,
            "event_type": "updated",
            "payload_json": changed,
            "occurred_at": stamp,
        },
    )


def goal_history(conn: sqlite3.Connection, goal_id: int) -> list[dict[str, Any]]:
    """События цели по времени; для несуществующей цели — пустой список."""
    return list_goal_events(conn, goal_id)


def goals_on(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Состояние целей на конец дня `day` (YYYY-MM-DD): события до этой даты включительно,
    по порядку. Цели, созданные позже, не попадают. Порядок: priority по убыванию, затем id."""
    sql = "SELECT * FROM goal_events WHERE substr(occurred_at, 1, 10) <= ? ORDER BY occurred_at, id"
    states: dict[int, dict[str, Any]] = {}
    for event in fetch_all(conn, sql, (day,)):
        payload = json.loads(event["payload_json"])
        if event["event_type"] == "created":
            states[event["goal_id"]] = {"id": event["goal_id"], **payload}
        else:
            states[event["goal_id"]].update(payload)
    return sorted(states.values(), key=lambda s: (-s["priority"], s["id"]))


PHASE_FIELDS = ("name", "description", "start_date", "end_date")


def _check_phase_fields(fields: dict[str, Any]) -> None:
    """Общие проверки propose_phase и update_phase (goal_ids уже убран из fields)."""
    unknown = set(fields) - set(PHASE_FIELDS)
    if unknown:
        raise ValueError(f"нельзя задать поля: {sorted(unknown)}")
    if "name" in fields and not fields["name"]:
        raise ValueError("у фазы должно быть название")


def _check_phase_goals(conn: sqlite3.Connection, goal_ids: list[int]) -> None:
    for goal_id in goal_ids:
        if get_goal(conn, goal_id) is None:
            raise LookupError(f"цели {goal_id} нет")


def _check_phase_dates(start: str | None, end: str | None) -> None:
    if start and end and end < start:
        raise ValueError("конец фазы раньше начала")


def propose_phase(
    conn: sqlite3.Connection,
    name: str,
    *,
    now: str | None = None,
    **fields: Any,
) -> int:
    """Черновик фазы (proposed), связь с целями goal_ids и событие proposed.
    fields — необязательные description, start_date, end_date, goal_ids (список целей).
    При исключении вызывающий делает rollback."""
    goal_ids = sorted(set(fields.pop("goal_ids", None) or []))
    _check_phase_fields({"name": name, **fields})
    _check_phase_dates(fields.get("start_date"), fields.get("end_date"))
    _check_phase_goals(conn, goal_ids)
    stamp = _now(now)
    snapshot = {"name": name, "description": None, "start_date": None, "end_date": None, **fields}
    phase_id = add_phase(conn, {**snapshot, "created_at": stamp})
    for goal_id in goal_ids:
        add_phase_goal(conn, phase_id, goal_id)
    add_phase_event(
        conn,
        {
            "phase_id": phase_id,
            "event_type": "proposed",
            "payload_json": {**snapshot, "goal_ids": goal_ids},
            "occurred_at": stamp,
        },
    )
    return phase_id


def _proposed_phase(conn: sqlite3.Connection, phase_id: int, stamp: str) -> dict[str, Any]:
    """Фаза для решения/правки: должна быть proposed, stamp не раньше её последнего события."""
    phase = get_phase(conn, phase_id)
    if phase is None:
        raise LookupError(f"фазы {phase_id} нет")
    if phase["status"] != "proposed":
        raise ValueError(f"фаза {phase_id} уже не черновик ({phase['status']})")
    if stamp < list_phase_events(conn, phase_id)[-1]["occurred_at"]:
        raise ValueError("время раньше последнего события фазы")
    return phase


def _phase_event(
    conn: sqlite3.Connection, phase_id: int, kind: str, payload: Any, stamp: str
) -> None:
    add_phase_event(
        conn,
        {"phase_id": phase_id, "event_type": kind, "payload_json": payload, "occurred_at": stamp},
    )


def update_phase(
    conn: sqlite3.Connection, phase_id: int, changes: dict[str, Any], now: str | None = None
) -> None:
    """Правка черновика (только proposed): name, description, start_date, end_date, goal_ids
    (заменяет набор целей). Событие updated хранит новые значения изменившихся полей; если
    ничего не изменилось — события нет. now раньше последнего события — ValueError.
    При исключении вызывающий делает rollback."""
    if not changes:
        raise ValueError("нет изменений")
    fields = dict(changes)
    goal_ids = fields.pop("goal_ids", None)
    _check_phase_fields(fields)
    stamp = _now(now)
    phase = _proposed_phase(conn, phase_id, stamp)
    merged = {**phase, **fields}
    _check_phase_dates(merged["start_date"], merged["end_date"])
    changed = {k: v for k, v in fields.items() if phase[k] != v}
    if goal_ids is not None:
        goal_ids = sorted(set(goal_ids))
        _check_phase_goals(conn, goal_ids)
        if goal_ids != list_phase_goal_ids(conn, phase_id):
            changed["goal_ids"] = goal_ids
    if not changed:
        return
    row = {k: v for k, v in changed.items() if k != "goal_ids"}
    if row:
        update_phase_row(conn, phase_id, row)
    if "goal_ids" in changed:
        delete_phase_goals(conn, phase_id)
        for goal_id in changed["goal_ids"]:
            add_phase_goal(conn, phase_id, goal_id)
    _phase_event(conn, phase_id, "updated", changed, stamp)


def accept_phase(conn: sqlite3.Connection, phase_id: int, now: str | None = None) -> None:
    """Принятие фазы пользователем: proposed -> accepted, accepted_at, событие accepted.
    now раньше последнего события фазы — ValueError. При исключении вызывающий делает rollback."""
    stamp = _now(now)
    _proposed_phase(conn, phase_id, stamp)
    update_phase_row(conn, phase_id, {"status": "accepted", "accepted_at": stamp})
    _phase_event(conn, phase_id, "accepted", {"accepted_at": stamp}, stamp)


def reject_phase(conn: sqlite3.Connection, phase_id: int, now: str | None = None) -> None:
    """Отклонение черновика: proposed -> rejected, событие rejected.
    При исключении вызывающий делает rollback."""
    stamp = _now(now)
    _proposed_phase(conn, phase_id, stamp)
    update_phase_row(conn, phase_id, {"status": "rejected"})
    _phase_event(conn, phase_id, "rejected", {}, stamp)


def phases_on(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Состояние фаз на конец дня `day` (YYYY-MM-DD) по событиям: предложенные до этой даты,
    с полями, целями (goal_ids) и статусом на тот момент. Порядок по id."""
    sql = (
        "SELECT * FROM phase_events WHERE substr(occurred_at, 1, 10) <= ? ORDER BY occurred_at, id"
    )
    states: dict[int, dict[str, Any]] = {}
    for event in fetch_all(conn, sql, (day,)):
        payload = json.loads(event["payload_json"])
        kind = event["event_type"]
        if kind == "proposed":
            states[event["phase_id"]] = {
                "id": event["phase_id"],
                **payload,
                "status": "proposed",
                "accepted_at": None,
            }
        elif kind == "updated":
            states[event["phase_id"]].update(payload)
        else:
            states[event["phase_id"]].update(payload, status=kind)
    return [states[phase_id] for phase_id in sorted(states)]
