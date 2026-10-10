import subprocess
import sys

BLOCK = "import sys; sys.modules['EventKit'] = None; sys.modules['Foundation'] = None; "


def run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-c", BLOCK + code], capture_output=True, text=True
    )


def test_package_imports_without_eventkit() -> None:
    result = run("import ai_coach.workload.calendar_eventkit, ai_coach.workload.service")
    assert result.returncode == 0, result.stderr


def test_cli_and_mcp_import_without_eventkit() -> None:
    result = run("import ai_coach.cli.main, ai_coach.mcp_server, ai_coach.sync.workload_sync")
    assert result.returncode == 0, result.stderr


def test_reader_without_eventkit_raises_calendar_error() -> None:
    code = (
        "from datetime import date\n"
        "from ai_coach.workload.calendar_eventkit import CalendarError, CalendarReader\n"
        "try:\n"
        "    CalendarReader().read(date(2026, 10, 1), date(2026, 10, 2))\n"
        "except CalendarError:\n"
        "    print('calendar-error')\n"
    )
    result = run(code)
    assert "calendar-error" in result.stdout, result.stderr


def test_calendar_error_is_an_exception() -> None:
    from ai_coach.workload.calendar_eventkit import CalendarError

    assert issubclass(CalendarError, Exception)
