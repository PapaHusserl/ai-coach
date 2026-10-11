"""agenda: события тренера в календаре - черновики, проверка, переходы статусов.

Запись в календарь (calendar_write.CalendarWriter) здесь не импортируется: MCP-сервер берёт
отсюда только черновики и чтение.
"""

from ai_coach.agenda.service import (
    AgendaError,
    agenda_rows,
    cancel_event,
    create_draft,
    remove_event,
    validate_draft,
    write_event,
)

__all__ = [
    "AgendaError",
    "agenda_rows",
    "cancel_event",
    "create_draft",
    "remove_event",
    "validate_draft",
    "write_event",
]
