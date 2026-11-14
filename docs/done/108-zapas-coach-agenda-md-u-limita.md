# 108. Запас coach-agenda.md у лимита
status: done
priority: low
updated: 2026-11-14

Находка папы-кабана при закрытии П11 (docs/plan-p11.md, «Риски» 11, «Правки по ревью», партия 3):
`.claude/agents/coach-agenda.md` — 8037 Б при лимите 8192 (`tests/text_limits.py:9`), запас 155 Б. Следующая
правка текста напоминаний упрётся в лимит.

## Закрыто

Шаг Н41, 2026-11-14 — docs/plan-n41.md.
