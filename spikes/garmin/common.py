"""Общее для скриптов спайка Garmin. Одноразовый код, не продакшен."""

import json
from pathlib import Path
from typing import Any

from garminconnect import Garmin

TOKEN_DIR = Path.home() / ".config" / "ai-coach" / "garmin"
TOKEN_FILE = TOKEN_DIR / "garmin_tokens.json"
OUT = Path(__file__).resolve().parents[1] / "out"
PREFIX = "SPIKE "
LOGIN_HINT = "Токенов нет. Сначала запусти: ! uv run python spikes/garmin/login.py"


def fix_perms() -> None:
    TOKEN_DIR.chmod(0o700)
    if TOKEN_FILE.exists():
        TOKEN_FILE.chmod(0o600)


def load_client() -> Garmin:
    """Вход только по сохранённым токенам. Нет токенов - ошибка, не новый логин."""
    if not TOKEN_FILE.exists():
        raise SystemExit(LOGIN_HINT)
    client = Garmin()
    client.login(str(TOKEN_DIR))
    fix_perms()
    return client


def save_json(name: str, data: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def confirm(text: str) -> bool:
    print(text)
    return input("Отправить? [y/N] ").strip().lower() == "y"


def describe(workout: dict[str, Any]) -> str:
    sport = workout["sportType"]["sportTypeKey"]
    steps = sum(len(s["workoutSteps"]) for s in workout["workoutSegments"])
    return f"'{workout['workoutName']}', спорт {sport}, шагов верхнего уровня {steps}"


def remember(entry: dict[str, Any]) -> None:
    """Дописывает загруженное в out/uploaded.json (для удаления и отчёта)."""
    path = OUT / "uploaded.json"
    items = json.loads(path.read_text()) if path.exists() else []
    items.append(entry)
    save_json("uploaded.json", items)


def upload_and_schedule(client: Garmin, workout: dict[str, Any], date_str: str, push: bool) -> None:
    """Загрузка, планирование на дату, по желанию push на часы. Каждый шаг - через y/N."""
    name = workout["workoutName"]
    if not name.startswith(PREFIX):
        raise SystemExit(f"Название должно начинаться с '{PREFIX}': {name}")
    slug = name.replace(" ", "_").lower()
    if not confirm(f"Загрузить в Garmin Connect: {describe(workout)}"):
        print("Пропущено.")
        return
    uploaded = client.upload_workout(workout)
    save_json(f"upload_{slug}.json", uploaded)
    workout_id = uploaded["workoutId"]
    print(f"Загружено, workoutId={workout_id}")
    entry: dict[str, Any] = {"workoutId": workout_id, "name": name, "date": None}
    remember(entry)
    if confirm(f"Запланировать workoutId={workout_id} на {date_str}"):
        scheduled = client.schedule_workout(workout_id, date_str)
        save_json(f"schedule_{slug}.json", scheduled)
        entry["date"] = date_str
        remember(entry)
        print("Запланировано.")
    if push and confirm(f"Отправить workoutId={workout_id} на устройство (push)"):
        pushed = client.push_workout_to_device(workout_id)
        save_json(f"push_{slug}.json", pushed)
        print("Push отправлен.")
    print("Синхронизируй часы (Garmin Connect на телефоне) и проверь на часах.")
