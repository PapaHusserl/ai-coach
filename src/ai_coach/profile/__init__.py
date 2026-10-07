"""profile: профиль спортсмена (журнал ключ-значение) и расчёт КБЖУ.

Ручное значение главнее Garmin. Функции записи НЕ делают commit (как в store).
"""

from ai_coach.profile.nutrition import nutrition
from ai_coach.profile.service import (
    current_profile,
    profile_history,
    profile_nutrition,
    resting_hr,
    set_value,
)

__all__ = [
    "current_profile",
    "nutrition",
    "profile_history",
    "profile_nutrition",
    "resting_hr",
    "set_value",
]
