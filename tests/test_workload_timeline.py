"""ai_coach.workload.timeline: переключения и длинные отрезки по ленте окон (шаг Н8).

Лента - список (начало, конец, класс); данные выдуманные.
"""

from datetime import datetime, timedelta

from ai_coach.workload.timeline import longest_stretch, switch_rate

Segment = tuple[datetime, datetime, str]

DAY = datetime(2026, 10, 7, 9, 0).astimezone()


def seg(start: str, end: str, cls: str) -> Segment:
    """Отрезок по часам 'ЧЧ:ММ' (или 'ЧЧ:ММ:СС') выдуманного дня."""

    def moment(text: str) -> datetime:
        parts = [int(x) for x in text.split(":")]
        return DAY.replace(hour=parts[0], minute=parts[1], second=parts[2] if len(parts) > 2 else 0)

    return (moment(start), moment(end), cls)


def run(start: datetime, seconds: float, cls: str) -> Segment:
    return (start, start + timedelta(seconds=seconds), cls)


# --- switch_rate ---


def test_switch_rate_two_transitions_in_two_hours() -> None:
    segments = [
        seg("09:00", "09:40", "challenge"),
        seg("09:40", "10:20", "hindrance"),
        seg("10:20", "11:00", "challenge"),
    ]
    assert switch_rate(segments) == 1.0


def test_switch_rate_one_class_has_no_transitions() -> None:
    segments = [seg("09:00", "10:00", "work"), seg("10:00", "11:00", "work")]
    assert switch_rate(segments) == 0.0


def test_switch_rate_short_segment_between_same_class_gives_no_transition() -> None:
    segments = [
        run(DAY, 3600, "challenge"),
        run(DAY + timedelta(seconds=3600), 4, "hindrance"),
        run(DAY + timedelta(seconds=3604), 3600, "challenge"),
    ]
    assert switch_rate(segments) == 0.0


def test_switch_rate_five_second_segment_counts_as_transition() -> None:
    segments = [
        run(DAY, 3600, "challenge"),
        run(DAY + timedelta(seconds=3600), 5, "hindrance"),
        run(DAY + timedelta(seconds=3605), 3600, "challenge"),
    ]
    assert switch_rate(segments) == 1.0


def test_switch_rate_short_segments_count_in_active_hours() -> None:
    """55 минут длинного отрезка + 100 коротких по 4 с = больше часа активного экрана."""
    segments = [run(DAY, 3300, "challenge")]
    start = DAY + timedelta(seconds=3300)
    for n in range(100):
        segments.append(run(start + timedelta(seconds=4 * n), 4, "hindrance"))
    assert switch_rate(segments) == 0.0


def test_switch_rate_under_minimum_active_hours_is_none() -> None:
    segments = [
        run(DAY, 1944, "challenge"),
        run(DAY + timedelta(seconds=1944), 1296, "hindrance"),
    ]
    assert switch_rate(segments) is None


def test_switch_rate_exactly_one_hour_is_a_number() -> None:
    segments = [seg("09:00", "09:30", "challenge"), seg("09:30", "10:00", "hindrance")]
    assert switch_rate(segments) == 1.0


def test_switch_rate_empty_is_none() -> None:
    assert switch_rate([]) is None


def test_switch_rate_is_rounded_to_one_decimal() -> None:
    segments = [seg("09:00", "09:45", "challenge"), seg("09:45", "10:30", "hindrance")]
    assert switch_rate(segments) == 0.7


def test_switch_rate_counts_every_pair_of_different_classes() -> None:
    segments = [
        seg("09:00", "09:45", "work"),
        seg("09:45", "10:30", "hobby"),
        seg("10:30", "11:15", "browser"),
        seg("11:15", "12:00", "unmarked"),
    ]
    assert switch_rate(segments) == 1.0


# --- longest_stretch ---


def test_stretch_pause_of_three_minutes_does_not_break() -> None:
    segments = [seg("09:00", "10:00", "work"), seg("10:03", "11:00", "work")]
    assert longest_stretch(segments) == 2.0


def test_stretch_pause_of_exactly_five_minutes_breaks() -> None:
    segments = [seg("09:00", "10:00", "work"), seg("10:05", "11:00", "work")]
    assert longest_stretch(segments) == 1.0


def test_stretch_six_minutes_of_hobby_breaks() -> None:
    segments = [
        seg("09:00", "10:00", "work"),
        seg("10:00", "10:06", "hobby"),
        seg("10:06", "11:00", "work"),
    ]
    assert longest_stretch(segments) == 1.0


def test_stretch_two_minutes_of_hobby_does_not_break() -> None:
    segments = [
        seg("09:00", "10:00", "work"),
        seg("10:00", "10:02", "hobby"),
        seg("10:02", "11:00", "work"),
    ]
    assert longest_stretch(segments) == 2.0


def test_stretch_challenge_and_hindrance_are_work_and_do_not_break() -> None:
    segments = [
        seg("09:00", "10:00", "work"),
        seg("10:00", "10:30", "challenge"),
        seg("10:30", "11:00", "hindrance"),
    ]
    assert longest_stretch(segments) == 2.0


def test_stretch_without_work_is_zero() -> None:
    assert longest_stretch([seg("09:00", "10:00", "hobby")]) == 0
    assert longest_stretch([seg("09:00", "10:00", "browser")]) == 0
    assert longest_stretch([seg("09:00", "10:00", "unmarked")]) == 0
    assert longest_stretch([]) == 0


def test_stretch_takes_the_longest_of_several() -> None:
    segments = [
        seg("09:00", "09:30", "work"),
        seg("10:00", "12:00", "work"),
        seg("13:00", "13:45", "work"),
    ]
    assert longest_stretch(segments) == 2.0


def test_stretch_is_rounded_to_two_decimals() -> None:
    assert longest_stretch([seg("09:00", "09:20", "work")]) == 0.33
