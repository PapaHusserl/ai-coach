# 57. Повторы по дням в `coach event list` и MCP `get_agenda`
status: done
priority: medium
updated: 2026-11-25

`agenda_rows` (`agenda/service.py:277`) отдаёт активные серии с исходной датой, без раскладки по дням: weekly-
чек-ин виден в списке любого дня. Пульт П1 фильтрует сам (`web/day.py`); раскладка для CLI и MCP — видимое,
решает Влад (docs/plan-p1.md «Правки по ревью» п.1).

## Закрыто

Шаг Н36, 2026-11-25 — docs/plan-n36.md.
