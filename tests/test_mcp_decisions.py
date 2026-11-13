"""Шаг Н29, партия 3: очередь решений в сводке и инструмент get_decisions."""

import json
import sqlite3
from typing import Any

import pytest
from fake_clock import freeze
from mcp.server.mcpserver.exceptions import ToolError
from mcp_fakes import call, rows

from ai_coach.mcp_server.snapshot import SNAPSHOT_MAX_CHARS, SNAPSHOT_ROWS
from ai_coach.store.decisions import add_decision
from ai_coach.store.garmin_data import upsert_activity
from ai_coach.store.goals import add_goal
from ai_coach.store.journal import add_food
from ai_coach.store.plans import add_plan_actual, add_planned_workout

DAY = "2026-10-07"
YESTERDAY = "2026-10-06"
TOMORROW = "2026-10-08"
AFTER = "2026-10-09"


@pytest.fixture(autouse=True)
def today(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, f"{DAY} 09:00:00")


def put(
    conn: sqlite3.Connection,
    text: str = "решить",
    created: str = f"{DAY} 08:00:00",
    target: str | None = None,
    status: str = "open",
    decided: str | None = None,
    **extra: Any,
) -> int:
    later = {key: extra.pop(key) for key in ("result", "result_at") if key in extra}
    values = {"text": text, "created_at": created, "target_date": target} | extra
    decision_id = add_decision(conn, values)
    if status != "open":
        conn.execute(
            "UPDATE decision_log SET status = ?, decided_at = ? WHERE id = ?",
            (status, decided, decision_id),
        )
    for key, value in later.items():
        conn.execute(f"UPDATE decision_log SET {key} = ? WHERE id = ?", (value, decision_id))
    return decision_id


def snap(conn: sqlite3.Connection) -> dict[str, Any]:
    return call(conn, "get_morning_snapshot", date=DAY)


def pending_texts(conn: sqlite3.Connection) -> list[str]:
    return [r["text"] for r in snap(conn)["decisions_pending"]["rows"]]


def check_texts(conn: sqlite3.Connection) -> list[str]:
    return [r["text"] for r in snap(conn)["decisions_to_check"]["rows"]]


# сводка: решения на будущее


def test_snapshot_keys_are_lists_with_truncated(conn: sqlite3.Connection) -> None:
    snapshot = snap(conn)
    assert snapshot["decisions_pending"] == {"rows": [], "truncated": False}
    assert snapshot["decisions_to_check"] == {"rows": [], "truncated": False}


def test_pending_has_open_items_with_kind_and_ref(conn: sqlite3.Connection) -> None:
    put(conn, "про бег", kind="workout", ref_id=5, target=TOMORROW)
    row = snap(conn)["decisions_pending"]["rows"][0]
    assert (row["kind"], row["ref_id"], row["text"]) == ("workout", 5, "про бег")
    assert {"id", "target_date", "created_at"} <= set(row)


def test_pending_has_no_closed_items(conn: sqlite3.Connection) -> None:
    put(conn, "закрыто", status="yes", decided=f"{DAY} 08:30:00")
    put(conn, "снято", status="dropped", decided=f"{DAY} 08:30:00")
    assert pending_texts(conn) == []


def test_pending_order_by_target_date_then_no_date_last(conn: sqlite3.Connection) -> None:
    put(conn, "послезавтра", target=AFTER)
    put(conn, "завтра", target=TOMORROW)
    put(conn, "без даты")
    put(conn, "просрочен", target=YESTERDAY)
    assert pending_texts(conn) == ["просрочен", "завтра", "послезавтра", "без даты"]


def test_pending_same_day_older_created_first(conn: sqlite3.Connection) -> None:
    put(conn, "позже", created=f"{DAY} 08:30:00", target=TOMORROW)
    put(conn, "раньше", created=f"{YESTERDAY} 20:00:00", target=TOMORROW)
    assert pending_texts(conn) == ["раньше", "позже"]


def test_pending_mixes_kinds_in_one_list(conn: sqlite3.Connection) -> None:
    put(conn, "слова", target=AFTER)
    put(conn, "фаза", kind="phase", ref_id=2, target=TOMORROW)
    put(conn, "черновик", kind="workout", ref_id=7, target=DAY)
    assert pending_texts(conn) == ["черновик", "фаза", "слова"]


def test_pending_keeps_overdue_item(conn: sqlite3.Connection) -> None:
    put(conn, "просрочен", target=YESTERDAY)
    assert pending_texts(conn) == ["просрочен"]


def test_pending_truncated_over_snapshot_decisions(conn: sqlite3.Connection) -> None:
    from ai_coach.mcp_server.snapshot import SNAPSHOT_DECISIONS

    for number in range(SNAPSHOT_DECISIONS + 1):
        put(conn, f"пункт {number}")
    block = snap(conn)["decisions_pending"]
    assert block["truncated"] is True
    assert len(block["rows"]) == SNAPSHOT_DECISIONS


def test_to_check_yes_text_with_past_target_and_no_result(conn: sqlite3.Connection) -> None:
    put(conn, "съездить", target=YESTERDAY, status="yes", decided=f"{YESTERDAY} 08:00:00")
    block = snap(conn)["decisions_to_check"]
    row = block["rows"][0]
    assert (row["text"], row["target_date"]) == ("съездить", YESTERDAY)
    assert {"id", "decided_at"} <= set(row)


def test_to_check_excludes_target_today(conn: sqlite3.Connection) -> None:
    put(conn, "сегодня", target=DAY, status="yes", decided=f"{YESTERDAY} 08:00:00")
    assert check_texts(conn) == []


def test_to_check_excludes_no_target(conn: sqlite3.Connection) -> None:
    put(conn, "без даты", status="yes", decided=f"{YESTERDAY} 08:00:00")
    assert check_texts(conn) == []


def test_to_check_excludes_item_with_result(conn: sqlite3.Connection) -> None:
    put(
        conn,
        "сделано",
        target=YESTERDAY,
        status="yes",
        decided=f"{YESTERDAY} 08:00:00",
        result="kept",
        result_at=f"{DAY} 08:00:00",
    )
    assert check_texts(conn) == []


@pytest.mark.parametrize("status", ["no", "dropped", "open"])
def test_to_check_excludes_not_yes(conn: sqlite3.Connection, status: str) -> None:
    put(conn, "не да", target=YESTERDAY, status=status, decided=f"{YESTERDAY} 08:00:00")
    assert check_texts(conn) == []


def test_to_check_excludes_workout_and_phase(conn: sqlite3.Connection) -> None:
    decided = f"{YESTERDAY} 08:00:00"
    put(
        conn,
        "тренировка",
        kind="workout",
        ref_id=5,
        target=YESTERDAY,
        status="yes",
        decided=decided,
    )
    put(conn, "фаза", kind="phase", ref_id=5, target=YESTERDAY, status="yes", decided=decided)
    assert check_texts(conn) == []


def test_snapshot_with_decisions_survives_truncation(conn: sqlite3.Connection) -> None:
    big = "я" * 300
    for number in range(SNAPSHOT_ROWS * 2):
        put(conn, f"пункт {number} {big}", target=TOMORROW)
        put(
            conn,
            f"проверка {number} {big}",
            target=YESTERDAY,
            status="yes",
            decided=f"{DAY} 08:00:00",
        )
        add_goal(conn, {"title": f"Цель {number} {big}", "status": "active"})
        add_food(conn, {"logged_at": f"{DAY} 09:00:00", "text": f"еда {number} {big}"})
    snapshot = snap(conn)
    assert len(json.dumps(snapshot, ensure_ascii=False)) <= SNAPSHOT_MAX_CHARS
    assert "decisions_pending" in snapshot


# get_decisions


def test_tool_rejects_period_over_92_days(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="Период не больше 92 дней"):
        call(conn, "get_decisions", date_from="2026-01-01", date_to="2026-05-01")


def test_tool_rejects_end_before_start(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="Конец периода раньше начала"):
        call(conn, "get_decisions", date_from=DAY, date_to=YESTERDAY)


def test_tool_returns_rows_with_parts(conn: sqlite3.Connection) -> None:
    put(conn, "утро-вечер", created=f"{DAY} 09:00:00", status="yes", decided=f"{DAY} 20:00:00")
    row = rows(conn, "get_decisions", date_from=DAY, date_to=DAY)[0]
    assert (row["created_part"], row["decided_part"]) == ("morning", "evening")


def test_tool_day_part_by_row_hours(conn: sqlite3.Connection) -> None:
    put(conn, "день", created=f"{DAY} 12:00:00", status="no", decided=f"{DAY} 18:59:00")
    row = rows(conn, "get_decisions", date_from=DAY, date_to=DAY)[0]
    assert (row["created_part"], row["decided_part"]) == ("day", "day")


def stats(conn: sqlite3.Connection, start: str = DAY, end: str = DAY) -> dict[str, Any]:
    return call(conn, "get_decisions", date_from=start, date_to=end)["stats"]


def test_stats_counts_yes_and_kept_by_decided_part(conn: sqlite3.Connection) -> None:
    put(
        conn,
        "съездить",
        target=YESTERDAY,
        status="yes",
        decided=f"{DAY} 09:00:00",
        result="kept",
        result_at=f"{DAY} 10:00:00",
    )
    morning = stats(conn)["morning"]
    assert (morning["yes"], morning["kept"], morning["no"]) == (1, 1, 0)


def test_stats_counts_no_dropped_and_missed(conn: sqlite3.Connection) -> None:
    put(conn, "а", status="no", decided=f"{DAY} 13:00:00")
    put(conn, "б", status="dropped", decided=f"{DAY} 20:00:00")
    put(
        conn,
        "в",
        status="yes",
        decided=f"{DAY} 20:30:00",
        result="missed",
        result_at=f"{DAY} 21:00:00",
    )
    found = stats(conn)
    assert found["day"]["no"] == 1
    assert (found["evening"]["dropped"], found["evening"]["yes"]) == (1, 1)
    assert found["evening"]["missed"] == 1


def test_stats_ignores_open_items(conn: sqlite3.Connection) -> None:
    put(conn, "открыто", created=f"{DAY} 09:00:00")
    found = stats(conn)
    assert [found["morning"][key] for key in ("yes", "no", "dropped", "kept", "missed")] == [0] * 5


def test_stats_counts_item_created_before_period_decided_inside(
    conn: sqlite3.Connection,
) -> None:
    put(conn, "давнее", created=f"{YESTERDAY} 20:00:00", status="yes", decided=f"{DAY} 09:00:00")
    assert [r["text"] for r in rows(conn, "get_decisions", date_from=DAY, date_to=DAY)] == [
        "давнее"
    ]
    assert stats(conn)["morning"]["yes"] == 1


def test_stats_skips_item_decided_after_period(conn: sqlite3.Connection) -> None:
    put(conn, "позже", created=f"{DAY} 09:00:00", status="yes", decided=f"{TOMORROW} 09:00:00")
    assert len(rows(conn, "get_decisions", date_from=DAY, date_to=DAY)) == 1
    assert stats(conn)["morning"]["yes"] == 0


# исполнение тренировок берётся из plan_actual (Р18 = 1)


def workout_item(conn: sqlite3.Connection, status: str, actual: str | None) -> dict[str, Any]:
    planned = add_planned_workout(
        conn, {"date": YESTERDAY, "sport": "run", "name": "Бег", "workout_json": {}}
    )
    if actual is not None:
        values: dict[str, Any] = {"date": YESTERDAY, "kind": actual, "planned_id": planned}
        if actual != "skipped":
            upsert_activity(
                conn,
                {
                    "activity_id": 900,
                    "start_time_local": f"{YESTERDAY} 07:00:00",
                    "type_key": "running",
                    "name": "Бег",
                    "raw_json": {},
                },
            )
            values["activity_id"] = 900
        add_plan_actual(conn, values)
    decided = None if status == "open" else f"{YESTERDAY} 08:00:00"
    decision_id = put(
        conn,
        "Бег",
        kind="workout",
        ref_id=planned,
        target=YESTERDAY,
        status=status,
        decided=decided,
    )
    found = rows(conn, "get_decisions", date_from=YESTERDAY, date_to=DAY)
    row = next(r for r in found if r["id"] == decision_id)
    stored = conn.execute("SELECT result FROM decision_log WHERE id = ?", (decision_id,)).fetchone()
    return row | {"stored": stored[0]}


@pytest.mark.parametrize(
    ("actual", "result"),
    [("done", "kept"), ("skipped", "missed"), ("different", "missed"), (None, None)],
)
def test_workout_result_comes_from_plan_actual(
    conn: sqlite3.Connection, actual: str | None, result: str | None
) -> None:
    assert workout_item(conn, "yes", actual)["result"] == result


def test_workout_result_not_written_to_table(conn: sqlite3.Connection) -> None:
    assert workout_item(conn, "yes", "done")["stored"] is None


@pytest.mark.parametrize("actual", ["done", "skipped", None])
def test_workout_no_has_null_result(conn: sqlite3.Connection, actual: str | None) -> None:
    assert workout_item(conn, "no", actual)["result"] is None


def test_phase_result_is_null(conn: sqlite3.Connection) -> None:
    put(conn, "фаза", kind="phase", ref_id=3, status="yes", decided=f"{DAY} 08:00:00")
    row = rows(conn, "get_decisions", date_from=DAY, date_to=DAY)[0]
    assert row["result"] is None


def test_tool_over_row_limit_keeps_newest_rows(conn: sqlite3.Connection) -> None:
    for index in range(61):
        put(conn, f"п{index:02d}", created=f"{DAY} {index // 60:02d}:{index % 60:02d}:00")
    answer = call(conn, "get_decisions", date_from=DAY, date_to=DAY)
    texts = [r["text"] for r in answer["rows"]]
    assert answer["truncated"] is True
    assert (texts[0], texts[-1]) == ("п01", "п60")
