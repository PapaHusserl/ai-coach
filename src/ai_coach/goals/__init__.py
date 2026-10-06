"""goals: цели пользователя, фазы (proposed/accepted) и история изменений целей.

Договорённости: функции записи НЕ делают commit (как в store). Время — ISO-строка,
`now` — ISO-строка (для проверок и переноса задним числом), иначе текущее местное.
Цели не удаляются: закрытие — статус done/cancelled.
"""

from ai_coach.goals.service import (
    accept_phase,
    create_goal,
    get_goal,
    get_phase,
    goal_history,
    goals_on,
    list_goals,
    list_phases,
    phases_on,
    propose_phase,
    reject_phase,
    update_goal,
    update_phase,
)

__all__ = [
    "accept_phase",
    "create_goal",
    "get_goal",
    "get_phase",
    "goal_history",
    "goals_on",
    "list_goals",
    "list_phases",
    "phases_on",
    "propose_phase",
    "reject_phase",
    "update_goal",
    "update_phase",
]
