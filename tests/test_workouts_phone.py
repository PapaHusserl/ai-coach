import base64
import json
import random
import re
import string
import zlib
from pathlib import Path
from typing import Any

import pytest

from ai_coach.workouts import phone

LINKS = Path(__file__).resolve().parent / "fixtures" / "links"
NAMES = ["strength", "stretch", "run"]
BASE = "https://example.test/player/"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((LINKS / f"{name}.json").read_text(encoding="utf-8"))


def build(name: str) -> dict[str, Any]:
    data = fixture(name)
    payload = data["payload"]
    return phone.player_payload(payload["sp"], data["spec"], payload["d"], payload.get("tm"))


def deflate_fragment(raw: bytes) -> str:
    packer = zlib.compressobj(9, zlib.DEFLATED, -15)
    data = packer.compress(raw) + packer.flush()
    return "v1." + base64.urlsafe_b64encode(data).decode().rstrip("=")


def noisy_payload(size: int) -> dict[str, Any]:
    rnd = random.Random(1)
    note = "".join(rnd.choice(string.ascii_letters + string.digits) for _ in range(size))
    return {
        "v": 1,
        "n": "x",
        "sp": "run",
        "d": "2026-10-09",
        "b": [{"r": 1, "s": [{"k": "work", "note": note}]}],
    }


# --- константы ---


def test_player_version_is_1() -> None:
    assert phone.PLAYER_VERSION == 1


def test_max_fragment_is_2000() -> None:
    assert phone.MAX_FRAGMENT == 2000


# --- эталонные фикстуры: контракт с JS ---


@pytest.mark.parametrize("name", NAMES)
def test_payload_matches_fixture(name: str) -> None:
    assert build(name) == fixture(name)["payload"]


@pytest.mark.parametrize("name", NAMES)
def test_fragment_matches_fixture(name: str) -> None:
    assert phone.encode_fragment(fixture(name)["payload"]) == fixture(name)["fragment"]


@pytest.mark.parametrize("name", NAMES)
def test_fixture_fragment_decodes_to_payload(name: str) -> None:
    assert phone.decode_fragment(fixture(name)["fragment"]) == fixture(name)["payload"]


@pytest.mark.parametrize("name", NAMES)
def test_fixture_fragment_is_within_limit(name: str) -> None:
    assert len(fixture(name)["fragment"]) <= 2000


# --- payload ---


def test_strength_zero_weight_has_no_kg() -> None:
    work = build("strength")["b"][1]["s"][0]
    assert "kg" not in work


def test_strength_without_title_gets_readable_code() -> None:
    spec = {
        "name": "С",
        "exercises": [
            {
                "category": "SQUAT",
                "exercise": "BARBELL_BACK_SQUAT",
                "sets": 3,
                "reps": 5,
                "rest_seconds": 90,
                "weight_kg": 60,
            }
        ],
    }
    payload = phone.player_payload("strength", spec, "2026-10-09")
    assert payload["b"][0]["t"] == "Barbell back squat"


def plank_payload(**extra: Any) -> dict[str, Any]:
    item = {"category": "PLANK", "exercise": "PLANK", "sets": 3, "seconds": 60,
            "rest_seconds": 60, "weight_kg": 0}  # fmt: skip
    spec = {"name": "Планка", "exercises": [item | extra]}
    return phone.player_payload("strength", spec, "2026-10-09")


def test_strength_seconds_becomes_sec_without_reps_and_kg() -> None:
    assert plank_payload()["b"][0]["s"][0] == {"k": "work", "sec": 60}


def test_strength_seconds_with_weight_keeps_kg() -> None:
    assert plank_payload(weight_kg=10)["b"][0]["s"][0] == {"k": "work", "sec": 60, "kg": 10}


def test_strength_seconds_block_repeats_sets_and_has_rest() -> None:
    block = plank_payload()["b"][0]
    assert block["r"] == 3
    assert block["s"][1] == {"k": "rest", "sec": 60}


def test_strength_seconds_block_title_is_readable_code() -> None:
    assert plank_payload()["b"][0]["t"] == "Plank"


def test_strength_seconds_fragment_fits_limit() -> None:
    assert len(phone.encode_fragment(plank_payload())) <= phone.MAX_FRAGMENT


def test_strength_reps_has_reps_and_no_sec() -> None:
    item = {"category": "PLANK", "exercise": "PLANK", "sets": 3, "reps": 8,
            "rest_seconds": 60, "weight_kg": 0}  # fmt: skip
    spec = {"name": "Планка", "exercises": [item]}
    work = phone.player_payload("strength", spec, "2026-10-09")["b"][0]["s"][0]
    assert work["reps"] == 8
    assert "sec" not in work


def test_strength_block_repeats_equal_sets() -> None:
    assert [b["r"] for b in build("strength")["b"]] == [3, 2]


def test_stretch_description_goes_to_note() -> None:
    assert build("stretch")["b"][0]["s"][0]["note"] == "Таз к пяткам, вытяни руки вперёд"


def test_run_interval_becomes_work() -> None:
    assert [s["k"] for s in build("run")["b"][0]["s"]] == ["warmup", "work", "recovery", "cooldown"]


def test_run_steps_are_in_one_block() -> None:
    assert len(build("run")["b"]) == 1


def test_run_meters_and_pace() -> None:
    step = build("run")["b"][0]["s"][1]
    assert (step["m"], step["pace"]) == (1000, [255, 245])


def test_no_time_means_no_tm_key() -> None:
    assert "tm" not in build("run")


def test_time_goes_to_tm() -> None:
    assert build("strength")["tm"] == "18:30"


def test_empty_keys_are_dropped() -> None:
    spec = {"name": "Бег", "steps": [{"type": "warmup", "seconds": 300}]}
    payload = phone.player_payload("run", spec, "2026-10-09")
    assert payload["b"][0]["s"] == [{"k": "warmup", "sec": 300}]
    assert "dur" not in payload


@pytest.mark.parametrize("sport", ["bike", "swim"])
def test_bike_and_swim_interval_becomes_work(sport: str) -> None:
    spec = {"name": "Т", "steps": [{"type": "interval", "seconds": 600}]}
    payload = phone.player_payload(sport, spec, "2026-10-10")
    assert payload["sp"] == sport
    assert payload["b"][0]["s"] == [{"k": "work", "sec": 600}]


# --- encode / decode ---


def test_roundtrip() -> None:
    payload = fixture("run")["payload"]
    assert phone.decode_fragment(phone.encode_fragment(payload)) == payload


def test_fragment_has_v1_prefix_and_url_safe_alphabet() -> None:
    fragment = phone.encode_fragment(fixture("stretch")["payload"])
    assert re.fullmatch(r"v1\.[A-Za-z0-9_-]+", fragment)


def test_encode_is_deterministic() -> None:
    payload = fixture("strength")["payload"]
    assert phone.encode_fragment(payload) == phone.encode_fragment(payload)


def test_encode_ignores_key_order() -> None:
    first = {"v": 1, "n": "a", "sp": "run", "d": "2026-10-09"}
    second = {"d": "2026-10-09", "sp": "run", "n": "a", "v": 1}
    assert phone.encode_fragment(first) == phone.encode_fragment(second)


def test_unicode_survives_roundtrip() -> None:
    payload = {"v": 1, "n": "Ёлка, жим лёжа 💪 日本", "sp": "run", "d": "2026-10-09"}
    assert phone.decode_fragment(phone.encode_fragment(payload)) == payload


def test_unicode_is_not_escaped_in_json() -> None:
    payload = {"v": 1, "n": "Ёлка", "sp": "run", "d": "2026-10-09"}
    fragment = phone.encode_fragment(payload)
    body = fragment[3:]
    raw = zlib.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)), -15)
    assert (
        raw
        == json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True).encode()
    )


@pytest.mark.parametrize(
    "fragment", ["", "v1.", "garbage", "v2.abcd", "v1.!!!!", "v1.@@@@", "v1.A", "v1.abcdefgh"]
)
def test_decode_rejects_garbage(fragment: str) -> None:
    with pytest.raises(ValueError):
        phone.decode_fragment(fragment)


def test_decode_rejects_other_prefix_with_valid_body() -> None:
    body = phone.encode_fragment(fixture("run")["payload"])[3:]
    with pytest.raises(ValueError):
        phone.decode_fragment("v2." + body)


def test_decode_rejects_valid_deflate_that_is_not_json() -> None:
    with pytest.raises(ValueError):
        phone.decode_fragment(deflate_fragment(b"not json at all"))


# --- лимит 2000 ---


def test_fragment_over_real_limit_raises() -> None:
    with pytest.raises(ValueError, match="2000"):
        phone.encode_fragment(noisy_payload(3000))


def test_fragment_just_over_real_limit_raises() -> None:
    for size in range(1400, 3000, 7):
        fragment = deflate_fragment(
            json.dumps(
                noisy_payload(size), separators=(",", ":"), ensure_ascii=False, sort_keys=True
            ).encode()
        )
        if len(fragment) > 2000:
            with pytest.raises(ValueError, match="2000"):
                phone.encode_fragment(noisy_payload(size))
            return
    raise AssertionError("не нашли размер сверх лимита")


def test_fragment_of_exactly_limit_length_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    fragment = phone.encode_fragment(noisy_payload(500))
    monkeypatch.setattr(phone, "MAX_FRAGMENT", len(fragment))
    assert phone.encode_fragment(noisy_payload(500)) == fragment


def test_fragment_one_over_limit_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fragment = phone.encode_fragment(noisy_payload(500))
    monkeypatch.setattr(phone, "MAX_FRAGMENT", len(fragment) - 1)
    with pytest.raises(ValueError):
        phone.encode_fragment(noisy_payload(500))


def test_limit_message_has_length_and_advice(monkeypatch: pytest.MonkeyPatch) -> None:
    fragment = phone.encode_fragment(noisy_payload(500))
    monkeypatch.setattr(phone, "MAX_FRAGMENT", len(fragment) - 1)
    with pytest.raises(ValueError, match=str(len(fragment))):
        phone.encode_fragment(noisy_payload(500))


# --- адрес ---


def test_workout_url_joins_base_and_fragment() -> None:
    assert phone.workout_url("v1.abc", BASE) == BASE + "#v1.abc"


def test_default_player_url_is_a_string() -> None:
    assert isinstance(phone.PLAYER_URL, str)


def test_strength_zero_rest_has_no_rest_step() -> None:
    spec = {
        "name": "С",
        "exercises": [
            {
                "category": "SQUAT",
                "exercise": "BARBELL_BACK_SQUAT",
                "sets": 3,
                "reps": 5,
                "rest_seconds": 0,
                "weight_kg": 60,
            }
        ],
    }
    payload = phone.player_payload("strength", spec, "2026-10-09")
    assert [s["k"] for s in payload["b"][0]["s"]] == ["work"]
