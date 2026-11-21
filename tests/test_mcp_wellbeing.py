import sqlite3
from datetime import date, timedelta

from mcp_fakes import call, rows, tool_names

DAY = "2026-10-07"


def feel(conn: sqlite3.Connection, day: str, score: int, text: str | None, at: str) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, text, logged_at) VALUES (?, ?, ?, ?)",
        (day, score, text, at),
    )


def metrics(conn: sqlite3.Connection, day: str, **values: object) -> None:
    names = ["date", "raw_json", *values]
    marks = ", ".join("?" for _ in names)
    conn.execute(
        f"INSERT INTO daily_metrics ({', '.join(names)}) VALUES ({marks})",
        (day, "{}", *values.values()),
    )


def kinds(conn: sqlite3.Connection, day: str = DAY) -> list[str]:
    return [r["kind"] for r in rows(conn, "get_deviations", date=day)]


def test_tools_exist(conn: sqlite3.Connection) -> None:
    assert {"get_wellbeing", "get_deviations"} <= tool_names(conn)


def test_wellbeing_has_rows_and_truncated(conn: sqlite3.Connection) -> None:
    answer = call(conn, "get_wellbeing", start=DAY, end=DAY)
    assert answer == {"rows": [], "truncated": False}


def test_wellbeing_returns_entries_of_period_inclusive(conn: sqlite3.Connection) -> None:
    feel(conn, "2026-10-05", 5, None, "2026-10-05 08:00:00")
    feel(conn, "2026-10-06", 3, "устал", "2026-10-06 08:00:00")
    feel(conn, DAY, 4, None, f"{DAY} 08:00:00")
    feel(conn, "2026-10-08", 1, None, "2026-10-08 08:00:00")
    found = rows(conn, "get_wellbeing", start="2026-10-06", end=DAY)
    assert [(r["date"], r["score"], r["text"]) for r in found] == [
        ("2026-10-06", 3, "устал"),
        (DAY, 4, None),
    ]


def test_wellbeing_keeps_all_entries_of_a_day_in_time_order(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, 2, "вечером хуже", f"{DAY} 20:00:00")
    feel(conn, DAY, 4, "утром хорошо", f"{DAY} 08:00:00")
    found = rows(conn, "get_wellbeing", start=DAY, end=DAY)
    assert [r["score"] for r in found] == [4, 2]


def test_wellbeing_rows_are_limited_and_truncated_flag_set(conn: sqlite3.Connection) -> None:
    for number in range(70):
        feel(conn, DAY, 3, None, f"{DAY} 08:{number // 60:02d}:{number % 60:02d}")
    answer = call(conn, "get_wellbeing", start=DAY, end=DAY)
    assert len(answer["rows"]) == 60
    assert answer["truncated"] is True


def test_deviations_have_rows_and_truncated(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_deviations", date=DAY)
    assert (result["rows"], result["truncated"]) == ([], False)


def test_deviations_without_load_say_atl_ctl_not_checked(conn: sqlite3.Connection) -> None:
    assert "coach sync" in call(conn, "get_deviations", date=DAY)["load_error"]


def test_no_data_means_no_deviations(conn: sqlite3.Connection) -> None:
    assert kinds(conn) == []


def test_low_wellbeing_is_a_deviation(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, 2, None, f"{DAY} 08:00:00")
    assert kinds(conn) == ["wellbeing"]


def test_main_wellbeing_of_the_day_is_the_last_one(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, 1, None, f"{DAY} 08:00:00")
    feel(conn, DAY, 4, "отпустило", f"{DAY} 18:00:00")
    assert kinds(conn) == []


def test_last_wellbeing_bad_after_good_one_is_a_deviation(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, 5, None, f"{DAY} 08:00:00")
    feel(conn, DAY, 2, "плохо", f"{DAY} 18:00:00")
    assert kinds(conn) == ["wellbeing"]


def test_wellbeing_of_another_day_is_ignored(conn: sqlite3.Connection) -> None:
    feel(conn, "2026-10-06", 1, None, "2026-10-06 08:00:00")
    assert kinds(conn) == []


def test_low_readiness_is_a_deviation(conn: sqlite3.Connection) -> None:
    metrics(conn, DAY, readiness_score=32)
    assert kinds(conn) == ["readiness"]


def test_readiness_33_is_fine(conn: sqlite3.Connection) -> None:
    metrics(conn, DAY, readiness_score=33)
    assert kinds(conn) == []


def test_bad_hrv_status_is_a_deviation(conn: sqlite3.Connection) -> None:
    metrics(conn, DAY, hrv_status="UNBALANCED")
    assert kinds(conn) == ["hrv"]


def test_short_sleep_is_a_deviation(conn: sqlite3.Connection) -> None:
    metrics(conn, DAY, sleep_seconds=5 * 3600)
    assert kinds(conn) == ["sleep"]


def test_six_hours_of_sleep_is_fine(conn: sqlite3.Connection) -> None:
    metrics(conn, DAY, sleep_seconds=6 * 3600)
    assert kinds(conn) == []


def test_several_deviations_in_one_answer(conn: sqlite3.Connection) -> None:
    metrics(conn, DAY, readiness_score=10, sleep_seconds=4 * 3600, hrv_status="LOW")
    feel(conn, DAY, 1, None, f"{DAY} 08:00:00")
    assert sorted(kinds(conn)) == ["hrv", "readiness", "sleep", "wellbeing"]


def test_snapshot_has_wellbeing_section(conn: sqlite3.Connection) -> None:
    feel(conn, DAY, 4, "бодро", f"{DAY} 08:00:00")
    section = call(conn, "get_morning_snapshot", date=DAY)["wellbeing"]
    assert [(r["score"], r["text"]) for r in section["rows"]] == [(4, "бодро")]
    assert section["truncated"] is False


def test_snapshot_wellbeing_rows_are_projected(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log"
        " (date, score, text, logged_at, mood, stress, work_thoughts, event_id)"
        " VALUES (?, 4, 'бодро', ?, 3, 2, 5, 7)",
        (DAY, f"{DAY} 08:00:00"),
    )
    row = call(conn, "get_morning_snapshot", date=DAY)["wellbeing"]["rows"][0]
    assert list(row) == [
        "date",
        "logged_at",
        "score",
        "mood",
        "stress",
        "fatigue",
        "irritability",
        "text",
    ]
    assert (row["mood"], row["stress"]) == (3, 2)


def test_get_wellbeing_keeps_all_columns(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, logged_at, work_thoughts, event_id)"
        " VALUES (?, 4, ?, 5, 7)",
        (DAY, f"{DAY} 08:00:00"),
    )
    row = rows(conn, "get_wellbeing", start=DAY, end=DAY)[0]
    assert (row["work_thoughts"], row["event_id"]) == (5, 7)


def test_get_wellbeing_gives_fatigue_and_irritability(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, logged_at, fatigue, irritability)"
        " VALUES (?, 4, ?, 4, 2)",
        (DAY, f"{DAY} 20:00:00"),
    )
    feel(conn, DAY, 3, None, f"{DAY} 21:00:00")
    first, second = rows(conn, "get_wellbeing", start=DAY, end=DAY)
    assert (first["fatigue"], first["irritability"]) == (4, 2)
    assert (second["fatigue"], second["irritability"]) == (None, None)


def test_snapshot_wellbeing_rows_have_fatigue_and_irritability(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, logged_at, fatigue, irritability)"
        " VALUES (?, 4, ?, 4, 2)",
        (DAY, f"{DAY} 20:00:00"),
    )
    feel(conn, DAY, 3, None, f"{DAY} 21:00:00")
    first, second = call(conn, "get_morning_snapshot", date=DAY)["wellbeing"]["rows"]
    assert (first["fatigue"], first["irritability"]) == (4, 2)
    assert (second["fatigue"], second["irritability"]) == (None, None)


def test_snapshot_wellbeing_has_history_not_only_today(conn: sqlite3.Connection) -> None:
    feel(conn, "2026-10-03", 3, None, "2026-10-03 08:00:00")
    feel(conn, DAY, 4, None, f"{DAY} 08:00:00")
    section = call(conn, "get_morning_snapshot", date=DAY)["wellbeing"]
    assert [r["date"] for r in section["rows"]] == ["2026-10-03", DAY]


def test_snapshot_has_deviations_section(conn: sqlite3.Connection) -> None:
    metrics(conn, DAY, readiness_score=20)
    section = call(conn, "get_morning_snapshot", date=DAY)["deviations"]
    assert [r["kind"] for r in section["rows"]] == ["readiness"]
    assert section["truncated"] is False


def test_symptom_in_morning_text_survives_evening_entry_without_text(
    conn: sqlite3.Connection,
) -> None:
    feel(conn, DAY, 3, "горло болит", f"{DAY} 08:00:00")
    feel(conn, DAY, 4, None, f"{DAY} 20:00:00")
    found = rows(conn, "get_deviations", date=DAY)
    assert [(r["kind"], r["value"], r["limit"]) for r in found] == [("symptoms", ["горло"], None)]


def test_symptom_of_yesterday_is_not_today(conn: sqlite3.Connection) -> None:
    feel(conn, "2026-10-06", 3, "горло", "2026-10-06 08:00:00")
    feel(conn, DAY, 4, "бодро", f"{DAY} 08:00:00")
    assert kinds(conn) == []


def test_symptom_in_pult_mark_with_event_id_counts(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, text, logged_at, event_id)"
        " VALUES (?, 4, 'насморк', ?, 7)",
        (DAY, f"{DAY} 08:00:00"),
    )
    assert kinds(conn) == ["symptoms"]


def past(conn: sqlite3.Connection, scores: list[int], first_back: int = 1) -> None:
    """По записи на день, начиная с first_back дней до DAY и дальше в прошлое."""
    for offset, score in enumerate(scores):
        day = (date.fromisoformat(DAY) - timedelta(days=first_back + offset)).isoformat()
        feel(conn, day, score, None, f"{day} 08:00:00")


def below_rows(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    found = rows(conn, "get_deviations", date=DAY)
    return [(r["kind"], r["value"], r["limit"]) for r in found if r["kind"].endswith("_below")]


def test_seven_days_at_4_and_today_3_is_wellbeing_below(conn: sqlite3.Connection) -> None:
    past(conn, [4] * 7)
    feel(conn, DAY, 3, None, f"{DAY} 08:00:00")
    assert below_rows(conn) == [("wellbeing_below", 3, 4)]


def test_six_days_of_history_is_not_enough(conn: sqlite3.Connection) -> None:
    past(conn, [4] * 6)
    feel(conn, DAY, 3, None, f"{DAY} 08:00:00")
    assert kinds(conn) == []


def test_history_all_at_3_and_today_3_is_fine(conn: sqlite3.Connection) -> None:
    past(conn, [3] * 14)
    feel(conn, DAY, 3, None, f"{DAY} 08:00:00")
    assert kinds(conn) == []


def test_below_yesterday_without_entry_today_is_empty(conn: sqlite3.Connection) -> None:
    past(conn, [3] + [4] * 7)
    assert kinds(conn) == []


def test_today_is_not_part_of_the_norm(conn: sqlite3.Connection) -> None:
    past(conn, [4] * 4 + [3] * 3)
    feel(conn, DAY, 3, None, f"{DAY} 08:00:00")
    assert below_rows(conn) == [("wellbeing_below", 3, 4)]


def test_days_older_than_14_are_not_in_the_norm(conn: sqlite3.Connection) -> None:
    past(conn, [5] * 7, first_back=15)
    past(conn, [3] * 7)
    feel(conn, DAY, 3, None, f"{DAY} 08:00:00")
    assert kinds(conn) == []


def test_day_14_back_is_in_the_norm(conn: sqlite3.Connection) -> None:
    past(conn, [4] * 7, first_back=8)
    feel(conn, DAY, 3, None, f"{DAY} 08:00:00")
    assert below_rows(conn) == [("wellbeing_below", 3, 4)]


def test_mood_below_norm_from_history(conn: sqlite3.Connection) -> None:
    for back in range(1, 8):
        day = (date.fromisoformat(DAY) - timedelta(days=back)).isoformat()
        conn.execute(
            "INSERT INTO wellbeing_log (date, score, mood, logged_at) VALUES (?, 4, 4, ?)",
            (day, f"{day} 08:00:00"),
        )
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, mood, logged_at) VALUES (?, 4, 3, ?)",
        (DAY, f"{DAY} 08:00:00"),
    )
    assert kinds(conn) == ["mood_below"]


def test_below_norm_and_symptom_in_one_day_give_both_rows(conn: sqlite3.Connection) -> None:
    past(conn, [4] * 7)
    feel(conn, DAY, 3, "горло", f"{DAY} 08:00:00")
    assert kinds(conn) == ["wellbeing_below", "symptoms"]


def test_snapshot_deviations_include_below_norm(conn: sqlite3.Connection) -> None:
    past(conn, [4] * 7)
    feel(conn, DAY, 3, None, f"{DAY} 08:00:00")
    section = call(conn, "get_morning_snapshot", date=DAY)["deviations"]
    assert [r["kind"] for r in section["rows"]] == ["wellbeing_below"]


# Н33, партия 1: ответы форм дня идут в разбор симптомов.


def put_form_answers(
    conn: sqlite3.Connection, answers: dict[str, object], archived: bool = False
) -> None:
    import json

    from workload_fakes import coach_event

    from ai_coach.store.agenda import add_event
    from ai_coach.store.forms import add_form, add_form_entry, archive_form

    fields = [
        {"key": "temperature", "type": "number", "label": "Температура", "unit": "°C"},
        {"key": "nose", "type": "yesno", "label": "Насморк"},
    ]
    add_form(
        conn,
        {
            "name": "sick",
            "title": "Болезнь",
            "fields_json": json.dumps(fields, ensure_ascii=False),
            "created_at": f"{DAY} 07:00:00",
        },
    )
    event_id = add_event(conn, coach_event(survey="form:sick"))
    add_form_entry(
        conn,
        {
            "date": DAY,
            "time": "09:00:00",
            "event_id": event_id,
            "form": "sick",
            "values_json": json.dumps(answers),
            "text": None,
        },
    )
    if archived:
        archive_form(conn, "sick", f"{DAY} 12:00:00")


def put_answer(
    conn: sqlite3.Connection,
    answers: dict[str, object],
    clock: str,
    text: str | None = None,
    wellbeing_id: int | None = None,
) -> None:
    import json

    from workload_fakes import coach_event

    from ai_coach.store.agenda import add_event
    from ai_coach.store.forms import add_form_entry

    event_id = add_event(conn, coach_event(survey="form:sick"))
    add_form_entry(
        conn,
        {
            "date": DAY,
            "time": clock,
            "event_id": event_id,
            "form": "sick",
            "values_json": json.dumps(answers),
            "text": text,
            "wellbeing_id": wellbeing_id,
        },
    )


def test_answer_with_wellbeing_entry_without_text_gives_symptoms_once(
    conn: sqlite3.Connection,
) -> None:
    put_form_answers(conn, {"temperature": 36.6, "nose": False})
    feel(conn, DAY, 4, None, f"{DAY} 09:00:00")
    wellbeing_id = conn.execute("SELECT max(id) FROM wellbeing_log").fetchone()[0]
    put_answer(conn, {"temperature": 36.6, "nose": True}, "10:00:00", wellbeing_id=wellbeing_id)
    found = rows(conn, "get_deviations", date=DAY)
    assert [r["kind"] for r in found] == ["symptoms"]
    assert found[0]["value"] == ["насморк"]


def test_three_answers_of_the_day_give_the_largest_fever(conn: sqlite3.Connection) -> None:
    put_form_answers(conn, {"temperature": 37.2, "nose": False})
    put_answer(conn, {"temperature": 37.9, "nose": False}, "13:00:00")
    put_answer(conn, {"temperature": 37.4, "nose": False}, "20:00:00")
    found = rows(conn, "get_deviations", date=DAY)
    assert {"kind": "fever", "value": 37.9, "limit": 37.0} in found


def test_own_text_of_answer_without_wellbeing_id_is_read(conn: sqlite3.Connection) -> None:
    put_form_answers(conn, {"temperature": 36.6, "nose": False})
    put_answer(conn, {"temperature": 36.6, "nose": False}, "11:00:00", text="першит горло")
    found = rows(conn, "get_deviations", date=DAY)
    assert found[0]["kind"] == "symptoms"
    assert found[0]["value"] == ["горло", "першение"]


def test_form_answers_without_text_give_symptoms(conn: sqlite3.Connection) -> None:
    put_form_answers(conn, {"temperature": 36.6, "nose": True})
    assert kinds(conn) == ["symptoms"]
    assert rows(conn, "get_deviations", date=DAY)[0]["value"] == ["насморк"]


def test_form_temperature_gives_fever_row(conn: sqlite3.Connection) -> None:
    put_form_answers(conn, {"temperature": 37.2, "nose": False})
    found = rows(conn, "get_deviations", date=DAY)
    assert {"kind": "fever", "value": 37.2, "limit": 37.0} in found


def test_answers_of_archived_form_are_read(conn: sqlite3.Connection) -> None:
    put_form_answers(conn, {"temperature": 36.6, "nose": True}, archived=True)
    assert kinds(conn) == ["symptoms"]


def test_form_answers_of_another_day_are_ignored(conn: sqlite3.Connection) -> None:
    put_form_answers(conn, {"temperature": 36.6, "nose": True})
    assert kinds(conn, "2026-10-08") == []


def test_snapshot_without_data_has_empty_sections(conn: sqlite3.Connection) -> None:
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert snapshot["wellbeing"] == {"rows": [], "truncated": False}
    assert snapshot["deviations"] == {"rows": [], "truncated": False}
