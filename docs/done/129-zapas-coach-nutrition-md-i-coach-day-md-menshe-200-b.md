# 129. Запас coach-nutrition.md и coach-day.md меньше 200 Б
status: done
priority: low
updated: 2026-11-26

Находка архитектора при закрытии П12 (`wc -c` против `tests/text_limits.py`): `coach-nutrition.md` 6033 из 6144
(запас 111 Б), `coach-day.md` 6008 из 6144 (136 Б) — ниже 200 Б из местного правила AGENTS.md; следующий шаг,
что их правит, выносит текст в боковой файл.

## Закрыто

Шаг Н48, 2026-11-26 — docs/plan-n48.md. `coach-day.md` — вынос в боковой файл `.claude/agents/coach-day/`, 5537 Б
(`wc -c` 2026-11-26), сторож запаса — `tests/test_skills_text.py`. `coach-nutrition.md` к шагу уже 5734 Б, запас
410 (вынос П8) — в Н48 не правился (docs/plan-n48.md, «Побочные находки» п. 5). Общий сторож — BACKLOG 196.
