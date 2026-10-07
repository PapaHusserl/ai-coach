import ast
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from mcp_fakes import tool_names

import ai_coach.mcp_server as package

FORBIDDEN_WORDS = ["push", "send", "delete", "remove", "schedule", "upload", "garmin", "approve"]
FORBIDDEN_MODULES = ["garminconnect", "ai_coach.garmin", "ai_coach.plan", "ai_coach.sync"]
SOURCES = sorted(Path(package.__file__ or "").parent.glob("*.py"))


def imported_modules(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


EXPECTED_TOOLS = {
    "get_morning_snapshot",
    "get_daily_metrics",
    "get_activities",
    "get_strength_sets",
    "get_goals",
    "get_goals_on",
    "get_phases",
    "get_plan",
    "get_plan_actual",
    "get_load",
    "get_weights",
    "get_food",
    "get_food_pending",
    "get_wellbeing",
    "get_deviations",
    "save_food_nutrition",
    "create_draft_workout",
    "cancel_draft_workout",
    "propose_phase",
}


def test_server_has_only_expected_tools(conn: sqlite3.Connection) -> None:
    assert tool_names(conn) == EXPECTED_TOOLS


def test_no_tool_can_push_or_delete(conn: sqlite3.Connection) -> None:
    names = tool_names(conn)
    assert names
    bad = [name for name in names if any(word in name.lower() for word in FORBIDDEN_WORDS)]
    assert bad == []


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_source_does_not_import_sending_code(path: Path) -> None:
    for name in imported_modules(path):
        for forbidden in FORBIDDEN_MODULES:
            assert name != forbidden
            assert not name.startswith(forbidden + ".")


def test_garmin_client_is_not_loaded_with_server() -> None:
    code = (
        "import sys; import ai_coach.mcp_server.server;"
        "bad = [m for m in sys.modules if m == 'garminconnect' or m.startswith('ai_coach.garmin')];"
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
