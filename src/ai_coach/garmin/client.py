"""Обёртка над garminconnect: вход по токенам и единственный полный логин."""

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

import requests  # pyright: ignore[reportMissingTypeStubs]
from garminconnect import (  # pyright: ignore[reportMissingTypeStubs]
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

TOKEN_ENV = "AI_COACH_GARMIN_DIR"
TOKEN_NAME = "garmin_tokens.json"

NO_TOKENS = "Токенов Garmin нет. Выполни в обычном терминале: coach login"
BAD_PASSWORD = "Garmin не принял логин или пароль. Проверь их и повтори: coach login"
NETWORK = "Не удалось связаться с Garmin (ошибка сети или сервера). Повтори позже."
TOO_MANY = "Garmin вернул 429 (слишком много запросов или логинов). Подожди и повтори позже."


def token_dir() -> Path:
    """$AI_COACH_GARMIN_DIR, иначе ~/.config/ai-coach/garmin."""
    env = os.environ.get(TOKEN_ENV)
    return Path(env) if env else Path.home() / ".config" / "ai-coach" / "garmin"


def stale_tokens() -> str:
    return (
        "Токены Garmin протухли или отклонены. Удали "
        f"{token_dir() / TOKEN_NAME} и выполни в обычном терминале: coach login"
    )


class GarminError(Exception):
    """Понятная пользователю ошибка Garmin. Текст — готовое сообщение для консоли."""


class GarminAuthError(GarminError):
    """Нет токенов, токены протухли или логин/пароль не приняты."""


class GarminRateLimitError(GarminError):
    """Garmin ответил 429."""


@contextmanager
def garmin_errors(auth_message: str | None = None) -> Generator[None]:
    """Переводит ошибки garminconnect (401, 429, сеть) в наши, с понятным текстом."""
    try:
        yield
    except GarminConnectTooManyRequestsError as e:
        raise GarminRateLimitError(TOO_MANY) from e
    except GarminConnectAuthenticationError as e:
        raise GarminAuthError(auth_message or stale_tokens()) from e
    except (GarminConnectConnectionError, requests.RequestException) as e:
        raise GarminError(NETWORK) from e


def fix_perms(token_dir: Path) -> None:
    token_dir.chmod(0o700)
    token_file = token_dir / TOKEN_NAME
    if token_file.exists():
        token_file.chmod(0o600)


def load_client(directory: Path | None = None) -> Garmin:
    """Вход только по сохранённым токенам. Нет токенов — ошибка, не новый логин."""
    directory = directory or token_dir()
    if not (directory / TOKEN_NAME).exists():
        raise GarminAuthError(NO_TOKENS)
    client = Garmin()
    with garmin_errors():
        client.login(str(directory))
    fix_perms(directory)
    return client


def full_login(
    email: str,
    password: str,
    prompt_mfa: Callable[[], str],
    directory: Path | None = None,
) -> None:
    """Полный логин по паролю. Вызывается только из `coach login`."""
    directory = directory or token_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    client = Garmin(email, password, prompt_mfa=prompt_mfa)
    with garmin_errors(BAD_PASSWORD):
        client.login(str(directory))
    fix_perms(directory)
