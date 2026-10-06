"""Проверка 1. Логин Garmin (с MFA, если включена) и сохранение токенов.

Запуск: ! uv run python spikes/garmin/login.py
Токены есть - входит по ним без пароля. Нет - спрашивает логин/пароль через getpass.
Креды не печатаются и не пишутся.
"""

import argparse
from getpass import getpass

from common import TOKEN_DIR, TOKEN_FILE, fix_perms
from garminconnect import Garmin


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    TOKEN_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    TOKEN_DIR.chmod(0o700)
    if TOKEN_FILE.exists():
        print("Токены найдены, входим без пароля.")
        client = Garmin()
        client.login(str(TOKEN_DIR))
        fix_perms()
        print("OK: вход по токенам прошёл.")
        return
    asked = {"mfa": False}

    def prompt_mfa() -> str:
        asked["mfa"] = True
        return getpass("Код MFA: ")

    email = getpass("Garmin email (ввод скрыт): ")
    password = getpass("Garmin пароль (ввод скрыт): ")
    client = Garmin(email, password, prompt_mfa=prompt_mfa)
    client.login(str(TOKEN_DIR))
    fix_perms()
    print(f"OK: логин прошёл. MFA запрашивалась: {asked['mfa']}")
    print(f"Токены: {TOKEN_FILE}, права {oct(TOKEN_FILE.stat().st_mode & 0o777)}")
    print("Запусти этот скрипт ещё раз: должен войти без пароля.")


main()
