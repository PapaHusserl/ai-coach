import json
from pathlib import Path
from typing import Any

import pytest

from ai_coach.workouts import build_workout, describe_workout

REFERENCE = Path(__file__).parent / "fixtures" / "workouts"


def reference(name: str) -> dict[str, Any]:
    return json.loads((REFERENCE / f"{name}.json").read_text())


def strength_spec() -> dict[str, Any]:
    return {
        "name": "SPIKE Strength",
        "estimated_duration_secs": 1800,
        "exercises": [
            {"category": "BENCH_PRESS", "exercise": "BARBELL_BENCH_PRESS", "sets": 3,
             "reps": 8, "rest_seconds": 90, "weight_kg": 40},
            {"category": "SQUAT", "exercise": "BARBELL_BACK_SQUAT", "sets": 3,
             "reps": 8, "rest_seconds": 120, "weight_kg": 60},
            {"category": "ROW", "exercise": "BARBELL_ROW", "sets": 3,
             "reps": 10, "rest_seconds": 90, "weight_kg": 30},
        ],
    }  # fmt: skip


def mobility_spec() -> dict[str, Any]:
    names = [
        ("Cat-cow", "STRETCH_CAT_COW"),
        ("Hamstring stretch", "STRETCH_HAMSTRING"),
        ("Hip flexor stretch", "STRETCH_HIP_FLEXOR_AND_QUAD"),
        ("Child's pose", "STRETCH_CHILDS_POSE"),
    ]
    return {
        "name": "SPIKE Stretch mobility named",
        "estimated_duration_secs": 160,
        "steps": [{"description": d, "exercise": e, "seconds": 40} for d, e in names],
    }


def run_spec() -> dict[str, Any]:
    return {
        "name": "SPIKE Run",
        "estimated_duration_secs": 1320,
        "steps": [
            {"type": "warmup", "seconds": 300},
            {"type": "interval", "seconds": 600, "pace_sec_per_km": [390, 330]},
            {"type": "recovery", "seconds": 120},
            {"type": "cooldown", "seconds": 300},
        ],
    }


def bike_spec() -> dict[str, Any]:
    return {
        "name": "SPIKE Bike",
        "estimated_duration_secs": 1500,
        "steps": [
            {"type": "warmup", "seconds": 300},
            {"type": "interval", "seconds": 900},
            {"type": "cooldown", "seconds": 300},
        ],
    }


def swim_spec() -> dict[str, Any]:
    return {
        "name": "SPIKE Swim",
        "estimated_duration_secs": 900,
        "steps": [
            {"type": "interval", "meters": 200},
            {"type": "interval", "meters": 100},
            {"type": "interval", "meters": 100},
        ],
    }


def test_strength_matches_reference() -> None:
    assert build_workout("strength", strength_spec()) == reference("strength")


def test_strength_weight_is_in_kilograms_not_grams() -> None:
    workout = build_workout("strength", strength_spec())
    first = workout["workoutSegments"][0]["workoutSteps"][0]["workoutSteps"][0]
    assert first["weightValue"] == 40.0


def test_strength_repeats_set_count_and_has_rest_step() -> None:
    workout = build_workout("strength", strength_spec())
    group = workout["workoutSegments"][0]["workoutSteps"][1]
    assert group["numberOfIterations"] == 3
    assert [s["stepType"]["stepTypeKey"] for s in group["workoutSteps"]] == ["interval", "rest"]
    assert group["workoutSteps"][1]["endConditionValue"] == 120.0


def plank_spec(**timing: Any) -> dict[str, Any]:
    item = {"category": "PLANK", "exercise": "PLANK", "sets": 3, "rest_seconds": 60,
            "weight_kg": 0}  # fmt: skip
    return {"name": "Планка", "estimated_duration_secs": 360, "exercises": [item | timing]}


def plank_group(**timing: Any) -> dict[str, Any]:
    return build_workout("strength", plank_spec(**timing))["workoutSegments"][0]["workoutSteps"][0]


def test_strength_seconds_work_step_ends_by_time() -> None:
    work = plank_group(seconds=60)["workoutSteps"][0]
    assert work["endCondition"]["conditionTypeKey"] == "time"


def test_strength_seconds_work_step_has_duration_as_float() -> None:
    work = plank_group(seconds=60)["workoutSteps"][0]
    assert work["endConditionValue"] == 60.0


def test_strength_seconds_keeps_exercise_and_weight() -> None:
    work = plank_group(seconds=60)["workoutSteps"][0]
    assert (work["exerciseName"], work["weightValue"]) == ("PLANK", 0.0)


def test_strength_seconds_keeps_sets_and_rest() -> None:
    group = plank_group(seconds=60)
    assert group["numberOfIterations"] == 3
    assert [s["stepType"]["stepTypeKey"] for s in group["workoutSteps"]] == ["interval", "rest"]
    assert group["workoutSteps"][1]["endConditionValue"] == 60.0


def test_describe_workout_shows_plank_seconds() -> None:
    workout = build_workout("strength", plank_spec(seconds=60))
    assert "interval: 60 с, PLANK/PLANK, 0 кг" in describe_workout(workout)


def test_strength_reps_work_step_still_ends_by_reps() -> None:
    work = plank_group(reps=8)["workoutSteps"][0]
    assert work["endCondition"]["conditionTypeKey"] == "reps"
    assert work["endConditionValue"] == 8.0


def test_strength_with_reps_and_seconds_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_workout("strength", plank_spec(reps=8, seconds=60))


def test_strength_without_reps_and_seconds_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_workout("strength", plank_spec())


def test_mobility_matches_reference() -> None:
    assert build_workout("mobility", mobility_spec()) == reference("stretch_mobility_named")


def test_mobility_keeps_russian_description() -> None:
    spec = mobility_spec()
    spec["steps"][0]["description"] = "Кошка-корова: спина круглая, выдох"
    workout = build_workout("mobility", spec)
    first = workout["workoutSegments"][0]["workoutSteps"][0]
    assert first["description"] == "Кошка-корова: спина круглая, выдох"


def test_mobility_uses_warm_up_category() -> None:
    workout = build_workout("mobility", mobility_spec())
    steps = workout["workoutSegments"][0]["workoutSteps"]
    assert {s["category"] for s in steps} == {"WARM_UP"}
    assert workout["sportType"]["sportTypeKey"] == "mobility"


def test_run_matches_reference() -> None:
    assert build_workout("run", run_spec()) == reference("run")


def test_bike_matches_reference() -> None:
    assert build_workout("bike", bike_spec()) == reference("bike")


def test_swim_matches_reference() -> None:
    assert build_workout("swim", swim_spec()) == reference("swim")


def test_unknown_sport_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_workout("yoga", mobility_spec())


def test_workout_is_json_serializable() -> None:
    for sport, spec in [("strength", strength_spec()), ("run", run_spec())]:
        json.dumps(build_workout(sport, spec))
