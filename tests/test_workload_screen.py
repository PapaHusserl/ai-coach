"""ai_coach.workload.screen: экранное время из ActivityWatch (шаг v2.8).

Сеть не нужна: читатель подменён FakeAw, а AwReader гоняется через подмену urlopen. Названия
приложений и заголовки окон - выдуманные.
"""

import io
import json
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest
from workload_fakes import FakeAw, write_config

from ai_coach.workload.config import ScreenConfig, load_config
from ai_coach.workload.screen import (
    QUERY_HEAD,
    AwReader,
    ScreenError,
    by_category,
    classify,
    read_screen,
    screen_query,
)

D1 = date(2026, 10, 7)
D2 = date(2026, 10, 8)
HOUR = 3600
SECRET_TITLE = "СЕКРЕТНЫЙ_ЗАГОЛОВОК_ОКНА"

CONFIG = ScreenConfig(
    work=frozenset({"alpha editor"}),
    hobby=frozenset({"betagame"}),
    browser=frozenset({"gamma browser"}),
    meeting=frozenset({"deltacall"}),
    meeting_names=("DeltaCall",),
)


def at(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(hour)).astimezone()


def screen_of(tmp_path: Path, text: str) -> ScreenConfig:
    screen = load_config(write_config(tmp_path / "s.toml", text)).screen
    assert screen is not None
    return screen


def rows_of(rows: list[dict[str, Any]], day: date) -> dict[str, Any]:
    return {r["kind"]: r["value"] for r in rows if r["date"] == day.isoformat()}


# --- screen_query ---


def test_query_without_title_and_meeting_is_head_plus_merge() -> None:
    assert screen_query(ScreenConfig()) == [
        *QUERY_HEAD,
        'events = merge_events_by_keys(events, ["app"]);',
        "RETURN = sort_by_duration(events);",
    ]


def test_query_head_intersects_windows_with_not_afk() -> None:
    joined = "\n".join(QUERY_HEAD)
    assert '"not-afk"' in joined
    assert "filter_period_intersect(window, afk)" in joined


def test_query_with_meeting_unites_not_afk_with_meeting_windows() -> None:
    query = screen_query(CONFIG)
    assert 'meet = filter_keyvals(window, "app", ["DeltaCall"]);' in query
    assert "active = period_union(afk, meet);" in query
    assert "events = filter_period_intersect(window, active);" in query
    assert "events = filter_period_intersect(window, afk);" not in query


def test_query_meeting_name_keeps_mixed_case(tmp_path: Path) -> None:
    """filter_keyvals на сервере сравнивает точно: имя уходит как в toml, не в нижнем регистре."""
    screen = screen_of(tmp_path, '[screen]\nmeeting = ["DeltaCall"]\n')
    query = "\n".join(screen_query(screen))
    assert '["DeltaCall"]' in query
    assert "deltacall" not in query


def test_query_non_ascii_app_names_go_as_is_without_unicode_escapes(tmp_path: Path) -> None:
    text = (
        '[screen]\nmeeting = ["Звонок-Альфа"]\n[screen.title."Редактор-Бета"]\nwork = ["проект"]\n'
    )
    joined = "\n".join(screen_query(screen_of(tmp_path, text)))
    assert '["Звонок-Альфа"]' in joined
    assert '["Редактор-Бета"]' in joined
    assert "\\u" not in joined


def test_query_without_meeting_has_no_period_union() -> None:
    assert "period_union" not in "\n".join(screen_query(ScreenConfig(work=frozenset({"a"}))))


def test_query_title_app_is_categorized_and_excluded_from_rest(tmp_path: Path) -> None:
    text = '[screen.title.alphaedit]\nwork = ["proj-a", "proj-b"]\nhobby = ["fun"]\n'
    query = screen_query(screen_of(tmp_path, text))
    joined = "\n".join(query)
    assert 'rest = exclude_keyvals(events, "app", ["alphaedit"]);' in query
    assert 'filter_keyvals(events, "app", ["alphaedit"])' in joined
    assert "categorize(t0, " in joined
    assert "(?i)(?:proj-a|proj-b)" in joined
    assert "(?i)(?:fun)" in joined
    assert 'merge_events_by_keys(t0, ["app", "$category"])' in joined
    assert query[-1] == "RETURN = sort_by_duration(res);"


def test_query_hobby_class_goes_after_work_class(tmp_path: Path) -> None:
    """При равных классах побеждает последний: hobby должен идти после work."""
    text = '[screen.title.alphaedit]\nhobby = ["fun"]\nwork = ["proj"]\n'
    line = next(x for x in screen_query(screen_of(tmp_path, text)) if "categorize(" in x)
    assert line.index('"work"') < line.index('"hobby"')


def test_query_single_backslash_reaches_the_server(tmp_path: Path) -> None:
    """В toml `\\w` - один обратный слэш: в запросе query2 он должен остаться одним."""
    text = '[screen.title.alphaedit]\nwork = ["\\\\w+x"]\n'
    joined = "\n".join(screen_query(screen_of(tmp_path, text)))
    assert "(?i)(?:\\w+x)" in joined
    assert "\\\\w" not in joined


def test_query_literal_regex_in_toml_single_quotes_gets_one_backslash(tmp_path: Path) -> None:
    text = "[screen.title.alphaedit]\nwork = ['\\w+x']\n"
    assert "(?i)(?:\\w+x)" in "\n".join(screen_query(screen_of(tmp_path, text)))


def test_query_two_title_apps_get_two_categorize_blocks(tmp_path: Path) -> None:
    text = '[screen.title.alphaedit]\nwork = ["a"]\n[screen.title.betaedit]\nhobby = ["b"]\n'
    query = screen_query(screen_of(tmp_path, text))
    assert sum("categorize(" in x for x in query) == 2
    assert 'rest = exclude_keyvals(events, "app", ["alphaedit", "betaedit"]);' in query
    assert "res = concat(res, t0);" in query
    assert "res = concat(res, t1);" in query


def test_query_title_and_meeting_combine(tmp_path: Path) -> None:
    text = '[screen]\nmeeting = ["DeltaCall"]\n[screen.title.alphaedit]\nwork = ["a"]\n'
    joined = "\n".join(screen_query(screen_of(tmp_path, text)))
    assert "period_union" in joined
    assert "categorize(" in joined


# --- classify / by_category ---


def test_classify_known_classes_and_unmarked() -> None:
    assert classify("alpha editor", CONFIG) == "work"
    assert classify("betagame", CONFIG) == "hobby"
    assert classify("gamma browser", CONFIG) == "browser"
    assert classify("zeta tool", CONFIG) == "unmarked"


def test_classify_ignores_case_of_app_name() -> None:
    assert classify("Alpha Editor", CONFIG) == "work"
    assert classify("BETAGAME", CONFIG) == "hobby"


def test_classify_meeting_app_without_other_class_is_work() -> None:
    assert classify("deltacall", CONFIG) == "work"
    assert classify("DeltaCall", CONFIG) == "work"


def test_classify_meeting_app_with_other_class_keeps_that_class() -> None:
    config = ScreenConfig(
        hobby=frozenset({"deltacall"}), meeting=frozenset({"deltacall"}), meeting_names=("x",)
    )
    assert classify("deltacall", config) == "hobby"


def test_by_category_sums_seconds_per_class() -> None:
    per_app = {
        ("alpha editor", ""): 100.0,
        ("alpha editor", "hobby"): 40.0,
        ("betagame", ""): 30.0,
        ("gamma browser", ""): 20.0,
        ("zeta tool", ""): 10.0,
        ("deltacall", ""): 5.0,
    }
    assert by_category(per_app, CONFIG) == {
        "work": 105.0,
        "hobby": 70.0,
        "browser": 20.0,
        "unmarked": 10.0,
    }


def test_by_category_server_title_class_beats_app_class() -> None:
    assert by_category({("gamma browser", "work"): 60.0}, CONFIG)["work"] == 60.0


# --- read_screen: периоды ---


def test_periods_are_day_and_evening_for_each_day_in_order() -> None:
    aw = FakeAw()
    read_screen(aw, CONFIG, D1, D2)
    assert aw.calls == [
        [
            (at(D1, 4), at(D2, 4)),
            (at(D1, 19), at(D2, 4)),
            (at(D2, 4), at(D2 + timedelta(days=1), 4)),
            (at(D2, 19), at(D2 + timedelta(days=1), 4)),
        ]
    ]


def test_one_fetch_for_all_periods() -> None:
    aw = FakeAw()
    read_screen(aw, CONFIG, D1, D1 + timedelta(days=4))
    assert len(aw.calls) == 1
    assert len(aw.calls[0]) == 10


def test_single_day_window_has_two_periods() -> None:
    aw = FakeAw()
    read_screen(aw, CONFIG, D1, D1)
    assert len(aw.calls[0]) == 2


# --- read_screen: часы ---


def one_day(whole: dict[tuple[str, str], float], evening: dict | None = None) -> FakeAw:
    return FakeAw({D1.isoformat(): (whole, evening or {})})


def test_hours_by_category_and_evening() -> None:
    aw = one_day(
        {
            ("alpha editor", ""): 2.5 * HOUR,
            ("betagame", ""): 0.5 * HOUR,
            ("gamma browser", ""): 0.25 * HOUR,
            ("zeta tool", ""): 360,
        },
        {("alpha editor", ""): 0.5 * HOUR, ("gamma browser", ""): 0.25 * HOUR},
    )
    rows, _ = read_screen(aw, CONFIG, D1, D1)
    assert rows_of(rows, D1) == {
        "screen_work_hours": 2.5,
        "screen_hobby_hours": 0.5,
        "screen_browser_hours": 0.25,
        "screen_evening_hours": 0.75,
    }


def test_evening_hours_include_browser_and_unmarked() -> None:
    aw = one_day(
        {("zeta tool", ""): HOUR, ("gamma browser", ""): HOUR},
        {("zeta tool", ""): 0.5 * HOUR, ("gamma browser", ""): 0.5 * HOUR},
    )
    rows, _ = read_screen(aw, CONFIG, D1, D1)
    assert rows_of(rows, D1)["screen_evening_hours"] == 1.0


def test_hours_are_rounded_to_two_places() -> None:
    aw = one_day({("alpha editor", ""): 4000, ("betagame", ""): 1000})
    values = rows_of(read_screen(aw, CONFIG, D1, D1)[0], D1)
    assert values["screen_work_hours"] == 1.11
    assert values["screen_hobby_hours"] == 0.28


def test_meeting_app_counts_as_work() -> None:
    aw = one_day({("deltacall", ""): HOUR})
    assert rows_of(read_screen(aw, CONFIG, D1, D1)[0], D1)["screen_work_hours"] == 1.0


def test_meeting_app_in_mixed_case_counts_as_work() -> None:
    aw = one_day({("DeltaCall", ""): HOUR})
    assert rows_of(read_screen(aw, CONFIG, D1, D1)[0], D1)["screen_work_hours"] == 1.0


def test_server_category_by_title_decides_work_or_hobby() -> None:
    aw = one_day({("zeta tool", "work"): 2 * HOUR, ("zeta tool", "hobby"): HOUR})
    values = rows_of(read_screen(aw, CONFIG, D1, D1)[0], D1)
    assert values["screen_work_hours"] == 2.0
    assert values["screen_hobby_hours"] == 1.0


def test_unmarked_is_not_stored() -> None:
    aw = one_day({("zeta tool", ""): HOUR, ("alpha editor", ""): HOUR})
    kinds = {r["kind"] for r in read_screen(aw, CONFIG, D1, D1)[0]}
    assert kinds == {
        "screen_work_hours",
        "screen_hobby_hours",
        "screen_browser_hours",
        "screen_evening_hours",
    }


def test_browser_is_separate_and_not_in_work() -> None:
    aw = one_day({("gamma browser", ""): 3 * HOUR})
    values = rows_of(read_screen(aw, CONFIG, D1, D1)[0], D1)
    assert values["screen_browser_hours"] == 3.0
    assert values["screen_work_hours"] == 0


def test_zero_category_is_stored_as_zero_not_skipped() -> None:
    aw = one_day({("alpha editor", ""): HOUR})
    values = rows_of(read_screen(aw, CONFIG, D1, D1)[0], D1)
    assert values["screen_hobby_hours"] == 0
    assert values["screen_browser_hours"] == 0
    assert values["screen_evening_hours"] == 0


def test_row_shape_for_upsert_counter() -> None:
    aw = one_day({("alpha editor", ""): HOUR})
    rows, _ = read_screen(aw, CONFIG, D1, D1)
    assert len(rows) == 4
    for row in rows:
        assert set(row) == {"date", "kind", "value", "source", "raw_json"}
        assert row["source"] == "screen"
        assert row["raw_json"] is None
        assert row["date"] == D1.isoformat()


def test_day_without_window_events_gets_no_counters() -> None:
    aw = one_day({("alpha editor", ""): HOUR})
    rows, _ = read_screen(aw, CONFIG, D1, D2)
    assert {r["date"] for r in rows} == {D1.isoformat()}


def test_no_events_at_all_gives_no_rows_and_no_notes() -> None:
    assert read_screen(FakeAw(), CONFIG, D1, D2) == ([], [])


def test_days_are_filled_independently() -> None:
    aw = FakeAw(
        {
            D1.isoformat(): ({("alpha editor", ""): HOUR}, {}),
            D2.isoformat(): ({("betagame", ""): 2 * HOUR}, {("betagame", ""): HOUR}),
        }
    )
    rows, _ = read_screen(aw, CONFIG, D1, D2)
    assert rows_of(rows, D1)["screen_work_hours"] == 1.0
    assert rows_of(rows, D2)["screen_hobby_hours"] == 2.0
    assert rows_of(rows, D2)["screen_evening_hours"] == 1.0


# --- read_screen: ошибки и замечания ---


def test_sum_over_day_length_is_screen_error() -> None:
    aw = one_day({("alpha editor", ""): 24 * HOUR + 100})
    with pytest.raises(ScreenError):
        read_screen(aw, CONFIG, D1, D1)


def test_sum_over_evening_length_is_screen_error() -> None:
    aw = one_day({("alpha editor", ""): HOUR}, {("alpha editor", ""): 9 * HOUR + 100})
    with pytest.raises(ScreenError):
        read_screen(aw, CONFIG, D1, D1)


def test_sum_equal_to_period_length_is_fine() -> None:
    aw = one_day({("alpha editor", ""): 24 * HOUR}, {("alpha editor", ""): 9 * HOUR})
    rows, _ = read_screen(aw, CONFIG, D1, D1)
    assert rows_of(rows, D1)["screen_work_hours"] == 24.0


def test_reader_error_is_passed_up() -> None:
    with pytest.raises(ScreenError, match="не отвечает"):
        read_screen(FakeAw(error=ScreenError("aw-server не отвечает")), CONFIG, D1, D1)


def test_wrong_number_of_answers_is_screen_error() -> None:
    class Short:
        def fetch(self, periods: list[Any]) -> list[dict[tuple[str, str], float]]:
            return [{}]

    with pytest.raises(ScreenError):
        read_screen(Short(), CONFIG, D1, D1)


def test_big_unmarked_share_gives_a_note_without_names() -> None:
    aw = one_day({("zeta tool", ""): 2 * HOUR, ("alpha editor", ""): 8 * HOUR})
    rows, notes = read_screen(aw, CONFIG, D1, D1)
    assert len(notes) == 1
    assert "неразмеченное" in notes[0]
    assert "20" in notes[0]
    assert "zeta" not in notes[0]
    assert "zeta" not in json.dumps(rows)


def test_small_unmarked_share_gives_no_note() -> None:
    aw = one_day({("zeta tool", ""): HOUR, ("alpha editor", ""): 9 * HOUR})
    assert read_screen(aw, CONFIG, D1, D1)[1] == []


def test_unmarked_share_is_counted_over_all_days() -> None:
    aw = FakeAw(
        {
            D1.isoformat(): ({("zeta tool", ""): 2 * HOUR, ("alpha editor", ""): 8 * HOUR}, {}),
            D2.isoformat(): ({("alpha editor", ""): 10 * HOUR}, {}),
        }
    )
    assert read_screen(aw, CONFIG, D1, D2)[1] == []


# --- AwReader (HTTP подменён) ---


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None


def serve(monkeypatch: pytest.MonkeyPatch, answer: Any) -> list[tuple[Any, dict[str, Any]]]:
    seen: list[tuple[Any, dict[str, Any]]] = []

    def urlopen(request: Any, **kwargs: Any) -> FakeResponse:
        seen.append((request, kwargs))
        if isinstance(answer, Exception):
            raise answer
        payload = answer if isinstance(answer, bytes) else json.dumps(answer).encode("utf-8")
        return FakeResponse(payload)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return seen


def event(app: str, seconds: float, category: list[str] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"app": app, "title": SECRET_TITLE}
    if category is not None:
        data["$category"] = category
    return {"timestamp": "2026-10-07T10:00:00+00:00", "duration": seconds, "data": data}


PERIODS = [(at(D1, 4), at(D2, 4)), (at(D1, 19), at(D2, 4))]


def test_aw_reader_posts_query_and_periods(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = serve(monkeypatch, [[], []])
    AwReader(CONFIG).fetch(PERIODS)
    request, kwargs = seen[0]
    assert request.full_url == "http://127.0.0.1:5600/api/0/query/"
    assert request.get_method() == "POST"
    body = json.loads(request.data)
    assert body["query"] == screen_query(CONFIG)
    assert body["timeperiods"] == [f"{a.isoformat()}/{b.isoformat()}" for a, b in PERIODS]
    assert kwargs.get("timeout")


def test_aw_reader_uses_config_url_without_double_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = serve(monkeypatch, [[], []])
    AwReader(ScreenConfig(url="http://127.0.0.1:5999/")).fetch(PERIODS)
    assert seen[0][0].full_url == "http://127.0.0.1:5999/api/0/query/"


def test_aw_reader_sums_seconds_by_app_and_category(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = [
        [event("alpha editor", 100), event("alpha editor", 50), event("zeta tool", 7, ["work"])],
        [event("betagame", 30)],
    ]
    serve(monkeypatch, answer)
    assert AwReader(CONFIG).fetch(PERIODS) == [
        {("alpha editor", ""): 150, ("zeta tool", "work"): 7},
        {("betagame", ""): 30},
    ]


def test_aw_reader_never_returns_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, [[event("alpha editor", 100, ["hobby"])], []])
    fetched = AwReader(CONFIG).fetch(PERIODS)
    assert SECRET_TITLE not in repr(fetched)


def test_title_does_not_reach_rows_or_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = [[event("alpha editor", 3600), event("zeta tool", 3600)], [event("zeta tool", 60)]]
    serve(monkeypatch, answer)
    rows, notes = read_screen(AwReader(CONFIG), CONFIG, D1, D1)
    assert SECRET_TITLE not in json.dumps(rows, ensure_ascii=False)
    assert SECRET_TITLE not in json.dumps(notes, ensure_ascii=False)
    assert all(r["raw_json"] is None for r in rows)


def test_aw_reader_connection_refused_is_screen_error(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, urllib.error.URLError(ConnectionRefusedError()))
    with pytest.raises(ScreenError):
        AwReader(CONFIG).fetch(PERIODS)


def test_aw_reader_timeout_is_screen_error(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, TimeoutError())
    with pytest.raises(ScreenError):
        AwReader(CONFIG).fetch(PERIODS)


def test_aw_reader_http_error_is_screen_error_with_code(monkeypatch: pytest.MonkeyPatch) -> None:
    error = urllib.error.HTTPError("u", 400, "bad", None, io.BytesIO(b"x"))  # type: ignore[arg-type]
    serve(monkeypatch, error)
    with pytest.raises(ScreenError, match="400"):
        AwReader(CONFIG).fetch(PERIODS)


def test_aw_reader_not_json_is_screen_error(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, b"<html>not json</html>")
    with pytest.raises(ScreenError):
        AwReader(CONFIG).fetch(PERIODS)


@pytest.mark.parametrize("answer", [{"a": 1}, [[]], [[], [], []]])
def test_aw_reader_answer_not_by_period_count_is_screen_error(
    monkeypatch: pytest.MonkeyPatch, answer: Any
) -> None:
    serve(monkeypatch, answer)
    with pytest.raises(ScreenError):
        AwReader(CONFIG).fetch(PERIODS)


def test_screen_error_text_has_no_query_or_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, urllib.error.URLError("alpha editor " + SECRET_TITLE))
    with pytest.raises(ScreenError) as info:
        AwReader(CONFIG).fetch(PERIODS)
    assert SECRET_TITLE not in str(info.value)
