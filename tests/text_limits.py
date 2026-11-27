"""Лимиты размера текстов тренера (байты): единственное место, где они записаны."""

AGENT_LIMITS = {
    "coach.md": 18432,
    "coach-wellbeing.md": 11264,
    "coach-nutrition.md": 6144,
    "coach-onboarding.md": 6144,
    "coach-week.md": 6144,
    "coach-agenda.md": 8192,
    "coach-day.md": 6144,
    "coach-decisions.md": 6144,
    "coach-help.md": 8192,
}
RESERVE = 200
SKILL_LIMIT = 4096
EVENING_SKILL_LIMIT = 5120
SIDE_FILE_LIMIT = 4096
HELP_INDEX_LIMIT = AGENT_LIMITS["coach-help.md"]
HELP_TOPIC_LIMIT = 8192
PULT_TODO_LINK_LIMIT = 338
