"""Сборка JSON тренировок для спайка (без сети). Все названия с префиксом SPIKE.

Запуск: uv run python spikes/garmin/workouts.py --dump
Пишет эталонные JSON в spikes/garmin/reference/ (личных данных нет).
"""

import argparse
import json
from pathlib import Path
from typing import Any

from common import PREFIX
from garminconnect.workout import (
    CyclingWorkout,
    PaceTarget,
    RunningWorkout,
    StrengthWorkout,
    SwimmingWorkout,
    WorkoutSegment,
    create_cooldown_step,
    create_distance_interval_step,
    create_interval_step,
    create_recovery_step,
    create_strength_set,
    create_targeted_interval_step,
    create_warmup_step,
    pace_to_mps,
)

REFERENCE = Path(__file__).resolve().parent / "reference"
SPORTS = {
    "yoga": {"sportTypeId": 7, "sportTypeKey": "yoga", "displayOrder": 7},
    "mobility": {"sportTypeId": 11, "sportTypeKey": "mobility", "displayOrder": 11},
    "other": {"sportTypeId": 3, "sportTypeKey": "other", "displayOrder": 3},
    "pilates": {"sportTypeId": 8, "sportTypeKey": "pilates", "displayOrder": 8},
}
STRENGTH = {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 5}
RUNNING = {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1}
CYCLING = {"sportTypeId": 2, "sportTypeKey": "cycling", "displayOrder": 2}
SWIMMING = {"sportTypeId": 4, "sportTypeKey": "swimming", "displayOrder": 3}


def segment(sport: dict[str, Any], steps: list[Any]) -> WorkoutSegment:
    return WorkoutSegment(segmentOrder=1, sportType=sport, workoutSteps=steps)


def strength() -> dict[str, Any]:
    """Силовая: 3 упражнения, подходы x повторы, вес в кг, отдых."""
    steps = [
        create_strength_set(
            "BENCH_PRESS", 1, sets=3, reps=8, rest_seconds=90,
            exercise_name="BARBELL_BENCH_PRESS", weight_kg=40,
        ),
        create_strength_set(
            "SQUAT", 4, sets=3, reps=8, rest_seconds=120,
            exercise_name="BARBELL_BACK_SQUAT", weight_kg=60,
        ),
        create_strength_set(
            "ROW", 7, sets=3, reps=10, rest_seconds=90,
            exercise_name="BARBELL_ROW", weight_kg=30,
        ),
    ]  # fmt: skip
    workout = StrengthWorkout(
        workoutName=PREFIX + "Strength",
        estimatedDurationInSecs=1800,
        workoutSegments=[segment(STRENGTH, steps)],
    )
    return _grams_to_kg(workout.to_dict())


def _grams_to_kg(node: Any) -> Any:
    """garminconnect 0.3.17 пишет weightValue в граммах, а часы читают кг (40 кг -> 40000)."""
    if isinstance(node, dict):
        return {
            k: v / 1000 if k == "weightValue" and v is not None else _grams_to_kg(v)
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [_grams_to_kg(x) for x in node]
    return node


STRETCH_EXERCISES = [
    ("Cat-cow", "STRETCH_CAT_COW"),
    ("Hamstring stretch", "STRETCH_HAMSTRING"),
    ("Hip flexor stretch", "STRETCH_HIP_FLEXOR_AND_QUAD"),
    ("Child's pose", "STRETCH_CHILDS_POSE"),
]


def stretch(kind: str, named: bool = False) -> dict[str, Any]:
    """Растяжка: 4 шага по 40 секунд, тип спорта по kind (yoga/mobility/other/pilates).

    named: шагам проставляется упражнение из каталога Garmin (WARM_UP/STRETCH_*).
    """
    steps = []
    for order, (name, exercise) in enumerate(STRETCH_EXERCISES, start=1):
        update: dict[str, Any] = {"description": name}
        if named:
            update |= {"category": "WARM_UP", "exerciseName": exercise}
        steps.append(create_interval_step(40, order).model_copy(update=update))
    seg = segment(SPORTS[kind], steps).model_dump(exclude_none=True, mode="json")
    return {
        "workoutName": f"{PREFIX}Stretch {kind}{' named' if named else ''}",
        "sportType": SPORTS[kind],
        "estimatedDurationInSecs": 160,
        "workoutSegments": [seg],
    }


def running() -> dict[str, Any]:
    pace = PaceTarget(lower_limit=pace_to_mps(6, 30, "km"), upper_limit=pace_to_mps(5, 30, "km"))
    steps = [
        create_warmup_step(300, 1),
        create_targeted_interval_step(600, 2, pace),
        create_recovery_step(120, 3),
        create_cooldown_step(300, 4),
    ]
    workout = RunningWorkout(
        workoutName=PREFIX + "Run",
        estimatedDurationInSecs=1320,
        workoutSegments=[segment(RUNNING, steps)],
    )
    return workout.to_dict()


def cycling() -> dict[str, Any]:
    steps = [create_warmup_step(300, 1), create_interval_step(900, 2), create_cooldown_step(300, 3)]
    workout = CyclingWorkout(
        workoutName=PREFIX + "Bike",
        estimatedDurationInSecs=1500,
        workoutSegments=[segment(CYCLING, steps)],
    )
    return workout.to_dict()


def swimming() -> dict[str, Any]:
    steps = [
        create_distance_interval_step(200, 1),
        create_distance_interval_step(100, 2),
        create_distance_interval_step(100, 3),
    ]
    workout = SwimmingWorkout(
        workoutName=PREFIX + "Swim",
        estimatedDurationInSecs=900,
        workoutSegments=[segment(SWIMMING, steps)],
    )
    return workout.to_dict()


def all_references() -> dict[str, dict[str, Any]]:
    refs = {"strength": strength(), "run": running(), "bike": cycling(), "swim": swimming()}
    for kind in SPORTS:
        refs[f"stretch_{kind}"] = stretch(kind)
    refs["stretch_mobility_named"] = stretch("mobility", named=True)
    return refs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", action="store_true", help="записать эталоны в reference/")
    args = parser.parse_args()
    REFERENCE.mkdir(exist_ok=True)
    for name, workout in all_references().items():
        if args.dump:
            path = REFERENCE / f"{name}.json"
            path.write_text(json.dumps(workout, ensure_ascii=False, indent=2) + "\n")
        print(f"{name}: {workout['workoutName']}")


if __name__ == "__main__":
    main()
