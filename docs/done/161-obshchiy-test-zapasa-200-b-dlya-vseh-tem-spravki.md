# 161. Общий тест запаса 200 Б для всех тем справки
status: done
priority: medium
updated: 2026-11-27

В `tests/test_skills_help.py` тест запаса 200 Б (правило AGENTS.md) есть только у `coach-help.md` и `sleep.md`;
остальные `coach-help/*.md` его не стерегут — `wellbeing.md` дошёл до запаса 132 Б без красного теста. Идея — один
параметризованный тест по всем файлам `coach-help/*.md`. Находка папы — `docs/plan-n38.md`, партия 2.

## Закрыто

Шаг Н51, 2026-11-27 — [plan-n51.md](../plan-n51.md).
