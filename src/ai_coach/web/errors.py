"""Ошибки отметок пульта (общие для marks и food)."""


class MarkError(ValueError):
    """Отметку нельзя записать; текст - пользователю."""


class NoEvent(MarkError):
    """Пункта нет (или он отменён)."""
