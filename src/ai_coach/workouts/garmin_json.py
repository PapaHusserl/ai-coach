"""Сборка JSON тренировок для Garmin Connect по эталонам спайка (tests/fixtures/workouts).

Свой код вместо garminconnect.create_strength_set: тот пишет weightValue в граммах, нужны кг.
"""

from typing import Any

SPORTS = ("strength", "mobility", "run", "bike", "swim")

GARMIN_SPORT = {
    "strength": {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 5},
    "mobility": {"sportTypeId": 11, "sportTypeKey": "mobility", "displayOrder": 11},
    "run": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "bike": {"sportTypeId": 2, "sportTypeKey": "cycling", "displayOrder": 2},
    "swim": {"sportTypeId": 4, "sportTypeKey": "swimming", "displayOrder": 3},
}

STEP_TYPES = {
    "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery", "displayOrder": 4},
    "rest": {"stepTypeId": 5, "stepTypeKey": "rest", "displayOrder": 5},
    "repeat": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
}
END_TIME = {
    "conditionTypeId": 2,
    "conditionTypeKey": "time",
    "displayOrder": 2,
    "displayable": True,
}
END_DISTANCE = {
    "conditionTypeId": 3,
    "conditionTypeKey": "distance",
    "displayOrder": 3,
    "displayable": True,
}
END_REPS = {
    "conditionTypeId": 10,
    "conditionTypeKey": "reps",
    "displayOrder": 10,
    "displayable": True,
}
END_ITERATIONS = {
    "conditionTypeId": 7,
    "conditionTypeKey": "iterations",
    "displayOrder": 7,
    "displayable": False,
}
NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}
PACE_TARGET = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 1}
KILOGRAM = {"unitId": 8, "unitKey": "kilogram", "factor": 1000.0}


def _step(order: int, kind: str, end: dict[str, Any], value: float) -> dict[str, Any]:
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": order,
        "stepType": STEP_TYPES[kind],
        "endCondition": end,
        "endConditionValue": float(value),
        "targetType": NO_TARGET,
    }


def _workout(
    sport: str, spec: dict[str, Any], steps: list[dict[str, Any]], with_author: bool
) -> dict[str, Any]:
    workout: dict[str, Any] = {
        "workoutName": spec["name"],
        "sportType": GARMIN_SPORT[sport],
        "estimatedDurationInSecs": spec.get("estimated_duration_secs", 0),
        "workoutSegments": [
            {"segmentOrder": 1, "sportType": GARMIN_SPORT[sport], "workoutSteps": steps}
        ],
    }
    if with_author:
        workout["author"] = {}
    return workout


def build_strength(spec: dict[str, Any]) -> dict[str, Any]:
    """Силовая. spec: name, estimated_duration_secs, exercises (category, exercise — коды
    каталога Garmin, sets, reps или seconds (ровно одно: повторы или статика на время),
    rest_seconds, weight_kg). Упражнение — группа повторов: подход и отдых."""
    steps: list[dict[str, Any]] = []
    order = 1
    for item in spec["exercises"]:
        if ("seconds" in item) == ("reps" in item):
            raise ValueError("у упражнения должно быть ровно одно из reps / seconds")
        if "seconds" in item:
            work = _step(order + 1, "interval", END_TIME, item["seconds"])
        else:
            work = _step(order + 1, "interval", END_REPS, item["reps"])
        work["category"] = item["category"]
        work["exerciseName"] = item["exercise"]
        work["weightValue"] = float(item["weight_kg"])
        work["weightUnit"] = KILOGRAM
        rest = _step(order + 2, "rest", END_TIME, item["rest_seconds"])
        group = _step(order, "repeat", END_ITERATIONS, item["sets"])
        group["type"] = "RepeatGroupDTO"
        del group["targetType"]
        group["numberOfIterations"] = item["sets"]
        group["workoutSteps"] = [work, rest]
        group["smartRepeat"] = False
        steps.append(group)
        order += 3
    return _workout("strength", spec, steps, True)


def build_stretch(spec: dict[str, Any]) -> dict[str, Any]:
    """Растяжка (mobility). spec: name, estimated_duration_secs, steps (exercise — код
    WARM_UP/STRETCH_* каталога Garmin, seconds, description — техника по-русски, заметка)."""
    steps: list[dict[str, Any]] = []
    for order, item in enumerate(spec["steps"], start=1):
        step = _step(order, "interval", END_TIME, item["seconds"])
        step["description"] = item["description"]
        step["category"] = "WARM_UP"
        step["exerciseName"] = item["exercise"]
        steps.append(step)
    return _workout("mobility", spec, steps, False)


def build_endurance(sport: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Бег / вело / плавание. spec: name, estimated_duration_secs, steps: type
    (warmup/interval/recovery/cooldown/rest) и seconds или meters; необязательно
    pace_sec_per_km [медленнее, быстрее] — цель по темпу."""
    steps: list[dict[str, Any]] = []
    for order, item in enumerate(spec["steps"], start=1):
        if "meters" in item:
            step = _step(order, item["type"], END_DISTANCE, item["meters"])
        else:
            step = _step(order, item["type"], END_TIME, item["seconds"])
        if "pace_sec_per_km" in item:
            slow, fast = item["pace_sec_per_km"]
            step["targetType"] = PACE_TARGET
            step["targetValueOne"] = 1000 / slow
            step["targetValueTwo"] = 1000 / fast
        steps.append(step)
    return _workout(sport, spec, steps, True)


def build_workout(sport: str, spec: dict[str, Any]) -> dict[str, Any]:
    """JSON тренировки Garmin по виду спорта (strength/mobility/run/bike/swim) и spec."""
    if sport == "strength":
        return build_strength(spec)
    if sport == "mobility":
        return build_stretch(spec)
    if sport in SPORTS:
        return build_endurance(sport, spec)
    raise ValueError(f"неизвестный вид спорта: {sport}")


def _pace(mps: float) -> str:
    """Скорость м/с -> мин:сек на км."""
    seconds = round(1000 / mps)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _step_line(step: dict[str, Any], indent: str) -> str:
    kind = step["stepType"]["stepTypeKey"]
    end = step["endCondition"]["conditionTypeKey"]
    value = step["endConditionValue"]
    unit = {"time": "с", "distance": "м", "reps": "повторов"}[end]
    parts = [f"{indent}{kind}: {value:g} {unit}"]
    if step.get("exerciseName"):
        parts.append(f"{step['category']}/{step['exerciseName']}")
    if step.get("weightValue") is not None:
        parts.append(f"{step['weightValue']:g} кг")
    if step.get("targetValueOne") is not None:
        parts.append(f"темп {_pace(step['targetValueOne'])}-{_pace(step['targetValueTwo'])}/км")
    if step.get("description"):
        parts.append(f"заметка: {step['description']}")
    return ", ".join(parts)


def describe_workout(workout: dict[str, Any]) -> str:
    """Читаемый текст того, что уйдёт в Garmin: шаги, повторы, веса, заметки."""
    lines = [f"{workout['workoutName']} ({workout['sportType']['sportTypeKey']})"]
    for segment in workout["workoutSegments"]:
        for step in segment["workoutSteps"]:
            if step["type"] == "RepeatGroupDTO":
                lines.append(f"  повторить {step['numberOfIterations']} раз:")
                lines += [_step_line(s, "    ") for s in step["workoutSteps"]]
            else:
                lines.append(_step_line(step, "  "))
    return "\n".join(lines)
