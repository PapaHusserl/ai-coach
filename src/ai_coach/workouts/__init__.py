"""workouts: сборка JSON тренировок Garmin (garmin_json), ссылка на плеер для телефона (phone)."""

from ai_coach.workouts.garmin_json import SPORTS, build_workout, describe_workout
from ai_coach.workouts.phone import (
    decode_fragment,
    encode_fragment,
    player_payload,
    player_url,
    workout_link_url,
    workout_url,
)

__all__ = [
    "SPORTS",
    "build_workout",
    "decode_fragment",
    "describe_workout",
    "encode_fragment",
    "player_payload",
    "player_url",
    "workout_link_url",
    "workout_url",
]
