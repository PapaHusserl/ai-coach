# Handoff — где остановились

**Обновлено:** 2026-10-27.

## Где мы

- Шаг 24 «Микронутриенты» ✅ (BACKLOG 6 → done/006), закрыт 2026-10-27 — [plan-24-micronutrients.md](plan-24-micronutrients.md). Итог тестя: смета $9–17 → факт $10,22.
- v2.8 ✅; секция `[screen]` уже в `~/.config/ai-coach/workload.toml`, осталась ручная проверка Влада.
- Следующий по ROADMAP — шаг 25 «Smells» (BACKLOG 8), документа шага ещё нет.

## Следующие 3 шага

1. Шаг 25 «Smells: `make check` в зелёный» (BACKLOG 8) — папа-кабан пишет `docs/plan-25-smells.md`.
2. Долг v2.8 — ручная проверка Влада: `coach sync`, `тренер вечер` с подсказкой экрана.
3. v2.9 «Калибровка весов и порогов перегруза» (BACKLOG 3).

## Открытые вопросы

- Можно потом (ревью шага 23): `seconds: null/0` проходит проверку ключа в `build_strength`.

## Что важно помнить

- Разметка календарей и экрана — `~/.config/ai-coach/workload.toml` (вне репо).
- Тесты: `uv run pytest -q` и `node --test "tests/player/*.test.mjs"`; `make smells` красный и на HEAD — шаг 25.
- После правок MCP-схемы — перезапустить MCP-сервер, иначе живёт старая схема.
- Репо публичное: личные данные — только в базе и `spikes/out/` (в .gitignore); названия приложений и окон в репо не пишутся.

## Ссылки

- Документ шага: [plan-24-micronutrients.md](plan-24-micronutrients.md); журнал — [pipeline.md](pipeline.md).
- Последний коммит: 6f08f99 (закрытие шага 24). Правила: AGENTS.md, docs/RULES.md.
- Отклик: `~/projects/semia-kabanov/otkliki/orkestrator/ai-coach/2026-10-27-24.md`.
