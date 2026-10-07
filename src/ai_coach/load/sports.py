"""Виды спорта: соответствие typeKey активности Garmin и вида спорта плана."""

SPORT_TYPE_KEYS = {
    "run": ("running", "treadmill_running", "trail_running", "track_running", "virtual_run"),
    "bike": (
        "cycling",
        "indoor_cycling",
        "road_biking",
        "mountain_biking",
        "gravel_cycling",
        "virtual_ride",
    ),
    "swim": ("lap_swimming", "open_water_swimming", "swimming"),
    "strength": ("strength_training",),
}

# Растяжка в TSS не считается. Точные typeKey на часах не проверены (см. шаг 7), берём вероятные.
MOBILITY_TYPE_KEYS = ("yoga", "pilates", "stretching", "mobility", "flexibility_training")


def sport_of(type_key: str) -> str | None:
    """Вид спорта по typeKey; незнакомый typeKey — None."""
    for sport, keys in SPORT_TYPE_KEYS.items():
        if type_key in keys:
            return sport
    return None
