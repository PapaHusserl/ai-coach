import json
import sqlite3

import pytest

from ai_coach.goals import (
    accept_phase,
    create_goal,
    get_goal,
    get_phase,
    goal_history,
    goals_on,
    list_goals,
    list_phases,
    phases_on,
    propose_phase,
    reject_phase,
    update_goal,
    update_phase,
)
from ai_coach.store.goals import list_goal_events, list_phase_events, list_phase_goal_ids


def titles_on(conn: sqlite3.Connection, day: str) -> list[str]:
    return sorted(g["title"] for g in goals_on(conn, day))


def test_create_goal_defaults(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "Марафон", now="2026-03-01T10:00:00")
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["title"] == "Марафон"
    assert goal["status"] == "active"
    assert goal["priority"] == 0


def test_create_goal_with_fields(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(
        conn,
        "Марафон",
        kind="run",
        priority=2,
        target="3:30",
        target_date="2026-10-01",
        now="2026-03-01T10:00:00",
    )
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["kind"] == "run"
    assert goal["priority"] == 2
    assert goal["target"] == "3:30"
    assert goal["target_date"] == "2026-10-01"


def test_get_goal_missing_is_none(conn: sqlite3.Connection) -> None:
    assert get_goal(conn, 42) is None


def test_create_goal_empty_title_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        create_goal(conn, "", now="2026-03-01T10:00:00")
    assert list_goals(conn) == []


def test_update_goal_changes_only_given_fields(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "Марафон", target="3:30", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"target": "3:20"}, now="2026-03-05T10:00:00")
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["target"] == "3:20"
    assert goal["title"] == "Марафон"
    assert goal["status"] == "active"


def test_update_goal_sets_updated_at(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"priority": 3}, now="2026-03-05T10:00:00")
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["updated_at"] == "2026-03-05T10:00:00"


def test_update_goal_missing_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        update_goal(conn, 42, {"title": "x"}, now="2026-03-05T10:00:00")


def test_update_goal_unknown_field_rejected(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    with pytest.raises(ValueError):
        update_goal(conn, goal_id, {"id": 99}, now="2026-03-05T10:00:00")
    assert len(list_goal_events(conn, goal_id)) == 1


def test_update_goal_empty_changes_rejected_without_event(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    with pytest.raises(ValueError):
        update_goal(conn, goal_id, {}, now="2026-03-05T10:00:00")
    assert len(list_goal_events(conn, goal_id)) == 1


def test_list_goals_all_statuses_by_id(conn: sqlite3.Connection) -> None:
    first = create_goal(conn, "a", now="2026-03-01T10:00:00")
    second = create_goal(conn, "b", now="2026-03-01T11:00:00")
    update_goal(conn, first, {"status": "done"}, now="2026-03-02T10:00:00")
    assert [g["id"] for g in list_goals(conn)] == [first, second]


def test_list_goals_filter_by_status(conn: sqlite3.Connection) -> None:
    first = create_goal(conn, "a", now="2026-03-01T10:00:00")
    second = create_goal(conn, "b", now="2026-03-01T11:00:00")
    update_goal(conn, first, {"status": "done"}, now="2026-03-02T10:00:00")
    assert [g["id"] for g in list_goals(conn, status="active")] == [second]


def test_create_writes_created_event(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "Марафон", target="3:30", now="2026-03-01T10:00:00")
    events = list_goal_events(conn, goal_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "created"
    assert events[0]["occurred_at"] == "2026-03-01T10:00:00"
    assert json.loads(events[0]["payload_json"])["title"] == "Марафон"


def test_update_writes_updated_event_with_changes(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "Марафон", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"target": "3:20"}, now="2026-03-05T10:00:00")
    events = list_goal_events(conn, goal_id)
    assert [e["event_type"] for e in events] == ["created", "updated"]
    assert events[1]["occurred_at"] == "2026-03-05T10:00:00"
    assert json.loads(events[1]["payload_json"])["target"] == "3:20"


def test_every_change_writes_one_event(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"title": "g2"}, now="2026-03-02T10:00:00")
    update_goal(conn, goal_id, {"priority": 5}, now="2026-03-03T10:00:00")
    update_goal(conn, goal_id, {"status": "done"}, now="2026-03-04T10:00:00")
    assert len(list_goal_events(conn, goal_id)) == 4


def test_events_belong_to_their_goal(conn: sqlite3.Connection) -> None:
    first = create_goal(conn, "a", now="2026-03-01T10:00:00")
    second = create_goal(conn, "b", now="2026-03-01T11:00:00")
    update_goal(conn, second, {"priority": 1}, now="2026-03-02T10:00:00")
    assert len(list_goal_events(conn, first)) == 1
    assert len(list_goal_events(conn, second)) == 2


def test_goal_history_returns_events_in_order(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"priority": 1}, now="2026-03-02T10:00:00")
    history = goal_history(conn, goal_id)
    assert [e["occurred_at"] for e in history] == ["2026-03-01T10:00:00", "2026-03-02T10:00:00"]


def test_goal_history_missing_goal_is_empty(conn: sqlite3.Connection) -> None:
    assert goal_history(conn, 42) == []


def test_goals_on_before_any_goal_is_empty(conn: sqlite3.Connection) -> None:
    create_goal(conn, "a", now="2026-03-10T10:00:00")
    assert goals_on(conn, "2026-03-09") == []


def test_goals_on_creation_day_includes_goal(conn: sqlite3.Connection) -> None:
    create_goal(conn, "a", now="2026-03-10T23:30:00")
    assert titles_on(conn, "2026-03-10") == ["a"]


def test_goals_on_empty_database(conn: sqlite3.Connection) -> None:
    assert goals_on(conn, "2026-03-10") == []


def test_goals_on_returns_state_as_of_date(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "Марафон", target="3:30", priority=1, now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"target": "3:20"}, now="2026-03-10T10:00:00")
    update_goal(conn, goal_id, {"target": "3:10", "priority": 2}, now="2026-03-20T10:00:00")

    early = goals_on(conn, "2026-03-05")
    middle = goals_on(conn, "2026-03-15")
    late = goals_on(conn, "2026-03-25")

    assert [(g["target"], g["priority"]) for g in early] == [("3:30", 1)]
    assert [(g["target"], g["priority"]) for g in middle] == [("3:20", 1)]
    assert [(g["target"], g["priority"]) for g in late] == [("3:10", 2)]


def test_goals_on_change_day_sees_change(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", target="a", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"target": "b"}, now="2026-03-10T08:00:00")
    assert goals_on(conn, "2026-03-10")[0]["target"] == "b"
    assert goals_on(conn, "2026-03-09")[0]["target"] == "a"


def test_goals_on_same_day_changes_last_wins(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", target="a", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"target": "b"}, now="2026-03-10T08:00:00")
    update_goal(conn, goal_id, {"target": "c"}, now="2026-03-10T09:00:00")
    assert goals_on(conn, "2026-03-10")[0]["target"] == "c"


def test_goals_on_status_history(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"status": "done"}, now="2026-03-10T10:00:00")
    assert goals_on(conn, "2026-03-05")[0]["status"] == "active"
    assert goals_on(conn, "2026-03-10")[0]["status"] == "done"


def test_goals_on_does_not_change_current_state(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", target="a", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"target": "b"}, now="2026-03-10T10:00:00")
    goals_on(conn, "2026-03-05")
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["target"] == "b"
    assert len(list_goal_events(conn, goal_id)) == 2


def test_goals_on_series_of_changes_several_goals(conn: sqlite3.Connection) -> None:
    marathon = create_goal(conn, "Марафон", now="2026-03-01T10:00:00")
    swim = create_goal(conn, "Плавание", now="2026-03-05T10:00:00")
    update_goal(conn, marathon, {"title": "Полумарафон"}, now="2026-03-10T10:00:00")
    update_goal(conn, swim, {"status": "cancelled"}, now="2026-03-12T10:00:00")
    bike = create_goal(conn, "Вело", now="2026-03-15T10:00:00")

    assert titles_on(conn, "2026-02-28") == []
    assert titles_on(conn, "2026-03-03") == ["Марафон"]
    assert titles_on(conn, "2026-03-08") == ["Марафон", "Плавание"]
    assert titles_on(conn, "2026-03-11") == ["Плавание", "Полумарафон"]
    assert titles_on(conn, "2026-03-20") == ["Вело", "Плавание", "Полумарафон"]
    statuses = {g["id"]: g["status"] for g in goals_on(conn, "2026-03-20")}
    assert statuses == {marathon: "active", swim: "cancelled", bike: "active"}


def test_goals_on_reflects_cleared_field(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", target="3:30", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"target": None}, now="2026-03-10T10:00:00")
    assert goals_on(conn, "2026-03-05")[0]["target"] == "3:30"
    assert goals_on(conn, "2026-03-15")[0]["target"] is None


def test_propose_phase_is_proposed(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(
        conn,
        "База",
        description="Объём",
        start_date="2026-04-01",
        end_date="2026-04-28",
        now="2026-03-25T10:00:00",
    )
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["name"] == "База"
    assert phase["description"] == "Объём"
    assert phase["start_date"] == "2026-04-01"
    assert phase["end_date"] == "2026-04-28"
    assert phase["status"] == "proposed"
    assert phase["accepted_at"] is None


def test_get_phase_missing_is_none(conn: sqlite3.Connection) -> None:
    assert get_phase(conn, 42) is None


def test_propose_phase_empty_name_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        propose_phase(conn, "", now="2026-03-25T10:00:00")
    assert list_phases(conn) == []


def test_propose_phase_end_before_start_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        propose_phase(
            conn, "База", start_date="2026-04-28", end_date="2026-04-01", now="2026-03-25T10:00:00"
        )
    assert list_phases(conn) == []


def test_accept_phase(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    accept_phase(conn, phase_id, now="2026-03-26T09:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "accepted"
    assert phase["accepted_at"] == "2026-03-26T09:00:00"
    assert phase["name"] == "База"


def test_accept_phase_twice_rejected_and_keeps_first_time(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    accept_phase(conn, phase_id, now="2026-03-26T09:00:00")
    with pytest.raises(ValueError):
        accept_phase(conn, phase_id, now="2026-03-27T09:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["accepted_at"] == "2026-03-26T09:00:00"


def test_accept_phase_missing_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        accept_phase(conn, 42, now="2026-03-26T09:00:00")


def test_accept_touches_only_that_phase(conn: sqlite3.Connection) -> None:
    first = propose_phase(conn, "a", now="2026-03-25T10:00:00")
    second = propose_phase(conn, "b", now="2026-03-25T11:00:00")
    accept_phase(conn, first, now="2026-03-26T09:00:00")
    other = get_phase(conn, second)
    assert other is not None
    assert other["status"] == "proposed"


def test_list_phases_filter_by_status(conn: sqlite3.Connection) -> None:
    first = propose_phase(conn, "a", now="2026-03-25T10:00:00")
    second = propose_phase(conn, "b", now="2026-03-25T11:00:00")
    accept_phase(conn, first, now="2026-03-26T09:00:00")
    assert [p["id"] for p in list_phases(conn)] == [first, second]
    assert [p["id"] for p in list_phases(conn, status="proposed")] == [second]
    assert [p["id"] for p in list_phases(conn, status="accepted")] == [first]


def test_phase_changes_do_not_write_goal_events(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    accept_phase(conn, phase_id, now="2026-03-26T09:00:00")
    assert len(list_goal_events(conn, goal_id)) == 1
    assert len(list_goal_events(conn)) == 1


def test_default_now_is_used_when_omitted(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g")
    events = list_goal_events(conn, goal_id)
    assert len(events) == 1
    assert events[0]["occurred_at"]


def test_update_goal_before_created_at_rejected(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-10T10:00:00")
    with pytest.raises(ValueError):
        update_goal(conn, goal_id, {"priority": 1}, now="2026-03-09T10:00:00")
    assert len(list_goal_events(conn, goal_id)) == 1
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["priority"] == 0


def test_update_goal_before_last_event_rejected(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"priority": 1}, now="2026-03-10T10:00:00")
    with pytest.raises(ValueError):
        update_goal(conn, goal_id, {"priority": 2}, now="2026-03-05T10:00:00")
    assert len(list_goal_events(conn, goal_id)) == 2
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["priority"] == 1


def test_update_goal_at_same_time_as_last_event_allowed(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"priority": 1}, now="2026-03-01T10:00:00")
    assert len(list_goal_events(conn, goal_id)) == 2


def test_update_goal_earlier_than_other_goal_event_allowed(conn: sqlite3.Connection) -> None:
    first = create_goal(conn, "a", now="2026-03-01T10:00:00")
    create_goal(conn, "b", now="2026-03-20T10:00:00")
    update_goal(conn, first, {"priority": 1}, now="2026-03-05T10:00:00")
    assert len(list_goal_events(conn, first)) == 2


@pytest.mark.parametrize(
    "bad", ["вчера", "05.03.2026 10:00", "2026-13-01T10:00:00", "2026-03-05T25:00:00"]
)
def test_create_goal_bad_now_rejected(conn: sqlite3.Connection, bad: str) -> None:
    with pytest.raises(ValueError):
        create_goal(conn, "g", now=bad)
    assert list_goals(conn) == []


@pytest.mark.parametrize("bad", ["вчера", "05.03.2026 10:00", "2026-13-01T10:00:00"])
def test_update_goal_bad_now_rejected(conn: sqlite3.Connection, bad: str) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    with pytest.raises(ValueError):
        update_goal(conn, goal_id, {"priority": 1}, now=bad)
    assert len(list_goal_events(conn, goal_id)) == 1


def test_propose_phase_bad_now_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        propose_phase(conn, "База", now="вчера")
    assert list_phases(conn) == []


def test_accept_phase_bad_now_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    with pytest.raises(ValueError):
        accept_phase(conn, phase_id, now="вчера")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "proposed"


@pytest.mark.parametrize("status", ["active", "done", "cancelled"])
def test_update_goal_allowed_statuses(conn: sqlite3.Connection, status: str) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    update_goal(conn, goal_id, {"status": status}, now="2026-03-02T10:00:00")
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["status"] == status


def test_update_goal_garbage_status_rejected(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "g", now="2026-03-01T10:00:00")
    with pytest.raises(ValueError):
        update_goal(conn, goal_id, {"status": "мусор"}, now="2026-03-02T10:00:00")
    assert len(list_goal_events(conn, goal_id)) == 1
    goal = get_goal(conn, goal_id)
    assert goal is not None
    assert goal["status"] == "active"


def test_propose_phase_links_goals(conn: sqlite3.Connection) -> None:
    first = create_goal(conn, "a", now="2026-03-01T10:00:00")
    second = create_goal(conn, "b", now="2026-03-01T11:00:00")
    phase_id = propose_phase(conn, "База", goal_ids=[second, first], now="2026-03-25T10:00:00")
    assert list_phase_goal_ids(conn, phase_id) == [first, second]


def test_propose_phase_without_goals_has_no_links(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    assert list_phase_goal_ids(conn, phase_id) == []


def test_propose_phase_missing_goal_rejected(conn: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        propose_phase(conn, "База", goal_ids=[42], now="2026-03-25T10:00:00")


def test_propose_phase_writes_proposed_event(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    events = list_phase_events(conn, phase_id)
    assert [e["event_type"] for e in events] == ["proposed"]
    assert events[0]["occurred_at"] == "2026-03-25T10:00:00"


def test_accept_phase_writes_accepted_event(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    accept_phase(conn, phase_id, now="2026-03-26T09:00:00")
    events = list_phase_events(conn, phase_id)
    assert [e["event_type"] for e in events] == ["proposed", "accepted"]
    assert events[1]["occurred_at"] == "2026-03-26T09:00:00"


def test_accept_phase_before_proposal_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    with pytest.raises(ValueError):
        accept_phase(conn, phase_id, now="2026-03-24T10:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "proposed"
    assert len(list_phase_events(conn, phase_id)) == 1


def test_rejected_accept_writes_no_event(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    accept_phase(conn, phase_id, now="2026-03-26T09:00:00")
    with pytest.raises(ValueError):
        accept_phase(conn, phase_id, now="2026-03-27T09:00:00")
    assert len(list_phase_events(conn, phase_id)) == 2


def test_phases_on_before_proposal_is_empty(conn: sqlite3.Connection) -> None:
    propose_phase(conn, "База", now="2026-03-25T10:00:00")
    assert phases_on(conn, "2026-03-24") == []


def test_phases_on_empty_database(conn: sqlite3.Connection) -> None:
    assert phases_on(conn, "2026-03-24") == []


def test_phases_on_proposed_until_accepted(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    accept_phase(conn, phase_id, now="2026-03-28T09:00:00")
    assert [p["status"] for p in phases_on(conn, "2026-03-25")] == ["proposed"]
    assert [p["status"] for p in phases_on(conn, "2026-03-27")] == ["proposed"]
    assert [p["status"] for p in phases_on(conn, "2026-03-28")] == ["accepted"]
    assert [p["status"] for p in phases_on(conn, "2026-04-30")] == ["accepted"]


def test_phases_on_returns_fields_and_goal_ids(conn: sqlite3.Connection) -> None:
    goal_id = create_goal(conn, "a", now="2026-03-01T10:00:00")
    phase_id = propose_phase(
        conn,
        "База",
        goal_ids=[goal_id],
        start_date="2026-04-01",
        end_date="2026-04-28",
        now="2026-03-25T10:00:00",
    )
    (phase,) = phases_on(conn, "2026-03-30")
    assert phase["id"] == phase_id
    assert phase["name"] == "База"
    assert phase["start_date"] == "2026-04-01"
    assert phase["end_date"] == "2026-04-28"
    assert phase["goal_ids"] == [goal_id]


def test_phases_on_several_phases_by_id(conn: sqlite3.Connection) -> None:
    first = propose_phase(conn, "a", now="2026-03-10T10:00:00")
    second = propose_phase(conn, "b", now="2026-03-20T10:00:00")
    accept_phase(conn, first, now="2026-03-22T10:00:00")
    assert [(p["id"], p["status"]) for p in phases_on(conn, "2026-03-15")] == [(first, "proposed")]
    assert [(p["id"], p["status"]) for p in phases_on(conn, "2026-03-25")] == [
        (first, "accepted"),
        (second, "proposed"),
    ]


def test_reject_phase(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    reject_phase(conn, phase_id, now="2026-03-26T09:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "rejected"
    assert phase["accepted_at"] is None


def test_reject_phase_writes_rejected_event(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    reject_phase(conn, phase_id, now="2026-03-26T09:00:00")
    events = list_phase_events(conn, phase_id)
    assert [e["event_type"] for e in events] == ["proposed", "rejected"]
    assert events[1]["occurred_at"] == "2026-03-26T09:00:00"


def test_reject_accepted_phase_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    accept_phase(conn, phase_id, now="2026-03-26T09:00:00")
    with pytest.raises(ValueError):
        reject_phase(conn, phase_id, now="2026-03-27T09:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "accepted"
    assert len(list_phase_events(conn, phase_id)) == 2


def test_reject_phase_twice_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    reject_phase(conn, phase_id, now="2026-03-26T09:00:00")
    with pytest.raises(ValueError):
        reject_phase(conn, phase_id, now="2026-03-27T09:00:00")
    assert len(list_phase_events(conn, phase_id)) == 2


def test_reject_phase_missing_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        reject_phase(conn, 42, now="2026-03-26T09:00:00")


def test_reject_phase_before_proposal_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    with pytest.raises(ValueError):
        reject_phase(conn, phase_id, now="2026-03-24T10:00:00")
    assert len(list_phase_events(conn, phase_id)) == 1


def test_reject_phase_bad_now_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    with pytest.raises(ValueError):
        reject_phase(conn, phase_id, now="вчера")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "proposed"


def test_rejected_phase_cannot_be_accepted(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    reject_phase(conn, phase_id, now="2026-03-26T09:00:00")
    with pytest.raises(ValueError):
        accept_phase(conn, phase_id, now="2026-03-27T09:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["status"] == "rejected"


def test_list_phases_filter_rejected(conn: sqlite3.Connection) -> None:
    first = propose_phase(conn, "a", now="2026-03-25T10:00:00")
    propose_phase(conn, "b", now="2026-03-25T11:00:00")
    reject_phase(conn, first, now="2026-03-26T09:00:00")
    assert [p["id"] for p in list_phases(conn, status="rejected")] == [first]


def test_update_phase_changes_only_given_fields(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(
        conn, "База", description="Объём", start_date="2026-04-01", now="2026-03-25T10:00:00"
    )
    update_phase(conn, phase_id, {"name": "Основа"}, now="2026-03-26T10:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["name"] == "Основа"
    assert phase["description"] == "Объём"
    assert phase["start_date"] == "2026-04-01"
    assert phase["status"] == "proposed"


def test_update_phase_all_fields(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    update_phase(
        conn,
        phase_id,
        {"name": "n", "description": "d", "start_date": "2026-05-01", "end_date": "2026-05-31"},
        now="2026-03-26T10:00:00",
    )
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert (phase["name"], phase["description"]) == ("n", "d")
    assert (phase["start_date"], phase["end_date"]) == ("2026-05-01", "2026-05-31")


def test_update_phase_writes_updated_event(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    update_phase(conn, phase_id, {"name": "Основа"}, now="2026-03-26T10:00:00")
    events = list_phase_events(conn, phase_id)
    assert [e["event_type"] for e in events] == ["proposed", "updated"]
    assert events[1]["occurred_at"] == "2026-03-26T10:00:00"
    assert json.loads(events[1]["payload_json"])["name"] == "Основа"


def test_update_phase_replaces_goal_set(conn: sqlite3.Connection) -> None:
    a = create_goal(conn, "a", now="2026-03-01T10:00:00")
    b = create_goal(conn, "b", now="2026-03-01T10:00:00")
    c = create_goal(conn, "c", now="2026-03-01T10:00:00")
    phase_id = propose_phase(conn, "База", goal_ids=[a, b], now="2026-03-25T10:00:00")
    update_phase(conn, phase_id, {"goal_ids": [b, c]}, now="2026-03-26T10:00:00")
    assert list_phase_goal_ids(conn, phase_id) == [b, c]


def test_update_phase_empty_goal_ids_clears_links(conn: sqlite3.Connection) -> None:
    a = create_goal(conn, "a", now="2026-03-01T10:00:00")
    phase_id = propose_phase(conn, "База", goal_ids=[a], now="2026-03-25T10:00:00")
    update_phase(conn, phase_id, {"goal_ids": []}, now="2026-03-26T10:00:00")
    assert list_phase_goal_ids(conn, phase_id) == []


def test_update_phase_without_goal_ids_keeps_links(conn: sqlite3.Connection) -> None:
    a = create_goal(conn, "a", now="2026-03-01T10:00:00")
    phase_id = propose_phase(conn, "База", goal_ids=[a], now="2026-03-25T10:00:00")
    update_phase(conn, phase_id, {"name": "Основа"}, now="2026-03-26T10:00:00")
    assert list_phase_goal_ids(conn, phase_id) == [a]


def test_update_phase_missing_goal_rejected(conn: sqlite3.Connection) -> None:
    a = create_goal(conn, "a", now="2026-03-01T10:00:00")
    phase_id = propose_phase(conn, "База", goal_ids=[a], now="2026-03-25T10:00:00")
    with pytest.raises(LookupError):
        update_phase(conn, phase_id, {"goal_ids": [42]}, now="2026-03-26T10:00:00")
    assert list_phase_goal_ids(conn, phase_id) == [a]
    assert len(list_phase_events(conn, phase_id)) == 1


def test_update_phase_missing_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        update_phase(conn, 42, {"name": "x"}, now="2026-03-26T10:00:00")


@pytest.mark.parametrize("finish", [accept_phase, reject_phase])
def test_update_phase_not_proposed_rejected(conn: sqlite3.Connection, finish) -> None:  # type: ignore[no-untyped-def]
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    finish(conn, phase_id, now="2026-03-26T09:00:00")
    with pytest.raises(ValueError):
        update_phase(conn, phase_id, {"name": "x"}, now="2026-03-27T09:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["name"] == "База"
    assert len(list_phase_events(conn, phase_id)) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"name": ""},
        {"id": 5},
        {"status": "accepted"},
        {"end_date": "2026-03-01", "start_date": "2026-04-01"},
    ],
)
def test_update_phase_invalid_changes_rejected(conn: sqlite3.Connection, changes: dict) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    with pytest.raises(ValueError):
        update_phase(conn, phase_id, changes, now="2026-03-26T10:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["name"] == "База"
    assert phase["status"] == "proposed"
    assert len(list_phase_events(conn, phase_id)) == 1


def test_update_phase_end_before_existing_start_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", start_date="2026-04-10", now="2026-03-25T10:00:00")
    with pytest.raises(ValueError):
        update_phase(conn, phase_id, {"end_date": "2026-04-01"}, now="2026-03-26T10:00:00")
    assert len(list_phase_events(conn, phase_id)) == 1


def test_update_phase_before_last_event_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    update_phase(conn, phase_id, {"name": "b"}, now="2026-03-27T10:00:00")
    with pytest.raises(ValueError):
        update_phase(conn, phase_id, {"name": "c"}, now="2026-03-26T10:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["name"] == "b"
    assert len(list_phase_events(conn, phase_id)) == 2


def test_update_phase_bad_now_rejected(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    with pytest.raises(ValueError):
        update_phase(conn, phase_id, {"name": "b"}, now="вчера")
    assert len(list_phase_events(conn, phase_id)) == 1


def test_accept_after_update_keeps_edited_fields(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    update_phase(conn, phase_id, {"name": "Основа"}, now="2026-03-26T10:00:00")
    accept_phase(conn, phase_id, now="2026-03-27T10:00:00")
    phase = get_phase(conn, phase_id)
    assert phase is not None
    assert phase["name"] == "Основа"
    assert phase["status"] == "accepted"


def test_phases_on_reflects_edits_by_date(conn: sqlite3.Connection) -> None:
    a = create_goal(conn, "a", now="2026-03-01T10:00:00")
    b = create_goal(conn, "b", now="2026-03-01T10:00:00")
    phase_id = propose_phase(
        conn, "База", goal_ids=[a], start_date="2026-04-01", now="2026-03-25T10:00:00"
    )
    update_phase(conn, phase_id, {"name": "Основа", "goal_ids": [b]}, now="2026-03-28T10:00:00")
    update_phase(conn, phase_id, {"start_date": "2026-04-07"}, now="2026-03-30T10:00:00")
    accept_phase(conn, phase_id, now="2026-04-02T10:00:00")

    (early,) = phases_on(conn, "2026-03-26")
    (middle,) = phases_on(conn, "2026-03-29")
    (edited,) = phases_on(conn, "2026-03-31")
    (accepted,) = phases_on(conn, "2026-04-02")

    assert (early["name"], early["goal_ids"], early["start_date"]) == ("База", [a], "2026-04-01")
    assert (middle["name"], middle["goal_ids"], middle["start_date"]) == (
        "Основа",
        [b],
        "2026-04-01",
    )
    assert (edited["start_date"], edited["status"]) == ("2026-04-07", "proposed")
    assert (accepted["name"], accepted["start_date"], accepted["status"]) == (
        "Основа",
        "2026-04-07",
        "accepted",
    )


def test_phases_on_rejected_status_from_reject_day(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", now="2026-03-25T10:00:00")
    reject_phase(conn, phase_id, now="2026-03-28T10:00:00")
    assert [p["status"] for p in phases_on(conn, "2026-03-27")] == ["proposed"]
    assert [p["status"] for p in phases_on(conn, "2026-03-28")] == ["rejected"]
    assert [p["status"] for p in phases_on(conn, "2026-05-01")] == ["rejected"]


def test_phases_on_rejected_phase_keeps_name_and_goals(conn: sqlite3.Connection) -> None:
    a = create_goal(conn, "a", now="2026-03-01T10:00:00")
    phase_id = propose_phase(conn, "База", goal_ids=[a], now="2026-03-25T10:00:00")
    reject_phase(conn, phase_id, now="2026-03-28T10:00:00")
    (phase,) = phases_on(conn, "2026-03-30")
    assert phase["name"] == "База"
    assert phase["goal_ids"] == [a]


def test_phases_on_clearing_field_by_update(conn: sqlite3.Connection) -> None:
    phase_id = propose_phase(conn, "База", description="d", now="2026-03-25T10:00:00")
    update_phase(conn, phase_id, {"description": None}, now="2026-03-26T10:00:00")
    assert phases_on(conn, "2026-03-25")[0]["description"] == "d"
    assert phases_on(conn, "2026-03-27")[0]["description"] is None
