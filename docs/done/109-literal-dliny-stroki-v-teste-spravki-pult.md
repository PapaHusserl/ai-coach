# 109. Литерал длины строки в тесте справки pult
status: done
priority: low
updated: 2026-11-15

Находка папы-кабана при плане Н40 (docs/plan-n40.md, «Побочные находки» 1):
`test_pult_topic_links_pult_todo_within_limit` (`tests/test_skills_help.py:217`) держит длину строки литералом
`338` — лимит вне `tests/text_limits.py`, чей докстринг называет файл единственным местом лимитов.

## Закрыто

Шаг П12 (партия 1), 2026-11-15 — docs/plan-p12.md.
