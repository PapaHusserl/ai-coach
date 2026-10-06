import stat
from pathlib import Path

import pytest
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)

from ai_coach.garmin.client import GarminError, full_login, load_client


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def no_mfa() -> str:
    return ""


@pytest.fixture
def token_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AI_COACH_GARMIN_DIR", str(tmp_path / "garmin"))
    return tmp_path / "garmin"


def put_tokens(token_dir: Path, mask: int = 0o644) -> Path:
    token_dir.mkdir(parents=True, exist_ok=True)
    token_file = token_dir / "garmin_tokens.json"
    token_file.write_text('{"token": "fake"}')
    token_file.chmod(mask)
    return token_file


def test_load_client_without_tokens_does_not_log_in(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(Garmin, "login", lambda self, tokenstore=None: calls.append(tokenstore))
    with pytest.raises(GarminError) as raised:
        load_client()
    assert "coach login" in str(raised.value)
    assert calls == []


def test_load_client_with_tokens_returns_client(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put_tokens(token_dir)
    seen: list[object] = []
    monkeypatch.setattr(Garmin, "login", lambda self, tokenstore=None: seen.append(tokenstore))
    client = load_client()
    assert isinstance(client, Garmin)
    assert seen == [str(token_dir)]


def test_load_client_tightens_token_permissions(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = put_tokens(token_dir, 0o644)
    monkeypatch.setattr(Garmin, "login", lambda self, tokenstore=None: None)
    load_client()
    assert mode(token_file) == 0o600
    assert mode(token_dir) == 0o700


@pytest.mark.parametrize(
    ("garmin_error", "hint"),
    [
        (GarminConnectAuthenticationError("401"), "coach login"),
        (GarminConnectTooManyRequestsError("429"), "429"),
    ],
)
def test_load_client_maps_garmin_errors_and_keeps_tokens(
    token_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    garmin_error: Exception,
    hint: str,
) -> None:
    token_file = put_tokens(token_dir)

    def broken(self: Garmin, tokenstore: str | None = None) -> None:
        raise garmin_error

    monkeypatch.setattr(Garmin, "login", broken)
    with pytest.raises(GarminError) as raised:
        load_client()
    assert hint in str(raised.value)
    assert token_file.read_text() == '{"token": "fake"}'


def test_full_login_saves_tokens_with_private_permissions(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_login(self: Garmin, tokenstore: str | None = None) -> None:
        assert tokenstore is not None
        Path(tokenstore, "garmin_tokens.json").write_text('{"token": "new"}')

    monkeypatch.setattr(Garmin, "login", fake_login)
    full_login("user@example.com", "secret", no_mfa)
    token_file = token_dir / "garmin_tokens.json"
    assert token_file.read_text() == '{"token": "new"}'
    assert mode(token_file) == 0o600
    assert mode(token_dir) == 0o700


def test_full_login_429_gives_clear_error_and_no_tokens(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: Garmin, tokenstore: str | None = None) -> None:
        raise GarminConnectTooManyRequestsError("429")

    monkeypatch.setattr(Garmin, "login", broken)
    with pytest.raises(GarminError) as raised:
        full_login("user@example.com", "secret", no_mfa)
    assert "429" in str(raised.value)
    assert not (token_dir / "garmin_tokens.json").exists()


def test_full_login_wrong_password_does_not_blame_tokens(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: Garmin, tokenstore: str | None = None) -> None:
        raise GarminConnectAuthenticationError("401")

    monkeypatch.setattr(Garmin, "login", broken)
    with pytest.raises(GarminError) as raised:
        full_login("user@example.com", "wrong", no_mfa)
    assert "wrong" not in str(raised.value)
    assert "протухли" not in str(raised.value)
    assert not (token_dir / "garmin_tokens.json").exists()
