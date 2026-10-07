"""Спайк: какие пороги по видам отдаёт Garmin. Только чтение, вывод в spikes/out/."""

import json
from pathlib import Path

from ai_coach.garmin.client import load_client

LACTATE_PATH = "/biometric-service/biometric/latestLactateThreshold"
OUT = Path(__file__).resolve().parents[1] / "out" / "thresholds"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = load_client()
    calls = {
        "heart_rate_zones": client.get_heart_rate_zones,
        "lactate_raw": lambda: client.connectapi(LACTATE_PATH),
        "cycling_ftp": client.get_cycling_ftp,
        "userprofile_settings": client.get_userprofile_settings,
    }
    for name, call in calls.items():
        try:
            data = call()
        except Exception as exc:  # noqa: BLE001 — спайк, фиксируем любую ошибку
            data = {"error": f"{type(exc).__name__}: {exc}"}
        (OUT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(name, "ok" if "error" not in str(data)[:20] else data)


if __name__ == "__main__":
    main()
