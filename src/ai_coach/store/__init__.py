"""store: SQLite без ORM, SQL-миграции в пакете.

Договорённости (импорт из подмодулей, например `from ai_coach.store.db import open_db`).
Все значения — dict[str, Any] с именами колонок из migrations/0001_init.sql; строки
возвращаются как dict[str, Any] (None, если записи нет). Даты/время — ISO-строки,
диапазоны start..end — включительно. Функции записи НЕ делают commit: вызывающий
оборачивает в `with conn:`. Поля `raw_json` и `*_json` можно передавать объектом
(dict/list) — сохраняется JSON-строкой; читаются как строка.

Подмодули: db (открытие, миграции, помощники), garmin_data, goals, plans, journal.
Путь к БД: явный путь > $AI_COACH_DB > ~/.local/share/ai-coach/coach.db.
"""
