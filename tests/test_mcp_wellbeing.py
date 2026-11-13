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
    assert list(row) == ["date", "logged_at", "score", "mood", "stress", "text"]
    assert (row["mood"], row["stress"]) == (3, 2)


def test_get_wellbeing_keeps_all_columns(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO wellbeing_log (date, score, logged_at, work_thoughts, event_id)"
        " VALUES (?, 4, ?, 5, 7)",
        (DAY, f"{DAY} 08:00:00"),
    )
    row = rows(conn, "get_wellbeing", start=DAY, end=DAY)[0]
    assert (row["work_thoughts"], row["event_id"]) == (5, 7)


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


def test_snapshot_without_data_has_empty_sections(conn: sqlite3.Connection) -> None:
    snapshot = call(conn, "get_morning_snapshot", date=DAY)
    assert snapshot["wellbeing"] == {"rows": [], "truncated": False}
    assert snapshot["deviations"] == {"rows": [], "truncated": False}
