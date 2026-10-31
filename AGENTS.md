# ai-coach

Правила ведения docs/ROADMAP.md, docs/BACKLOG.md, docs/handoff.md, docs/done/ и гигиены репо — @docs/RULES.md

Общие практики проектов — @~/projects/dashboard/priv/scaffold/COMMON.md

## Местные правила

- `docs/pipeline.md` — журнал партий, строка на партию: проекту нужна сводка этапов в одном файле (решение Влада
  2026-10-26).
- Новая или изменённая функция тренера (команда CLI, MCP-инструмент, скил, вопрос чек-ина, шкала) — правка
  `.claude/agents/coach-help.md` и `coach-help/` в том же шаге; план шага без пункта «Справка» неполный; полноту
  имён держит `tests/test_skills_help.py` (план Н14 «Правило», принят Владом 2026-10-31).
