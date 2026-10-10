import sys
import types
from datetime import date
from pathlib import Path

import pytest
from workload_fakes import stored_event, write_config

from ai_coach.store.workload import replace_calendar_window
from ai_coach.workload.calendar_eventkit import CalendarError, CalendarReader
from ai_coach.workload.config import WorkloadConfigError, load_config
from ai_coach.workload.service import workload_day


def test_reader_wraps_eventkit_failure_in_calendar_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def requestFullAccessToEventsWithCompletion_(self, handler):  # noqa: N802
            handler(True, None)

        def calendarsForEntityType_(self, kind):  # noqa: N802
            raise RuntimeError("boom")

    class StoreClass:
        @staticmethod
        def alloc():
            return types.SimpleNamespace(init=Store)

    kit = types.SimpleNamespace(EKEventStore=StoreClass, EKEntityTypeEvent=0)
    foundation = types.SimpleNamespace(
        NSDate=types.SimpleNamespace(dateWithTimeIntervalSince1970_=lambda t: t)
    )
    monkeypatch.setitem(sys.modules, "EventKit", kit)
    monkeypatch.setitem(sys.modules, "Foundation", foundation)
    with pytest.raises(CalendarError, match="RuntimeError"):
        CalendarReader().read(date(2026, 10, 1), date(2026, 10, 2))


@pytest.mark.parametrize(
    "text",
    ['[calendar]\nwork = "Work"\n', "calendar = 1\n", "[paths]\ntodo = 5\n"],
)
def test_config_with_wrong_types_is_error(tmp_path: Path, text: str) -> None:
    with pytest.raises(WorkloadConfigError):
        load_config(write_config(tmp_path / "w.toml", text))


def test_events_of_day_include_event_crossing_midnight(conn) -> None:
    event = stored_event(
        uid="n", start_at="2026-10-07T23:00:00", end_at="2026-10-08T01:00:00", title="Ночью"
    )
    replace_calendar_window(conn, "2026-10-01", "2026-10-31", [event])
    assert [e["title"] for e in workload_day(conn, "2026-10-08", True)["events"]] == ["Ночью"]
    assert [e["title"] for e in workload_day(conn, "2026-10-09", True)["events"]] == []
