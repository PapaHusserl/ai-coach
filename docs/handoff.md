# Handoff — где остановились

**Обновлено:** 2026-10-19.

## Где мы

- v1 и v2 (v2.0–v2.6) закрыты; идёт **v2.7 — спайк экранного времени** (Mac, ActivityWatch).
- Фаза А закрыта. Фаза Б — код готов (ревью, аудит, пуш 503ddad): `spikes/screen/aw_day.py --date`, `spikes/screen/aw_compare.py --days N`; решения Влада 7–11 — в docs/plan-v2.md «Шаг v2.7».
- cmux (61 % дня) делится на work/hobby по заголовку окна внутри aw-server (a29b7fc, решения 12–18): `[title."cmux"]` в `spikes/out/screen_rules.toml`, `--titles cmux` / `--apps` — только в tty. Стартовые regex `/msa` → work, `/projects` → hobby пока не ловят ничего (100 % «без правила»).

## Следующие 3 шага

1. Влад в своём терминале: `uv run python spikes/screen/aw_day.py --date <день> --titles cmux` → есть ли путь в заголовках → поправить title-regex (work+hobby+regex ≤ ~15, браузер вне лимита; «без правила» ≤ 20 %, иначе откат к «по app»).
2. Ручные замеры: CPU/батарея AW, размер базы AW, afk при блокировке экрана; прогон `aw_compare --days 7`.
3. Отчёт `docs/spike-screen-<дата>.md` (без названий окон, приложений, hostname) → вердикт по критериям «Годится/Не годится» → закрытие v2.7. Потом в закромах — калибровка весов перегруза.

## Открытые вопросы

- Ручных часов `coach feel --work` пока мало (2 будня) — для сравнения ±1 ч нужно больше дней.
- Решение (4) про браузер (доля / делить) — по цифрам после фазы Б.

## Что важно помнить

- Разметка календарей — `~/.config/ai-coach/workload.toml` (вне репо). Названия сравнивать по `strip()`.
- `sync_log kind='workload'`, не `sync`. Названия событий — только `get_workload(events=true)` на один день.
- `aw_compare` импортирует приватные `_counted/_clip/_hours` из `workload.service` — допустимо только для спайка.
- Тесты изолированы autouse-фикстурой в `tests/conftest.py`. Репо публичное: личные данные — только в базе и `spikes/out/` (в .gitignore).
- Вопросы Владу — через AskUserQuestion; решения за него не принимать.

## Ссылки

- Документ шага: [plan-v2.md](plan-v2.md) «Шаг v2.7»; журнал — [pipeline.md](pipeline.md).
- Последний коммит: 9b6ded7. Правила: AGENTS.md, docs/RULES.md.
