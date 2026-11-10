# Handoff — где остановились

**Обновлено:** 2026-11-11.

## Где мы

- Шаг Н27 закрыт ✅ — [plan-n27.md](plan-n27.md): тест `coach event list` замораживает «сегодня»
  через `fake_clock.freeze` (BACKLOG 70).
- Полный pytest зелёный, 4 мин (`uv run pytest -q`; `tests/run.sh` в проекте нет).
- Итог тестя: смета 5,4–8,5 $ → факт 4,97 $.

## Следующие 3 шага

1. Н24.
2. Н28 (BACKLOG 68).
3. П5 (BACKLOG 71, 72). Порядок — по ROADMAP архитектора.

## Открытые вопросы

- Бэкапы `~/.local/share/ai-coach/coach.db.bak-20261110-testleak` и `-testleak2` — Влад оставил (окно 2026-11-10);
  фейк удалён Владом, строки 21:08 — его.
- П5 (BACKLOG 71, 72): объём 72 — только смотреть события не тренера или ещё и править — решает Влад.
- `make smells` на HEAD 5 при пороге 0 (BACKLOG 58); повторы в `coach event list` (BACKLOG 57).
- Тексты тренера у края: `coach.md` 16301/16384, `coach-day.md` 6142/6144 (BACKLOG 56).
- Ручные проверки прошлых шагов (Н15–Н23, П1–П3) — «Открыто» их документов.
- Долги mutmut: Н2, Н13, Н11 п1, Н12, Н5, Н16, Н21 (`workload/todo.py`); Н18 — 50 выживших в `day_plan.py`.
- Кандидаты беклога: `find_deviations` `sleep>0` у OFF_WRIST (Н4); `(?i)` в `title_regex` (Н3).
- В `tests/test_mcp_read.py:137,141` есть значения веса — если реальный, заменить мини-задачей.
- Без ответа Влада: `uv tool install -e` для `coach`.
- Отклики Н5, Н15–Н23, П1–П4, Н27 в semia-kabanov не закоммичены — по команде Влада.

## Что важно помнить

- Разметка календарей и экрана — `~/.config/ai-coach/workload.toml` (вне репо).
- Транскрипты Claude Code живут 30 дней (`cleanupPeriodDays`) — sync сохраняет счётчики в базу.
- Тесты: полный pytest 4 мин (замер Н27), cov 33 мин; mutmut шага — `HOME=<scratchpad>/fakehome`,
  `rm -rf mutants` перед запуском, `--max-children 4`; 46–81 мин по нагрузке.
- После правок MCP-схемы — перезапустить MCP-сервер; субагентам нужна новая сессия.
- Репо публичное: личные данные — только в базе и `spikes/out/`; названия приложений и окон в репо не пишутся.
- metrics.py `--from` — UTC; местное время +05.

## Ссылки

- Документ шага: [plan-n27.md](plan-n27.md); журнал — [pipeline.md](pipeline.md).
- Последний коммит: 6f06d64 (закрытие Н27); metrics.py: 5,05 $. Правила: AGENTS.md, docs/RULES.md.
- Отклик: `~/projects/semia-kabanov/otkliki/orkestrator/ai-coach/2026-11-11-n27.md`.
