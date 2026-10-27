"""workload: нагрузка вне тренировок - календарь, туду, груминг, экран. Запись НЕ делает commit."""

from ai_coach.workload.calendar_eventkit import CalendarError, CalendarReader, EventReader
from ai_coach.workload.config import (
    WorkloadConfig,
    WorkloadConfigError,
    default_config,
    load_config,
)
from ai_coach.workload.grooming import GroomingError, read_grooming
from ai_coach.workload.screen import AwReader, ScreenError, ScreenReader, read_screen
from ai_coach.workload.service import AHEAD_DAYS, workload_day, workload_series
from ai_coach.workload.todo import TodoError, read_todo

__all__ = [
    "AHEAD_DAYS",
    "AwReader",
    "CalendarError",
    "CalendarReader",
    "EventReader",
    "GroomingError",
    "ScreenError",
    "ScreenReader",
    "TodoError",
    "WorkloadConfig",
    "WorkloadConfigError",
    "default_config",
    "load_config",
    "read_grooming",
    "read_screen",
    "read_todo",
    "workload_day",
    "workload_series",
]
