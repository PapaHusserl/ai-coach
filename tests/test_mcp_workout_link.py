import asyncio
import base64
import json
import sqlite3
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ImageContent, TextContent
from mcp_fakes import call, call_content, db_file

from ai_coach.mcp_server import build_server
from ai_coach.mcp_server.server import INSTRUCTIONS
from ai_coach.workouts import phone

BASE = "https://example.test/player/"
RUN = {
    "date": "2026-10-08",
    "sport": "run",
    "name": "Бег 5 км",
    "spec": {"steps": [{"type": "interval", "meters": 5000}]},
}
STRENGTH = {
    "date": "2026-10-09",
    "sport": "strength",
    "name": "Силовая",
    "spec": {
        "exercises": [
            {
                "category": "BENCH_PRESS",
                "exercise": "BARBELL_BENCH_PRESS",
                "sets": 3,
                "reps": 8,
                "rest_seconds": 90,
                "weight_kg": 40,
                "title": "Жим лёжа",
                "note": "Лопатки сведены",
            }
        ]
    },
}


@pytest.fixture(autouse=True)
def player_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_COACH_PLAYER_URL", BASE)


def draft(conn: sqlite3.Connection, **workout: Any) -> int:
    return call(conn, "create_draft_workout", **workout)["draft_id"]


def fragment_of(url: str) -> str:
    assert url.startswith(BASE + "#v1.")
    return url[len(BASE) + 1 :]


def descriptions(conn: sqlite3.Connection) -> dict[str, str]:
    server = build_server(db_file(conn))
    return {tool.name: tool.description or "" for tool in asyncio.run(server.list_tools())}


def test_link_answer_has_exact_fields(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **RUN))
    assert set(result) == {"workout_id", "name", "date", "url", "length"}


def test_link_answer_values(conn: sqlite3.Connection) -> None:
    workout_id = draft(conn, **RUN)
    result = call(conn, "get_workout_link", workout_id=workout_id)
    assert (result["workout_id"], result["name"], result["date"]) == (
        workout_id,
        "Бег 5 км",
        "2026-10-08",
    )


def test_link_length_is_fragment_length(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **RUN))
    assert result["length"] == len(fragment_of(result["url"]))


def test_link_fragment_decodes_to_workout(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **RUN))
    payload = phone.decode_fragment(fragment_of(result["url"]))
    assert (payload["v"], payload["n"], payload["sp"], payload["d"]) == (
        1,
        "Бег 5 км",
        "run",
        "2026-10-08",
    )


def test_link_matches_player_payload(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **STRENGTH))
    spec = {**STRENGTH["spec"], "name": STRENGTH["name"]}
    expected = phone.player_payload("strength", spec, STRENGTH["date"])
    assert phone.decode_fragment(fragment_of(result["url"])) == expected


def test_link_without_time_has_no_tm(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **RUN))
    assert "tm" not in phone.decode_fragment(fragment_of(result["url"]))


def test_link_with_time_has_tm(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **RUN), time="07:30")
    assert phone.decode_fragment(fragment_of(result["url"]))["tm"] == "07:30"


@pytest.mark.parametrize("value", ["00:00", "23:59", "09:05"])
def test_link_accepts_valid_time(conn: sqlite3.Connection, value: str) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **RUN), time=value)
    assert phone.decode_fragment(fragment_of(result["url"]))["tm"] == value


@pytest.mark.parametrize(
    "value", ["7:30", "24:00", "12:60", "0730", "07:30:00", "", "утро", "07-30", " 07:30", "7:5"]
)
def test_link_rejects_bad_time(conn: sqlite3.Connection, value: str) -> None:
    workout_id = draft(conn, **RUN)
    with pytest.raises(ToolError):
        call(conn, "get_workout_link", workout_id=workout_id, time=value)


def test_link_unknown_workout_is_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="999"):
        call(conn, "get_workout_link", workout_id=999)


def test_link_cancelled_workout_is_error(conn: sqlite3.Connection) -> None:
    workout_id = draft(conn, **RUN)
    call(conn, "cancel_draft_workout", workout_id=workout_id)
    with pytest.raises(ToolError):
        call(conn, "get_workout_link", workout_id=workout_id)


def test_link_works_for_draft_without_approval(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **STRENGTH))
    assert result["url"].startswith(BASE)


def test_link_uses_title_and_note(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **STRENGTH))
    block = phone.decode_fragment(fragment_of(result["url"]))["b"][0]
    assert block["t"] == "Жим лёжа"
    assert block["s"][0]["note"] == "Лопатки сведены"


def test_link_does_not_change_workout(conn: sqlite3.Connection) -> None:
    workout_id = draft(conn, **RUN)
    before = conn.execute("SELECT * FROM planned_workouts").fetchall()
    call(conn, "get_workout_link", workout_id=workout_id)
    after = conn.execute("SELECT * FROM planned_workouts").fetchall()
    assert [tuple(r) for r in after] == [tuple(r) for r in before]


def test_link_without_player_url_is_error(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    workout_id = draft(conn, **RUN)
    monkeypatch.delenv("AI_COACH_PLAYER_URL")
    monkeypatch.setattr(phone, "PLAYER_URL", "")
    with pytest.raises(ToolError, match="адрес плеера"):
        call(conn, "get_workout_link", workout_id=workout_id)


def test_link_with_empty_player_url_env_is_error(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    workout_id = draft(conn, **RUN)
    monkeypatch.setenv("AI_COACH_PLAYER_URL", "")
    monkeypatch.setattr(phone, "PLAYER_URL", "")
    with pytest.raises(ToolError, match="адрес плеера"):
        call(conn, "get_workout_link", workout_id=workout_id)


def test_link_over_limit_is_tool_error(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    workout_id = draft(conn, **RUN)
    monkeypatch.setattr(phone, "MAX_FRAGMENT", 10)
    with pytest.raises(ToolError, match="лимит"):
        call(conn, "get_workout_link", workout_id=workout_id)


def test_link_at_exact_limit_passes(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    workout_id = draft(conn, **RUN)
    length = call(conn, "get_workout_link", workout_id=workout_id)["length"]
    monkeypatch.setattr(phone, "MAX_FRAGMENT", length)
    assert call(conn, "get_workout_link", workout_id=workout_id)["length"] == length


# --- QR-картинка в ответе ---


def images(conn: sqlite3.Connection, **arguments: Any) -> list[ImageContent]:
    blocks = call_content(conn, "get_workout_link", **arguments)
    return [b for b in blocks if isinstance(b, ImageContent)]


def test_link_has_one_image(conn: sqlite3.Connection) -> None:
    assert len(images(conn, workout_id=draft(conn, **RUN))) == 1


def test_link_image_is_png_mime(conn: sqlite3.Connection) -> None:
    image = images(conn, workout_id=draft(conn, **RUN))[0]
    assert image.mime_type == "image/png"


def test_link_image_data_starts_with_png_signature(conn: sqlite3.Connection) -> None:
    image = images(conn, workout_id=draft(conn, **RUN))[0]
    assert base64.b64decode(image.data)[:8] == b"\x89PNG\r\n\x1a\n"


def test_link_with_time_has_image(conn: sqlite3.Connection) -> None:
    assert len(images(conn, workout_id=draft(conn, **RUN), time="07:30")) == 1


def test_link_text_block_first_then_image(conn: sqlite3.Connection) -> None:
    workout_id = draft(conn, **RUN)
    blocks = call_content(conn, "get_workout_link", workout_id=workout_id)
    url = call(conn, "get_workout_link", workout_id=workout_id)["url"]
    assert isinstance(blocks[0], TextContent)
    assert json.loads(blocks[0].text)["url"] == url
    assert isinstance(blocks[1], ImageContent)


def test_link_fields_unchanged_next_to_image(conn: sqlite3.Connection) -> None:
    result = call(conn, "get_workout_link", workout_id=draft(conn, **RUN))
    assert set(result) == {"workout_id", "name", "date", "url", "length"}


def test_link_unknown_workout_has_no_image(conn: sqlite3.Connection) -> None:
    with pytest.raises(ToolError, match="999"):
        call_content(conn, "get_workout_link", workout_id=999)


def test_link_over_limit_has_no_image(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    workout_id = draft(conn, **RUN)
    monkeypatch.setattr(phone, "MAX_FRAGMENT", 10)
    with pytest.raises(ToolError, match="лимит"):
        call_content(conn, "get_workout_link", workout_id=workout_id)


def test_link_without_player_url_has_no_image(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    workout_id = draft(conn, **RUN)
    monkeypatch.delenv("AI_COACH_PLAYER_URL")
    monkeypatch.setattr(phone, "PLAYER_URL", "")
    with pytest.raises(ToolError, match="адрес плеера"):
        call_content(conn, "get_workout_link", workout_id=workout_id)


def test_link_tool_description_mentions_qr(conn: sqlite3.Connection) -> None:
    assert "QR" in descriptions(conn)["get_workout_link"]


def test_link_tool_description_says_scan_with_camera(conn: sqlite3.Connection) -> None:
    assert "камер" in descriptions(conn)["get_workout_link"]


# --- тексты для Claude Desktop ---


def test_link_tool_description_says_show_link_as_is(conn: sqlite3.Connection) -> None:
    text = descriptions(conn)["get_workout_link"]
    assert "как есть" in text


def test_link_tool_description_prefers_time_for_run(conn: sqlite3.Connection) -> None:
    text = descriptions(conn)["get_workout_link"]
    assert "по времени" in text
    assert "телефон" in text


def test_link_tool_description_mentions_time_param(conn: sqlite3.Connection) -> None:
    assert "HH:MM" in descriptions(conn)["get_workout_link"]


def test_instructions_mention_link_and_phone() -> None:
    assert "get_workout_link" in INSTRUCTIONS
    assert "телефон" in INSTRUCTIONS


@pytest.mark.parametrize(
    "word",
    [
        "exercises",
        "steps",
        "category",
        "exercise",
        "sets",
        "reps",
        "rest_seconds",
        "weight_kg",
        "seconds",
        "meters",
        "pace_sec_per_km",
        "description",
        "type",
        "title",
        "note",
    ],
)
def test_create_draft_description_is_self_contained(conn: sqlite3.Connection, word: str) -> None:
    assert word in descriptions(conn)["create_draft_workout"]


@pytest.mark.parametrize("sport", ["strength", "mobility", "run", "bike", "swim"])
def test_create_draft_description_names_sport(conn: sqlite3.Connection, sport: str) -> None:
    assert sport in descriptions(conn)["create_draft_workout"]


def test_create_draft_description_says_garmin_codes_required(conn: sqlite3.Connection) -> None:
    text = descriptions(conn)["create_draft_workout"]
    assert "Garmin" in text
    assert "обязательн" in text
