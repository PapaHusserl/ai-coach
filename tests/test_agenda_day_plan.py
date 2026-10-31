"""План дня (шаг Н13): busy_spans, free_slots, plan_day, create_day_plan."""

import random
import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any

import pytest
from workload_fakes import coach_event, stored_event

from ai_coach.agenda.day_plan import (
    BREAK_MIN,
    FOCUS_MAX,
    FOCUS_MIN,
    REST_MIN,
    SNACK_MIN,
    TRAINING_PAD_MIN,
    WEEKDAY,
    WEEKEND,
    Task,
    Training,
    create_day_plan,
    plan_day,
)
from ai_coach.agenda.service import AgendaError, agenda_rows
from ai_coach.agenda.slots import MIN_SLOT, STEP_MIN, busy_spans, free_slots
from ai_coach.store.agenda import add_event, get_event
from ai_coach.store.plans import add_planned_workout
from ai_coach.store.workload import replace_calendar_window

MON = date(2026, 11, 2)
SAT = date(2026, 11, 7)
SUN = date(2026, 11, 8)
NOW = datetime(2026, 11, 1, 12, 0)  # воскресенье накануне понедельника


def at(day: date, clock: str) -> datetime:
    """clock 'HH:MM'; '24:00' - полночь следующего дня."""
    if clock == "24:00":
        return datetime.combine(day + timedelta(days=1), datetime.min.time())
    return datetime.fromisoformat(f"{day.isoformat()}T{clock}")


def span(day: date, first: str, last: str) -> tuple[datetime, datetime]:
    return at(day, first), at(day, last)


def window(day: date, first: str = "10:00") -> tuple[datetime, datetime]:
    return at(day, first), at(day, "24:00")


# --- free_slots ---


def test_free_slots_empty_day_is_one_window() -> None:
    assert free_slots(window(MON), []) == [window(MON)]


def test_free_slots_busy_splits_window() -> None:
    busy = [span(MON, "12:00", "13:00"), span(MON, "15:30", "16:00")]
    assert free_slots(window(MON), busy) == [
        span(MON, "10:00", "12:00"),
        span(MON, "13:00", "15:30"),
        (at(MON, "16:00"), at(MON, "24:00")),
    ]


def test_free_slots_busy_started_before_window() -> None:
    busy = [span(MON, "09:00", "10:30")]
    assert free_slots(window(MON), busy) == [(at(MON, "10:30"), at(MON, "24:00"))]


def test_free_slots_busy_going_past_window_end() -> None:
    busy = [(at(MON, "23:00"), at(MON, "24:00") + timedelta(hours=1))]
    assert free_slots(window(MON), busy) == [span(MON, "10:00", "23:00")]


def test_free_slots_drops_gap_shorter_than_min_slot() -> None:
    gap = MIN_SLOT - 10
    busy = [
        span(MON, "10:00", "12:00"),
        (at(MON, "12:00") + timedelta(minutes=gap), at(MON, "24:00")),
    ]
    assert free_slots(window(MON), busy) == []


def test_free_slots_keeps_gap_of_exactly_min_slot() -> None:
    busy = [
        span(MON, "10:00", "12:00"),
        (at(MON, "12:00") + timedelta(minutes=MIN_SLOT), at(MON, "24:00")),
    ]
    assert free_slots(window(MON), busy) == [(at(MON, "12:00"), at(MON, "12:30"))]


def test_free_slots_merges_overlapping_busy() -> None:
    busy = [span(MON, "12:30", "14:00"), span(MON, "12:00", "13:00")]
    assert free_slots(window(MON), busy) == [
        span(MON, "10:00", "12:00"),
        (at(MON, "14:00"), at(MON, "24:00")),
    ]


def test_free_slots_start_is_rounded_up_to_step() -> None:
    busy = [span(MON, "10:00", "12:07")]
    first = free_slots(window(MON), busy)[0][0]
    assert first == at(MON, "12:10")
    assert STEP_MIN == 5


# --- busy_spans ---


def calendar(conn: sqlite3.Connection, day: date, *events: dict[str, Any]) -> None:
    replace_calendar_window(conn, day.isoformat(), day.isoformat(), list(events))


def meeting(day: date, first: str, last: str, **fields: Any) -> dict[str, Any]:
    return stored_event(
        "work",
        start_at=f"{day.isoformat()}T{first}:00",
        end_at=f"{day.isoformat()}T{last}:00",
        **fields,
    )


def coach(conn: sqlite3.Connection, day: date, first: str, last: str, **fields: Any) -> None:
    base = {
        "date": day.isoformat(),
        "start_at": f"{day.isoformat()}T{first}:00",
        "end_at": f"{day.isoformat()}T{last}:00",
        "status": "draft",
    }
    add_event(conn, coach_event(**(base | fields)))


def test_busy_spans_takes_calendar_event(conn: sqlite3.Connection) -> None:
    calendar(conn, MON, meeting(MON, "12:00", "13:00"))
    assert busy_spans(conn, MON) == [span(MON, "12:00", "13:00")]


@pytest.mark.parametrize("fields", [{"status": "cancelled"}, {"my_status": "declined"}])
def test_busy_spans_skips_cancelled_and_declined(
    conn: sqlite3.Connection, fields: dict[str, Any]
) -> None:
    calendar(conn, MON, meeting(MON, "12:00", "13:00", **fields))
    assert busy_spans(conn, MON) == []


def test_busy_spans_skips_all_day(conn: sqlite3.Connection) -> None:
    calendar(conn, MON, meeting(MON, "00:00", "23:59", all_day=True))
    assert busy_spans(conn, MON) == []


def test_busy_spans_unknown_category_is_busy(conn: sqlite3.Connection) -> None:
    event = stored_event("unknown", start_at=f"{MON}T14:00:00", end_at=f"{MON}T15:00:00", uid="u2")
    calendar(conn, MON, event)
    assert busy_spans(conn, MON) == [span(MON, "14:00", "15:00")]


def test_busy_spans_skips_checkin(conn: sqlite3.Connection) -> None:
    coach(conn, MON, "11:00", "11:05", kind="checkin", category=None)
    assert busy_spans(conn, MON) == []


@pytest.mark.parametrize("kind", ["task", "rest", "training"])
def test_busy_spans_takes_coach_events_of_other_kinds(conn: sqlite3.Connection, kind: str) -> None:
    category = {"task": "work", "rest": "rest", "training": None}[kind]
    coach(conn, MON, "16:00", "17:00", kind=kind, category=category)
    assert busy_spans(conn, MON) == [span(MON, "16:00", "17:00")]


def test_busy_spans_takes_written_coach_event(conn: sqlite3.Connection) -> None:
    coach(conn, MON, "16:00", "17:00", status="written", calendar_uid="x")
    assert busy_spans(conn, MON) == [span(MON, "16:00", "17:00")]


def test_busy_spans_skips_cancelled_coach_event(conn: sqlite3.Connection) -> None:
    coach(conn, MON, "16:00", "17:00", status="cancelled")
    assert busy_spans(conn, MON) == []


def test_busy_spans_clips_event_started_yesterday(conn: sqlite3.Connection) -> None:
    yesterday = MON - timedelta(days=1)
    event = stored_event(
        "work",
        start_at=f"{yesterday}T23:00:00",
        end_at=f"{MON}T01:00:00",
        date=yesterday.isoformat(),
    )
    replace_calendar_window(conn, yesterday.isoformat(), yesterday.isoformat(), [event])
    assert busy_spans(conn, MON) == [(at(MON, "00:00"), at(MON, "01:00"))]


# --- plan_day ---


def plan(
    day: date = MON,
    busy: list[tuple[datetime, datetime]] | None = None,
    tasks: list[Task] | None = None,
    training: Training | None = None,
    first: str = "10:00",
) -> tuple[list[dict[str, Any]], list[str]]:
    weekend = day.weekday() >= 5
    return plan_day(
        WEEKEND if weekend else WEEKDAY,
        window(day, first),
        busy or [],
        tasks or [],
        training,
        weekend,
    )


def shape(blocks: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [(b["kind"], b["start_at"][11:16], b["end_at"][11:16]) for b in blocks]


def named(blocks: list[dict[str, Any]], title: str) -> dict[str, Any]:
    found = [b for b in blocks if b["title"] == title]
    assert len(found) == 1, blocks
    return found[0]


def test_weekday_layout_without_busy_and_tasks() -> None:
    blocks, skipped = plan()
    assert shape(blocks) == [
        ("meal", "11:00", "12:00"),
        ("focus", "12:00", "13:30"),
        ("focus", "13:45", "15:15"),
        ("meal", "15:30", "15:45"),
        ("rest", "15:45", "16:15"),
        ("focus", "16:15", "17:45"),
        ("meal", "19:00", "20:00"),
    ]
    assert skipped == []


def test_weekday_titles_and_categories() -> None:
    blocks, _ = plan()
    assert [b["title"] for b in blocks if b["kind"] == "meal"] == ["Завтрак", "Перекус", "Ужин"]
    assert named(blocks, "Прогулка / отдых")["category"] == "rest"
    assert {b["category"] for b in blocks if b["kind"] in ("focus", "meal")} == {None}


def test_weekday_has_focus_max_blocks_and_none_in_evening() -> None:
    blocks, _ = plan()
    focus = [b for b in blocks if b["kind"] == "focus"]
    assert len(focus) == FOCUS_MAX
    assert all(b["start_at"][11:16] < "19:00" for b in focus)
    assert all(b["end_at"] > b["start_at"] for b in blocks)
    assert (FOCUS_MIN, BREAK_MIN, SNACK_MIN, REST_MIN) == (90, 15, 15, 30)


def test_weekday_hour_before_breakfast_is_not_focus() -> None:
    blocks, _ = plan()
    assert all(b["start_at"][11:16] >= "11:00" for b in blocks)


def test_weekend_has_no_focus() -> None:
    blocks, skipped = plan(SAT, first="11:00")
    assert shape(blocks) == [
        ("meal", "12:00", "13:00"),
        ("meal", "16:00", "16:15"),
        ("rest", "16:15", "16:45"),
        ("meal", "19:00", "20:00"),
    ]
    assert skipped == []


def test_tasks_stand_first_in_list_order() -> None:
    tasks = [Task("A", 60, "work"), Task("B", 30, "personal")]
    blocks, _ = plan(tasks=tasks)
    first, second = named(blocks, "A"), named(blocks, "B")
    assert (first["kind"], first["start_at"][11:16], first["end_at"][11:16]) == (
        "task",
        "10:00",
        "11:00",
    )
    assert second["start_at"] >= first["end_at"]
    assert (first["category"], second["category"]) == ("work", "personal")
    focus = [b for b in blocks if b["kind"] == "focus"]
    assert focus and all(b["start_at"] >= second["end_at"] for b in focus)


def test_task_longer_than_any_window_is_skipped() -> None:
    busy = [span(MON, "11:00", "12:00"), span(MON, "13:00", "14:00")]
    blocks, skipped = plan_day(
        WEEKDAY, span(MON, "10:00", "14:00"), busy, [Task("Долгая", 120, "work")], None, False
    )
    assert [b for b in blocks if b["kind"] == "task"] == []
    assert any(line.startswith("Долгая") for line in skipped)


def test_task_not_fitting_before_dinner_goes_to_evening_without_focus() -> None:
    busy = [span(MON, "10:00", "19:00")]
    blocks, _ = plan(busy=busy, tasks=[Task("Вечерняя", 60, "work")])
    assert shape(blocks) == [
        ("meal", "19:00", "20:00"),
        ("task", "20:00", "21:00"),
    ]


def test_dinner_keeps_19_when_task_does_not_fit_in_daytime() -> None:
    busy = [span(MON, "10:00", "18:30")]
    blocks, _ = plan(busy=busy, tasks=[Task("Долго", 60, "work")])
    assert named(blocks, "Ужин")["start_at"][11:16] == "19:00"
    assert named(blocks, "Долго")["start_at"][11:16] == "20:00"


def test_breakfast_moves_to_nearest_window_after_meeting() -> None:
    blocks, _ = plan(busy=[span(MON, "11:00", "12:00")])
    breakfast = named(blocks, "Завтрак")
    assert (breakfast["start_at"][11:16], breakfast["end_at"][11:16]) == ("12:00", "13:00")


def test_breakfast_may_start_exactly_two_hours_later() -> None:
    blocks, _ = plan(busy=[span(MON, "11:00", "13:00")])
    assert named(blocks, "Завтрак")["start_at"][11:16] == "13:00"


def test_breakfast_later_than_two_hours_is_skipped() -> None:
    busy = [(at(MON, "11:00"), at(MON, "13:05"))]
    blocks, skipped = plan(busy=busy)
    assert all(b["title"] != "Завтрак" for b in blocks)
    assert any(line.startswith("Завтрак") for line in skipped)


def test_snack_moves_after_meeting_and_rest_follows() -> None:
    blocks, _ = plan(busy=[span(MON, "15:30", "16:00")])
    assert (named(blocks, "Перекус")["start_at"][11:16]) == "16:00"
    rest = named(blocks, "Прогулка / отдых")
    assert (rest["start_at"][11:16], rest["end_at"][11:16]) == ("16:15", "16:45")


def test_snack_skipped_means_no_rest() -> None:
    busy = [(at(MON, "15:30"), at(MON, "17:35"))]
    blocks, skipped = plan(busy=busy)
    assert all(b["kind"] != "rest" for b in blocks)
    assert all(b["title"] != "Перекус" for b in blocks)
    assert any(line.startswith("Перекус") for line in skipped)


def test_snack_fits_window_shorter_than_min_slot() -> None:
    blocks, _ = plan(busy=[span(MON, "15:45", "17:00")])
    snack = named(blocks, "Перекус")
    assert (snack["start_at"][11:16], snack["end_at"][11:16]) == ("15:30", "15:45")


def test_dinner_moves_after_meeting() -> None:
    blocks, _ = plan(busy=[span(MON, "19:00", "20:00")])
    assert named(blocks, "Ужин")["start_at"][11:16] == "20:00"


def test_breakfast_before_window_start_is_skipped_with_reason() -> None:
    blocks, skipped = plan(first="12:00")
    assert "Завтрак 11:00: раньше начала дня" in skipped
    assert all(b["title"] != "Завтрак" for b in blocks)


def test_today_evening_skips_three_meals_with_reason(conn: sqlite3.Connection) -> None:
    result = make(conn, now=datetime(2026, 11, 2, 20, 30))
    early = [s for s in result["skipped"] if "раньше начала дня" in s]
    assert early == [
        "Завтрак 11:00: раньше начала дня",
        "Перекус 15:30: раньше начала дня",
        "Ужин 19:00: раньше начала дня",
    ]
    assert not any(s.startswith("Прогулка") for s in result["skipped"])


def test_day_start_after_breakfast_skips_only_breakfast(conn: sqlite3.Connection) -> None:
    skipped = make(conn, day_start="12:00")["skipped"]
    assert "Завтрак 11:00: раньше начала дня" in skipped
    assert not any(s.startswith("Перекус") for s in skipped)


def test_meal_not_fitting_frame_is_skipped_as_outside() -> None:
    frame = WEEKDAY._replace(dinner=time(23, 30))
    blocks, skipped = plan_day(frame, window(MON), [], [], None, True)
    assert all(b["title"] != "Ужин" for b in blocks)
    assert "Ужин: вне рамки дня" in skipped


def test_meal_blocked_by_busy_is_skipped_as_busy() -> None:
    busy = [(at(MON, "19:00"), at(MON, "21:05"))]
    _, skipped = plan(busy=busy)
    line = next(s for s in skipped if s.startswith("Ужин"))
    assert line.startswith("Ужин: занято")
    assert "вне рамки" not in line


def test_dinner_later_than_two_hours_is_skipped() -> None:
    busy = [(at(MON, "19:00"), at(MON, "21:05"))]
    blocks, skipped = plan(busy=busy)
    assert all(b["title"] != "Ужин" for b in blocks)
    assert any(line.startswith("Ужин") for line in skipped)


def training(day: date, clock: str, minutes: int = 60 + TRAINING_PAD_MIN) -> Training:
    return Training("Бег", at(day, clock), minutes, 7)


def test_training_block_has_workout_id_and_blocks_dinner() -> None:
    blocks, _ = plan(training=training(MON, "18:00"))
    run = named(blocks, "Бег")
    assert (run["kind"], run["start_at"][11:16], run["end_at"][11:16]) == (
        "training",
        "18:00",
        "19:15",
    )
    assert run["workout_id"] == 7
    assert named(blocks, "Ужин")["start_at"][11:16] == "19:15"
    focus = [b for b in blocks if b["kind"] == "focus"]
    assert all(b["end_at"] <= run["start_at"] or b["start_at"] >= run["end_at"] for b in focus)


def test_training_in_the_evening_stays_inside_frame() -> None:
    blocks, skipped = plan(training=training(MON, "21:00"))
    run = named(blocks, "Бег")
    assert run["end_at"] <= at(MON, "24:00").isoformat(timespec="minutes")
    assert skipped == []


def test_training_over_busy_is_skipped_not_moved() -> None:
    blocks, skipped = plan(busy=[span(MON, "18:30", "19:00")], training=training(MON, "18:00"))
    assert all(b["kind"] != "training" for b in blocks)
    assert any("Тренировка" in line for line in skipped)


def test_training_going_past_end_of_day_is_skipped() -> None:
    blocks, skipped = plan(training=training(MON, "23:30"))
    assert all(b["kind"] != "training" for b in blocks)
    assert any("Тренировка" in line for line in skipped)


def test_training_beats_task_for_its_time() -> None:
    busy = [span(MON, "10:00", "18:00")]
    blocks, _ = plan(busy=busy, tasks=[Task("Т", 60, "work")], training=training(MON, "18:00"))
    assert named(blocks, "Бег")["start_at"][11:16] == "18:00"


def test_blocks_never_overlap_and_stay_inside_frame() -> None:
    rng = random.Random(13)
    for _ in range(50):
        busy: list[tuple[datetime, datetime]] = []
        for _ in range(rng.randint(0, 6)):
            start = at(MON, "08:00") + timedelta(minutes=rng.randrange(0, 17 * 12) * 5)
            busy.append((start, start + timedelta(minutes=rng.randrange(1, 30) * 5)))
        tasks = [Task(f"З{n}", rng.choice([30, 60, 90]), "work") for n in range(rng.randint(0, 3))]
        blocks, _ = plan(busy=busy, tasks=tasks)
        spans = [
            (datetime.fromisoformat(b["start_at"]), datetime.fromisoformat(b["end_at"]))
            for b in blocks
        ]
        lo, hi = window(MON)
        for first, last in spans:
            assert lo <= first < last <= hi
            assert all(last <= b0 or first >= b1 for b0, b1 in busy)
        for i, (first, last) in enumerate(spans):
            for other_first, other_last in spans[i + 1 :]:
                assert last <= other_first or first >= other_last


# --- create_day_plan ---


def planned_workout(
    conn: sqlite3.Connection, day: date, secs: int | None = 3600, status: str = "approved"
) -> int:
    spec: dict[str, Any] = {"name": "Бег"}
    if secs is not None:
        spec["estimated_duration_secs"] = secs
    return add_planned_workout(
        conn,
        {
            "date": day.isoformat(),
            "sport": "run",
            "name": "Бег",
            "workout_json": spec,
            "status": status,
        },
    )


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM coach_events").fetchone()[0]


def make(conn: sqlite3.Connection, day: date = MON, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("now", NOW)
    return create_day_plan(conn, day, **kwargs)


def test_creates_drafts_with_kinds_and_categories(conn: sqlite3.Connection) -> None:
    planned_workout(conn, MON)
    result = make(
        conn, tasks=[{"title": "Отчёт", "minutes": 60, "category": "hobby"}], training_at="18:00"
    )
    assert result["date"] == MON.isoformat()
    stored = [get_event(conn, d["draft_id"]) for d in result["drafts"]]
    assert all(row is not None and row["status"] == "draft" for row in stored)
    kinds = {row["kind"] for row in stored if row}
    assert kinds == {"task", "meal", "rest", "focus", "training"}
    for row in stored:
        assert row is not None
        expected = {"task": "hobby", "rest": "rest"}.get(row["kind"])
        assert row["category"] == expected


def test_drafts_match_response_fields(conn: sqlite3.Connection) -> None:
    result = make(conn)
    for draft in result["drafts"]:
        row = get_event(conn, draft["draft_id"])
        assert row is not None
        assert (row["kind"], row["title"], row["category"]) == (
            draft["kind"],
            draft["title"],
            draft["category"],
        )
        assert row["start_at"][:16] == draft["start_at"]
        assert row["end_at"][:16] == draft["end_at"]


def test_response_has_skipped_and_busy(conn: sqlite3.Connection) -> None:
    calendar(conn, MON, meeting(MON, "12:00", "13:00"))
    result = make(conn)
    assert result["busy"] == 1
    assert isinstance(result["skipped"], list)


def test_drafts_do_not_cross_calendar_events(conn: sqlite3.Connection) -> None:
    calendar(conn, MON, meeting(MON, "12:00", "13:30"))
    result = make(conn, tasks=[{"title": "Т", "minutes": 120, "category": "work"}])
    for draft in result["drafts"]:
        assert draft["end_at"] <= f"{MON}T12:00" or draft["start_at"] >= f"{MON}T13:30"


def test_second_call_is_already_planned_and_adds_nothing(conn: sqlite3.Connection) -> None:
    first = make(conn)
    before = count(conn)
    second = make(conn)
    focus_meal = {d["draft_id"] for d in first["drafts"] if d["kind"] in ("focus", "meal")}
    assert set(second["already_planned"]) == focus_meal
    assert "drafts" not in second
    assert count(conn) == before


def test_cancelled_events_do_not_count_as_planned(conn: sqlite3.Connection) -> None:
    first = make(conn)
    conn.execute("UPDATE coach_events SET status = 'cancelled'")
    second = make(conn)
    assert len(second["drafts"]) == len(first["drafts"])


def test_cancelled_workout_is_not_placed(conn: sqlite3.Connection) -> None:
    planned_workout(conn, MON, status="cancelled")
    result = make(conn, training_at="18:00")
    assert all(d["kind"] != "training" for d in result["drafts"])
    assert result["skipped"]


def test_training_without_plan_is_skipped(conn: sqlite3.Connection) -> None:
    result = make(conn, training_at="18:00")
    assert all(d["kind"] != "training" for d in result["drafts"])
    assert result["skipped"]


def test_training_already_in_agenda_is_not_doubled(conn: sqlite3.Connection) -> None:
    wid = planned_workout(conn, MON)
    coach(conn, MON, "08:00", "09:00", kind="training", category=None, workout_id=wid)
    result = make(conn, training_at="18:00")
    assert all(d["kind"] != "training" for d in result["drafts"])
    assert result["skipped"]


def test_training_block_uses_duration_plus_pad(conn: sqlite3.Connection) -> None:
    planned_workout(conn, MON, secs=3600)
    result = make(conn, training_at="18:00")
    run = next(d for d in result["drafts"] if d["kind"] == "training")
    assert (run["start_at"], run["end_at"]) == (f"{MON}T18:00", f"{MON}T19:15")


def test_training_without_duration_is_sixty_plus_pad(conn: sqlite3.Connection) -> None:
    planned_workout(conn, MON, secs=None)
    result = make(conn, training_at="18:00")
    run = next(d for d in result["drafts"] if d["kind"] == "training")
    assert run["end_at"] == f"{MON}T19:15"


def test_task_category_defaults_to_work_on_weekday(conn: sqlite3.Connection) -> None:
    result = make(conn, tasks=[{"title": "Т", "minutes": 30}])
    assert next(d for d in result["drafts"] if d["kind"] == "task")["category"] == "work"


def test_task_category_defaults_to_personal_on_weekend(conn: sqlite3.Connection) -> None:
    result = make(conn, SAT, tasks=[{"title": "Т", "minutes": 30}])
    assert next(d for d in result["drafts"] if d["kind"] == "task")["category"] == "personal"


def test_weekday_frame_starts_with_breakfast_at_11(conn: sqlite3.Connection) -> None:
    drafts = make(conn)["drafts"]
    assert (drafts[0]["title"], drafts[0]["start_at"]) == ("Завтрак", f"{MON}T11:00")


@pytest.mark.parametrize("day", [SAT, SUN])
def test_weekend_frame_has_breakfast_at_12_and_no_focus(
    conn: sqlite3.Connection, day: date
) -> None:
    drafts = make(conn, day)["drafts"]
    assert (drafts[0]["title"], drafts[0]["start_at"]) == ("Завтрак", f"{day}T12:00")
    assert all(d["kind"] != "focus" for d in drafts)


def test_weekend_tasks_start_not_before_11(conn: sqlite3.Connection) -> None:
    drafts = make(conn, SAT, tasks=[{"title": "Т", "minutes": 30}])["drafts"]
    assert min(d["start_at"] for d in drafts) == f"{SAT}T11:00"


def test_day_start_overrides_frame(conn: sqlite3.Connection) -> None:
    drafts = make(conn, day_start="12:00", tasks=[{"title": "Т", "minutes": 30}])["drafts"]
    assert min(d["start_at"] for d in drafts) >= f"{MON}T12:00"


def test_day_end_zero_equals_default(conn: sqlite3.Connection) -> None:
    default = make(conn)["drafts"]
    conn.execute("DELETE FROM coach_events")
    explicit = make(conn, day_end="00:00")["drafts"]
    assert [(d["kind"], d["start_at"], d["end_at"]) for d in explicit] == [
        (d["kind"], d["start_at"], d["end_at"]) for d in default
    ]


def test_day_end_limits_blocks(conn: sqlite3.Connection) -> None:
    drafts = make(conn, day_end="22:00", tasks=[{"title": "Т", "minutes": 30}])["drafts"]
    assert drafts and all(d["end_at"] <= f"{MON}T22:00" for d in drafts)


@pytest.mark.parametrize("start,end", [("12:00", "12:00"), ("12:00", "11:00")])
def test_day_end_not_after_day_start_is_error(
    conn: sqlite3.Connection, start: str, end: str
) -> None:
    with pytest.raises(AgendaError):
        make(conn, day_start=start, day_end=end)
    assert count(conn) == 0


def test_day_start_with_midnight_end_is_ok(conn: sqlite3.Connection) -> None:
    assert make(conn, day_start="12:00", day_end="00:00")["drafts"]


@pytest.mark.parametrize(
    "name", ["day_start", "day_end", "training_at", "breakfast_at", "snack_at", "dinner_at"]
)
@pytest.mark.parametrize("value", ["9:00", "20", "25:00", "ab:cd", "10:00:00"])
def test_bad_clock_is_error(conn: sqlite3.Connection, name: str, value: str) -> None:
    with pytest.raises(AgendaError):
        make(conn, MON, **{name: value})
    assert count(conn) == 0


def test_meal_times_can_be_overridden(conn: sqlite3.Connection) -> None:
    drafts = make(conn, breakfast_at="12:00", snack_at="16:00", dinner_at="20:00")["drafts"]
    by_title = {d["title"]: d for d in drafts}
    assert (by_title["Ужин"]["start_at"], by_title["Ужин"]["end_at"]) == (
        f"{MON}T20:00",
        f"{MON}T21:00",
    )
    assert (by_title["Перекус"]["start_at"], by_title["Перекус"]["end_at"]) == (
        f"{MON}T16:00",
        f"{MON}T16:15",
    )
    assert by_title["Завтрак"]["start_at"] == f"{MON}T12:00"


def test_today_blocks_start_not_before_now_rounded_up(conn: sqlite3.Connection) -> None:
    now = datetime(2026, 11, 2, 12, 7)
    drafts = make(conn, MON, now=now, tasks=[{"title": "Т", "minutes": 30}])["drafts"]
    assert drafts and min(d["start_at"] for d in drafts) >= f"{MON}T12:10"
    assert all(d["title"] != "Завтрак" for d in drafts)


def test_today_evening_has_only_tasks_and_training(conn: sqlite3.Connection) -> None:
    planned_workout(conn, MON)
    now = datetime(2026, 11, 2, 20, 30)
    result = make(
        conn,
        now=now,
        tasks=[{"title": "Т", "minutes": 30, "category": "work"}],
        training_at="21:00",
    )
    assert {d["kind"] for d in result["drafts"]} == {"task", "training"}
    assert min(d["start_at"] for d in result["drafts"]) >= f"{MON}T20:30"


def test_block_ending_at_midnight_is_stored_and_visible(conn: sqlite3.Connection) -> None:
    planned_workout(conn, MON)
    result = make(conn, training_at="22:45")
    run = next(d for d in result["drafts"] if d["kind"] == "training")
    assert run["end_at"] == f"{MON + timedelta(days=1)}T00:00"
    row = get_event(conn, run["draft_id"])
    assert row is not None and row["date"] == MON.isoformat()
    assert run["draft_id"] in [e["id"] for e in agenda_rows(conn, MON.isoformat(), MON.isoformat())]


def test_past_date_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(AgendaError):
        make(conn, date(2026, 10, 31))
    assert count(conn) == 0


def test_today_is_allowed_and_15_days_ahead_is_error(conn: sqlite3.Connection) -> None:
    make(conn, NOW.date())
    with pytest.raises(AgendaError):
        make(conn, NOW.date() + timedelta(days=15))


def test_14_days_ahead_is_allowed(conn: sqlite3.Connection) -> None:
    assert make(conn, NOW.date() + timedelta(days=14))["drafts"]


@pytest.mark.parametrize(
    "task",
    [
        {"title": "Т", "minutes": 0},
        {"title": "Т", "minutes": -5},
        {"title": "Т", "minutes": "30"},
        {"title": "Т"},
        {"minutes": 30},
        {"title": "  ", "minutes": 30},
    ],
)
def test_bad_task_is_error(conn: sqlite3.Connection, task: dict[str, Any]) -> None:
    with pytest.raises(AgendaError):
        make(conn, tasks=[task])
    assert count(conn) == 0


def test_broken_block_leaves_no_drafts(conn: sqlite3.Connection) -> None:
    tasks = [
        {"title": "А", "minutes": 30, "category": "work"},
        {"title": "Б", "minutes": 30, "category": "work"},
        {"title": "В", "minutes": 30, "category": "ignore"},
    ]
    with pytest.raises(AgendaError):
        make(conn, tasks=tasks)
    assert count(conn) == 0


def test_evening_repeat_does_not_double_tasks(conn: sqlite3.Connection) -> None:
    now = datetime(2026, 11, 2, 20, 30)
    tasks = [{"title": "Отчёт", "minutes": 60, "category": "work"}]
    first = make(conn, now=now, tasks=tasks)
    assert len(first["drafts"]) == 1
    before = count(conn)
    again = make(conn, now=now, tasks=[{"title": "  отчёт ", "minutes": 60, "category": "work"}])
    assert again["drafts"] == []
    assert any("уже стоит" in line for line in again["skipped"])
    assert count(conn) == before


def test_evening_repeat_places_task_with_other_title(conn: sqlite3.Connection) -> None:
    now = datetime(2026, 11, 2, 20, 30)
    make(conn, now=now, tasks=[{"title": "Отчёт", "minutes": 60, "category": "work"}])
    again = make(conn, now=now, tasks=[{"title": "Письмо", "minutes": 30, "category": "work"}])
    assert [d["title"] for d in again["drafts"]] == ["Письмо"]
    assert not any("уже стоит" in s for s in again["skipped"])
    assert all("раньше начала дня" in line for line in again["skipped"])


def test_task_standing_from_morning_is_not_doubled(conn: sqlite3.Connection) -> None:
    coach(conn, MON, "09:00", "10:00", kind="task", title="Отчёт", category="work")
    result = make(conn, tasks=[{"title": "Отчёт", "minutes": 60, "category": "work"}])
    assert all(d["kind"] != "task" for d in result["drafts"])
    assert any("уже стоит" in line for line in result["skipped"])


def test_frames_match_numbers_from_user() -> None:
    assert (WEEKDAY.start.hour, WEEKDAY.breakfast.hour, WEEKDAY.dinner.hour) == (10, 11, 19)
    assert (WEEKEND.start.hour, WEEKEND.breakfast.hour, WEEKEND.dinner.hour) == (11, 12, 19)
    assert (WEEKDAY.snack.hour, WEEKDAY.snack.minute) == (15, 30)
    assert (WEEKEND.snack.hour, WEEKEND.snack.minute) == (16, 0)
