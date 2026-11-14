import sqlite3

from workload_fakes import coach_event

from ai_coach.store.agenda import (
    add_event,
    category_by_uid,
    find_by_uid,
    get_event,
    list_events,
    update_event,
)


def test_add_event_returns_id_and_defaults_to_draft(conn: sqlite3.Connection) -> None:
    event_id = add_event(conn, coach_event())
    row = get_event(conn, event_id)
    assert row is not None
    assert row["status"] == "draft"
    assert row["title"] == "Синтетическая задача коуча"


def test_get_event_missing_is_none(conn: sqlite3.Connection) -> None:
    assert get_event(conn, 999) is None


def test_update_event_changes_only_given_fields(conn: sqlite3.Connection) -> None:
    event_id = add_event(conn, coach_event())
    update_event(conn, event_id, {"status": "written", "calendar_uid": "u1"})
    row = get_event(conn, event_id)
    assert row is not None
    assert (row["status"], row["calendar_uid"], row["category"]) == ("written", "u1", "work")


def test_list_events_filters_by_date_inclusive_and_sorts_by_start(conn: sqlite3.Connection) -> None:
    late = add_event(conn, coach_event(date="2026-10-11", start_at="2026-10-11T09:00:00"))
    early = add_event(conn, coach_event(date="2026-10-10", start_at="2026-10-10T08:00:00"))
    add_event(conn, coach_event(date="2026-10-12", start_at="2026-10-12T08:00:00"))
    add_event(conn, coach_event(date="2026-10-09", start_at="2026-10-09T08:00:00"))
    found = list_events(conn, "2026-10-10", "2026-10-11")
    assert [e["id"] for e in found] == [early, late]


def test_list_events_returns_all_statuses_by_default(conn: sqlite3.Connection) -> None:
    for status in ("draft", "written", "cancelled", "removed"):
        add_event(conn, coach_event(status=status))
    assert len(list_events(conn, "2026-10-10", "2026-10-10")) == 4


def test_list_events_filters_by_statuses(conn: sqlite3.Connection) -> None:
    for status in ("draft", "written", "cancelled"):
        add_event(conn, coach_event(status=status))
    found = list_events(conn, "2026-10-10", "2026-10-10", ("draft", "written"))
    assert sorted(e["status"] for e in found) == ["draft", "written"]


def test_category_by_uid(conn: sqlite3.Connection) -> None:
    add_event(conn, coach_event(status="written", calendar_uid="u1", category="hobby"))
    assert category_by_uid(conn, "u1") == "hobby"


def test_category_by_uid_null_category_is_none(conn: sqlite3.Connection) -> None:
    add_event(
        conn, coach_event(kind="training", status="written", calendar_uid="u2", category=None)
    )
    assert category_by_uid(conn, "u2") is None


def test_category_by_uid_unknown_is_none(conn: sqlite3.Connection) -> None:
    assert category_by_uid(conn, "nope") is None


def test_find_by_uid(conn: sqlite3.Connection) -> None:
    event_id = add_event(conn, coach_event(status="written", calendar_uid="u1"))
    found = find_by_uid(conn, "u1")
    assert found is not None
    assert found["id"] == event_id


def test_find_by_uid_unknown_is_none(conn: sqlite3.Connection) -> None:
    add_event(conn, coach_event())
    assert find_by_uid(conn, "nope") is None


def test_list_done_events_joins_kind_and_title(conn: sqlite3.Connection) -> None:
    from ai_coach.store.agenda import list_done_events, mark_done

    event_id = add_event(conn, coach_event(kind="practice", title="Растяжка"))
    mark_done(conn, event_id, "2026-10-10", 0, "2026-10-10T21:00:00")
    found = list_done_events(conn, "2026-10-10", "2026-10-10")
    assert len(found) == 1
    row = found[0]
    assert (row["event_id"], row["kind"], row["title"], row["done"]) == (
        event_id,
        "practice",
        "Растяжка",
        0,
    )
    assert (row["date"], row["logged_at"]) == ("2026-10-10", "2026-10-10T21:00:00")


def test_list_done_events_period_inclusive_sorted_by_date(conn: sqlite3.Connection) -> None:
    from ai_coach.store.agenda import list_done_events, mark_done

    event_id = add_event(conn, coach_event(kind="practice"))
    for day in ("2026-10-11", "2026-10-09", "2026-10-10", "2026-10-08", "2026-10-12"):
        mark_done(conn, event_id, day, 1, f"{day}T21:00:00")
    found = list_done_events(conn, "2026-10-09", "2026-10-11")
    assert [r["date"] for r in found] == ["2026-10-09", "2026-10-10", "2026-10-11"]


def test_list_done_events_keeps_mark_of_removed_event(conn: sqlite3.Connection) -> None:
    from ai_coach.store.agenda import list_done_events, mark_done

    event_id = add_event(conn, coach_event(kind="rest", status="removed"))
    mark_done(conn, event_id, "2026-10-10", 1, "2026-10-10T21:00:00")
    assert len(list_done_events(conn, "2026-10-10", "2026-10-10")) == 1
