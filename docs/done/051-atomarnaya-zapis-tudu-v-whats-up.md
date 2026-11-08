# 51. Атомарная запись туду в whats-up
status: done
priority: low
updated: 2026-11-08

Находка папы-кабана в docs/plan-n21.md: `~/.claude/skills/whats-up/todo.py` пишет `~/.claude/todo.json` не атомарно
(`open(path, "w")`); обрыв записи оставит битый JSON, тренер и `coach sync` упадут на `TodoError`. Правка —
через skill-intake.

## Закрыто

Шаг Н25, 2026-11-08. Правка вне репо через skill-intake: `~/.claude/skills/whats-up/todo.py`, функция `save` —
`mkstemp` + `fsync` + `os.replace`, права файла сохраняются; +2 теста в `test_todo.py` (5 из 5 зелёные); строка в
`registry.md`; бэкап `~/.claude/backups/skills-agents-20261108-1513`. Документа шага нет: цепочки кабанов не было
(ROADMAP Н25, Р5 = 1).
