"""Календарь коуча в синхронизации нагрузки: свои события, переносы, пропавшие."""

import sqlite3
from datetime import date
from typing import Any

from ai_coach.store.agenda import find_by_uid, list_events
from ai_coach.workload import WorkloadConfig


def own_events(
    raw: list[dict[str, Any]], config: WorkloadConfig, conn: sqlite3.Connection, stamp: str
) -> tuple[list[dict[str, Any]], int, set[str], list[dict[str, Any]]]:
    """События календаря коуча: свои (записанные тренером, по uid) с категорией из coach_events -
    в базу, если категория есть; чужие (добавлены руками) пропускаются. Возвращает строки для
    базы, число чужих, uid всех своих и переносы: у неповторяющегося своего события время в
    календаре другое - id, start_at, end_at, date, old_date, workout_id."""
    rows: list[dict[str, Any]] = []
    foreign = 0
    seen: set[str] = set()
    moves: list[dict[str, Any]] = []
    for event in raw:
        if config.category(event["calendar"]) != "coach":
            continue
        found = find_by_uid(conn, event["uid"])
        if found is None or found["status"] != "written":
            foreign += 1
            continue
        seen.add(event["uid"])
        if found["repeat"] is None and (
            event["start_at"] != found["start_at"] or event["end_at"] != found["end_at"]
        ):
            moves.append(
                {
                    "id": found["id"],
                    "start_at": event["start_at"],
                    "end_at": event["end_at"],
                    "date": event["start_at"][:10],
                    "old_date": found["date"],
                    "workout_id": found["workout_id"],
                }
            )
        if found["category"] is not None:
            row: dict[str, Any] = {"raw_json": {}, **event, "date": event["start_at"][:10]}
            demand = config.demand(found["category"], event.get("title"))
            rows.append(
                {**row, "category": found["category"], "demand": demand, "synced_at": stamp}
            )
    return rows, foreign, seen, moves


def vanished(conn: sqlite3.Connection, first: date, last: date, seen: set[str]) -> list[int]:
    """id записанных тренером событий, пропавших из календаря: с днём начала в окне и повторяющиеся
    (их вхождения есть в окне всегда), чьего uid в календаре коуча нет."""
    written = list_events(conn, first.isoformat(), last.isoformat(), ("written",))
    ids = {e["id"]: e for e in written}
    for event in list_events(conn, "0000-01-01", first.isoformat(), ("written",)):
        if event["repeat"] is not None:
            ids[event["id"]] = event
    return [i for i, e in ids.items() if e["calendar_uid"] not in seen]


def coach_part(
    raw: list[dict[str, Any]],
    config: WorkloadConfig,
    conn: sqlite3.Connection,
    stamp: str,
    window: tuple[date, date],
) -> tuple[list[dict[str, Any]], list[int], list[dict[str, Any]], list[str]]:
    """Календарь коуча: строки своих событий для базы, id пропавших, переносы и замечания для
    итога."""
    mine, foreign, seen, moves = own_events(raw, config, conn, stamp)
    gone = vanished(conn, window[0], window[1], seen)
    notes: list[str] = []
    if foreign:
        notes.append(f"чужих событий в календаре коуча: {foreign}")
    if gone:
        notes.append(f"пропало из календаря коуча: {len(gone)}")
    if moves:
        notes.append(f"перенесено в календаре: {len(moves)}")
    for move in moves:
        if move["workout_id"] is not None and move["date"] != move["old_date"]:
            notes.append(
                f"тренировка {move['workout_id']} перенесена в календаре, на часах - старая дата"
            )
    return mine, gone, moves, notes
