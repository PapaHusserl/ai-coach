# Шаг 25. Smells: `make check` в зелёный

Закрывает BACKLOG 8. План — папа-кабан, 2026-10-27. Режим «встроить»: только рефакторинг, поведение не меняется.
Разведка на HEAD e7e7ab9.

## Суть

`make check` красный одной целью — `smells`: `qlty smells --all` даёт 4 находки сложности при `SMELLS_MAX ?= 0`
(Makefile, строка 3). Остальные цели на HEAD зелёные: `lint` («All checks passed», 269 файлов отформатированы),
`types` (pyright 0 ошибок), `dead` (vulture пусто), `player-test` (54 JS-теста). `cov` (3150 тестов, порог
`fail_under = 94`) я не прогонял — тяжёлый прогон, окно Влада; по plan-24 «Правки по ревью» п. 13 гейт партии 5
с pytest зелёный — ожидание: зелёный, не проверено.

Инструмент: qlty 0.651.0 (2026-10-01), конфиг `.qlty/qlty.toml` — свой порог только у `function_parameters = 15`
(шаг 19а, решение Влада 2026-10-08, pipeline.md). Пороги сложности — умолчания qlty (`qlty config show`):
`file_complexity.threshold = 50`, `function_complexity.threshold = 18`. Проверка строгая — `count >= threshold`
(`qlty-smells/src/structure/checks/file_complexity.rs`), то есть цель: файл ≤ 49, функция ≤ 17. Метрика —
когнитивная сложность (`qlty metrics --functions`, столбец `cognitive`); сумма по файлу считается своим
обходом (у main.py сумма функций 55 при count 54, у tools.py 53 при 51) — итог проверяется только `make smells`.

**Правило:** новое правило нет; инструментальные пороги не меняются (при Р1 = рефакторинг): `SMELLS_MAX ?= 0`,
`file_complexity 50`, `function_complexity 18` — как есть.
**Поведение:** не меняется — вывод CLI, ответы MCP, тексты ошибок конфига, строка итога `coach sync` и порядок
замечаний в ней байт в байт; команды `coach profile|goal` и инструмент `get_morning_snapshot` остаются под теми
же именами.
**Вне репо:** нет.

## Решения

Влад, 2026-10-27: умолчания 1–6 приняты; Р1 = (1) рефакторинг, пороги как есть; Р2 = А (`cli/profile.py`);
Р3 = А (`mcp_server/snapshot.py`). Одна партия.
Влад, 2026-10-27 (окно после хэнд-бэка кабана, рекомендация папы): умолчание «приватные `tools._x` без
переименований» заменено — `_day`/`_shift`/`_day_deviations`/`_now`/`_today` в tools публичные (`parse_day`,
`shift_day`, `day_deviations`, `now`, `today`), подавления pyright убрать.

## Находки и как разводить

Цифры `cognitive` — измерены `qlty metrics --functions` на HEAD; цифры «после» — ожидание, не проверено.

### 1. `src/ai_coach/cli/main.py` — сложность файла 54 (нужно ≤ 49)

Вклад функций: `status` 12, `import_` 6, `push` 6, `login` 5, `feel` 5, `screen` 5, `goal_list` 4, `sync` 2,
`parse_hours` 2, `profile_show` 2, `goal_add` 2, по 1 — `approve_`, `link`, `profile_set`, `close_goal`. Упрощение
внутри файла (например, вынос разбора дат из `status` в helper) сумму файла не снижает — нужно выносить код.
Прецедент: `cli/` уже разрезан по доменам (`journal.py`, `pantry.py`, `habits.py`, `meds.py`, …), main.py только
регистрирует под-приложения `add_typer`.

- Вариант А (рекомендую): новый `src/ai_coach/cli/profile.py` — `profile_app`, `goal_app` и их команды
  `profile_show`, `profile_set`, `goal_add`, `goal_list`, `close_goal`, `goal_done`, `goal_cancel` (суммарно 10);
  main.py: `from ai_coach.cli.profile import goal_app, profile_app`, `add_typer` остаются. `fail`, `now`,
  `check_date` — импорт из `cli/journal.py` (там они уже есть, main уже берёт оттуда `check_date`). Ожидание
  54 → 44. Тесты не правятся: `tests/test_cli_profile.py` зовёт команды через `main.app` и патчит только
  `main.load_client` (no_network) — остаётся валидным; vulture уже знает `@profile_app.command*`,
  `@goal_app.command*` (pyproject `ignore_decorators`).
- Вариант Б: `cli/wellbeing.py` — `feel`, `screen`, `parse_hours`, `MIN_SCORE`/`MAX_SCORE`/`MAX_HOURS`,
  `SCREEN_LABELS` (12). Минус: `tests/test_cli_screen.py:43` патчит `main.AwReader` — правка теста.
- Вариант В: поднять `[smells.file_complexity] threshold` в `.qlty/qlty.toml` (прецедент — параметры 15 в
  шаге 19а). Минус: main.py растёт с каждым шагом (новая команда — новая строка), порог отложит, не решит;
  долг по порогам уже лежит в BACKLOG 2.

### 2. `src/ai_coach/mcp_server/tools.py` — сложность файла 51 (нужно ≤ 49)

Вклад: `morning_snapshot` 10, `_clean` 7, `save_food_nutrition` 7, `cap` 5, `_hr_params` 5,
`create_draft_workout` 4, по 2 — `period`, `profile`, `cancel_draft_workout`, остальное 0–1. Прецедент: инструменты
уже вынесены по доменам «отдельно от tools.py из-за размера» — `review.py`, `variety.py`, `habits.py`,
`agenda.py`, `workload.py`, `overload.py`, `links.py`; они берут `tools.cap`, `tools.period`, `tools.load`;
server.py держит карту имя → функция (`server.py:38–309`).

- Вариант А (рекомендую): новый `src/ai_coach/mcp_server/snapshot.py` — `morning_snapshot` (+ вложенный `part`),
  `_snapshot_profile`, `_snapshot_nutrition`, `_snapshot_meds`, `_snapshot_habits` и константы только снапшота:
  `SNAPSHOT_*` (8 штук), `WELLBEING_DAYS`, `WORKLOAD_AHEAD_DAYS`, `AGENDA_BACK_DAYS`, `AGENDA_AHEAD_DAYS`,
  `AGENDA_FIELDS`, `AHEAD_SKIP`, `NOT_LISTS`, `DATE_SERIES`. Из tools — `tools.cap`, `tools.load`,
  `tools._day`, `tools._shift`, `tools._day_deviations`, `tools._now`, `tools._today`, `tools.MAX_CHARS`
  (стиль `tools.x` как в `review.py`/`variety.py`). server.py: `snapshot.morning_snapshot` в строке 41, импорт
  модуля. Ожидание 51 → 39; snapshot.py ≈ 12. Снапшот — функция, растущая каждым шагом (новая фича — новый
  ключ): её вынос даёт запас обоим файлам. Правка тестов — только импорт констант в трёх файлах:
  `tests/test_mcp_profile.py` (`SNAPSHOT_ROWS`), `tests/test_mcp_supplement_log.py` (`SNAPSHOT_CHARS`),
  `tests/test_mcp_snapshot.py` (`SNAPSHOT_CHARS`, `SNAPSHOT_ROWS`) — `MAX_CHARS` остаётся в tools; остальные
  тесты держат свои локальные константы (`SNAPSHOT_MEDS_ROWS` и т. п.) и вызывают инструмент через
  `mcp_fakes.call` → не трогаются.
- Вариант Б: `mcp_server/write.py` — `create_draft_workout`, `save_food_nutrition`, `check_groups`,
  `cancel_draft_workout`, `propose_phase`, `MAX_NUTRITION`, `WEEKEND_ONLY_SPORT`, `SATURDAY` (15; 51 → 36).
  Минус: `variety.py:49` берёт `tools.check_groups`, `tests/test_cli_link.py` импортирует
  `create_draft_workout`/`cancel_draft_workout` из tools — две правки; снапшот остаётся в tools и снова упрётся
  в 50 через 1–2 шага.
- Вариант В: порог вверх — как в п. 1.

### 3. `src/ai_coach/sync/workload_sync.py: sync_workload` — функция 19 (нужно ≤ 17)

Вся сложность — три источника с `try/except` подряд и ветки `if config is None` / `if config.screen is None`.
В файле уже есть вынесенные части (`coach_part`, `read_calendar`) — продолжить в том же стиле:

- `resolve_config(config: WorkloadConfig | None, errors: list[str]) -> WorkloadConfig` — новая: `None` →
  `load_config()`, при `WorkloadConfigError` — `errors.append(str(e))` и `default_config()`.
- `read_counters(config, screen, first, today, notes, errors) -> list[dict[str, Any]]` — новая: туду, груминг,
  экран (`"экран не настроен"` в notes либо `read_screen` с `screen or AwReader(config.screen)`), порядок
  записей в `notes`/`errors` тот же, что сейчас (строки 157–176).
- `sync_workload` остаётся: окно, календарь, `summary`/`message`, транзакция. Ожидание 19 → ≈ 7.
- Не трогать `read_calendar`/`CalendarReader` — `tests/test_cli_sync_workload.py:45` патчит
  `workload_sync.CalendarReader`.
- Альтернатива (не рекомендую): таблица источников `(метка, вызов, класс ошибки)` и один цикл — компактнее, но
  меняет структуру сильнее ради тех же 2 пунктов.

### 4. `src/ai_coach/workload/config.py: _title_rules` — функция 19 (нужно ≤ 17)

Сложность — вложенные цикл по категориям + проверка кавычки + `try: re.compile`. Вынести тело цикла:

- `_title_patterns(cats: dict[str, Any], app: str, cat: str) -> list[str]` — новая: `_strings(cats, cat,
  f"screen.title.{app}.")`, проверка `'"'`, `re.compile(title_regex(patterns))` при непустом списке; тексты
  `WorkloadConfigError` переносятся как есть.
- `_title_rules`: цикл по приложениям, проверка таблицы и чужих ключей,
  `rules[app] = {cat: _title_patterns(cats, app, cat) for cat in TITLE_CATS}`. Ожидание 19 → ≈ 6, helper ≈ 6.

## Модули и функции

- `src/ai_coach/cli/main.py` — убрать `profile_app`, `goal_app` и 7 команд (строки 52–55, 355–453), импорт из
  `cli/profile.py`; docstring модуля не меняется (команды те же).
- `src/ai_coach/cli/profile.py` — новый (при Р2 = А).
- `src/ai_coach/mcp_server/tools.py` — убрать снапшот и его константы (строки 75–128 частично, 320–347, 392–494).
- `src/ai_coach/mcp_server/snapshot.py` — новый (при Р3 = А).
- `src/ai_coach/mcp_server/server.py:10, 41` — импорт `snapshot`, `snapshot.morning_snapshot`.
- `src/ai_coach/sync/workload_sync.py: sync_workload` (есть), `resolve_config`, `read_counters` — новые.
- `src/ai_coach/workload/config.py: _title_rules` (есть), `_title_patterns` — новая.
- `tests/test_mcp_profile.py:6`, `tests/test_mcp_supplement_log.py:7`, `tests/test_mcp_snapshot.py:7` — импорт
  `SNAPSHOT_*` из `ai_coach.mcp_server.snapshot` (при Р3 = А).
- `docs/architecture.md:178` — сигнатура `sync_workload(conn, days, today, reader, config)` уже отстала
  (нет `screen`); при желании дописать `screen` — правка одной строки, в объём шага не входит без «да».
- Не трогать: `.qlty/qlty.toml`, `Makefile`, `pyproject.toml` (при Р1 = рефакторинг); `README.md:41–42` — текст
  про `make check` верен.

## Партии

Объём: перенос ≈ 100 строк (cli/profile.py) + ≈ 150 строк (snapshot.py), новых строк кода ≈ 60 (три helper-а),
правка импортов в server.py и трёх тестах, 1–3 новых теста. Всё механическое, страховка — 3150 тестов.
Решение архитектора: одна партия — иначе две партии дадут два полных круга ревью/аудита на красном `make
check` (после первой smells всё равно останутся). Если Влад хочет меньше диффа на ревью — две: (1) п. 3–4
(внутри файлов), (2) п. 1–2 (новые модули); зелёный `make check` только после второй.

1. Кабан-доеба (TDD, до правок): тесты из раздела ниже, что отсутствуют — порядок замечаний `sync_workload` при
   нескольких сбоях, прямые тесты `resolve_config`/`read_counters`/`_title_patterns` (они новые — тесты после
   появления сигнатур, по плану).
2. Кабан: п. 3 и п. 4 — `make smells` показывает 2 находки (только файлы), pytest по `tests/test_workload_*.py`,
   `tests/test_cli_sync_workload.py` зелёный.
3. Кабан: п. 1 (при Р2) и п. 2 (при Р3), server.py, импорты тестов — `make smells` → `smells: 0 (max 0)`.
4. Гейт партии: `make check` целиком — `check: OK` (первый зелёный с 401c68b). Мутации (`make mutate`,
   фоном вне агента, по изменённым модулям — `MOD` в Makefile берёт их из `git diff`) — по желанию Влада, в
   `reports/mutmut.txt`.

## Тесты (кабан-доеба)

Существующие — страховка «поведение не меняется»:

- `coach profile|goal` — `tests/test_cli_profile.py` (через `main.app`): тексты «Не заполнено», «Целей нет»,
  «Цель N: done.» неизменны; проверено: файл есть, патчит только `main.load_client`.
- `get_morning_snapshot` — `tests/test_mcp_snapshot.py` (состав ключей, ужимание до `MAX_CHARS`, `NOT_LISTS`),
  `tests/test_mcp_snapshot_workload.py`, `tests/test_mcp_evening_after_midnight.py` (`freeze` из
  `tests/fake_clock.py` патчит `datetime`/`date` во всех модулях `ai_coach.*` — snapshot.py берёт время через
  `tools._now()`/`tools._today()`, поэтому попадает под подмену без правок), `tests/test_mcp_habits_today.py`,
  `tests/test_mcp_meds.py`, `tests/test_mcp_pantry*.py`, `tests/test_mcp_recipes.py`,
  `tests/test_mcp_sport_nutrition.py`, `tests/test_mcp_profile.py` — все зовут инструмент через `mcp_fakes.call`
  (сервер), на имени модуля не завязаны.
- `sync_workload` — `tests/test_workload_sync.py`, `tests/test_cli_sync_workload.py` (7 тестов),
  `tests/test_workload_sync_agenda.py`, `tests/test_workload_screen.py`, `tests/test_workload_robustness.py`,
  `tests/test_mcp_snapshot_workload.py` — через публичную `sync_workload(conn, days, today, reader, config,
  screen)` с `FakeCalendar`/`FakeAw` из `tests/workload_fakes.py`.
- `_title_rules` — `tests/test_workload_config.py:131–205`: чтение правил, один класс, регистр имени
  приложения, плохая regex (work и hobby), кавычка, чужой ключ, не список (параметризовано), приложение не
  таблица — все ветки helper-а.
- Импорт без EventKit — `tests/test_workload_import.py` импортирует `ai_coach.cli.main`, `ai_coach.mcp_server`,
  `ai_coach.sync.workload_sync` с заблокированным EventKit: новые модули не должны тянуть EventKit при импорте
  (они и не тянут — только store/ и tools).

Чего не хватает (добавить):

- `sync_workload` при одновременном сбое туду, груминга и экрана (битые пути + `FakeAw(error=ScreenError)`) и
  неразмеченном календаре → строка итога `событий 0, счётчиков 0; календарь не настроен; туду: …; груминг: …;
  экран: …` — порядок фиксируется до рефакторинга; «ожидание, не проверено» (сейчас проверяется только
  одиночное «экран не настроен», `tests/test_workload_sync.py:326`).
- `sync_workload` с `config=None` и битым toml по `AI_COACH_WORKLOAD_CONFIG` → в итоге первая запись ошибок —
  текст `WorkloadConfigError`, календарь пропущен («календарь не настроен»), туду/груминг читаются по путям по
  умолчанию. Теста этой ветки через `sync_workload` grep не нашёл (`WorkloadConfigError` в тестах sync не
  встречается; `tests/test_workload_robustness.py:42` проверяет только `load_config`) — добавить.
- Прямые: `_title_patterns({"work": ["a", "b"]}, "alpha", "work") == ["a", "b"]`; `{"work": ['a"b']}` →
  `WorkloadConfigError` «кавычка»; `{"work": ["("]}` → «плохая regex»; `{}` → `[]` без компиляции.
- Проверка руками (Влад, после партии): `make check` → `check: OK`; `coach profile show`, `coach goal list` —
  вывод как раньше; `тренер` → утренняя сводка приходит (снапшот живой через MCP).

Для mutmut (`модуль:функция`): `sync.workload_sync:sync_workload`, `sync.workload_sync:resolve_config` (новая),
`sync.workload_sync:read_counters` (новая), `workload.config:_title_rules`, `workload.config:_title_patterns`
(новая), `mcp_server.snapshot:morning_snapshot` (новая по месту), `cli.profile:goal_add` (новая по месту).

## Развилки

- **Р1. Принцип: рефакторинг или пороги.** (1) рефакторинг по пп. 1–4, пороги как есть; (2) поднять
  `file_complexity` (например 60) в `.qlty/qlty.toml` и рефакторить только функции пп. 3–4; (3) поднять оба
  порога, кода не трогать. Рекомендую (1): прецедент 19а был вынужденным (qlty не умеет порог по файлам для
  typer-команд), здесь же разрез по доменам — уже принятый стиль обоих пакетов; (2)–(3) оставят долг, который
  вернётся на следующем же шаге. Разблокирует всё остальное; решает Влад.
- **Р2. Как резать `cli/main.py`** (при Р1 = 1): (А) `cli/profile.py` — профиль и цели; (Б) `cli/wellbeing.py` —
  feel, screen. Рекомендую А: без правок тестов, запас 5 пунктов; Б — правка `test_cli_screen.py:43`.
- **Р3. Как резать `mcp_server/tools.py`** (при Р1 = 1): (А) `snapshot.py`; (Б) `write.py`. Рекомендую А —
  убирает из tools самую растущую функцию; правка импортов в трёх тестах против двух у Б, зато запас 10 вместо
  13 — и снапшот больше не давит на tools.

## Умолчания (внутреннее)

- Имена новых модулей и функций — как в разделе «Находки»; `cli/profile.py` берёт `fail`/`now`/`check_date` из
  `cli/journal.py`, свои копии не заводит (в main.py копии `fail`/`now` остаются — там их используют остальные
  команды; слияние дублей — не этот шаг).
- snapshot.py обращается к tools только через `tools.<имя>` (стиль `review.py`/`variety.py`, они берут лишь
  публичные `cap`/`period`/`check_groups`). Исправлено 2026-10-27 по вопросу кабана: pyright strict даёт
  `reportPrivateUsage` на `tools._day/_shift/_day_deviations/_now/_today` и `reportUnusedFunction` на `_now` —
  общие helper-ы делаем публичными, как в v2.1 сделали `cap`/`period` (pipeline.md, строка v2.1):
  `_day` → `parse_day`, `_shift` → `shift_day`, `_day_deviations` → `day_deviations`, `_now` → `now`,
  `_today` → `today` (имена `day`/`date` не брать — так зовут параметры и локальные в tools). Все вызовы в
  tools.py и snapshot.py — переименовать (18 мест в tools.py); директивы `# pyright: reportPrivateUsage=false`
  и `# pyright: ignore[reportUnusedFunction]` — убрать (файловых отключений pyright в `src/` нет, построчные
  — только для чужих библиотек и EventKit в `agenda/calendar_write.py:15–16`). Тесты приватные имена не
  импортируют (grep `tools._` по tests/ пуст); `fake_clock.freeze` подменяет `datetime`/`date` в tools —
  `now()`/`today()` под подменой остаются.
- Константы снапшота переезжают вместе с кодом (при Р3 = А); `MAX_CHARS`, `MAX_ROWS`, `MAX_DAYS` остаются в tools
  (их берут server.py и 9 тестов).
- Порядок записей в `notes`/`errors` `sync_workload` — неизменный, helper-ы дописывают в переданные списки.
- Одна партия; коммит после ревью и тестов, аудит по коммиту (память проекта).
- `docs/architecture.md` не правится: карта модулей там по пакетам (`cli/`, `mcp_server/`), файлы внутри не
  перечислены (`review.py`, `variety.py` тоже не упомянуты).

## Риски

- Сумма функций ≠ count файла у qlty (54 против 55, 51 против 53): после переноса реальная цифра может
  отличаться от ожидания на 1–2; критерий — `make smells`, не арифметика. Если main.py после А останется ≥ 50
  (маловероятно: ожидание 44) — добавить Б.
- Порог строгий (`>=`): цель ≤ 49 / ≤ 17, не «≤ 50 / ≤ 18».
- `fake_clock.freeze` подменяет время только в уже импортированных модулях `ai_coach.*`: snapshot.py должен
  импортироваться server.py на уровне модуля (так и будет — карта инструментов строится при импорте) и не
  импортировать `datetime` сам, а звать `tools._now()`/`tools._today()`.
- Циклов импорта нет: snapshot → tools, server → snapshot; profile → journal, main → profile. Обратных рёбер не
  заводить (tools не должен знать о snapshot, journal — о profile).
- `cov` на HEAD не прогонялся мной: если он красный по другой причине, шаг это вскроет на гейте — тогда
  отдельный разговор, в объём не входит.
- Строка pipeline.md про партию — по местному правилу AGENTS.md, пишет оркестратор.

## Открытые вопросы

1. Р1 — рефакторинг или пороги (блокирующий); решает Влад.
2. Р2, Р3 — варианты разреза; решает Влад, рекомендации А/А.

## Правки по ревью

Круг 1, 2026-10-28 (мама — можно мержить; свекровь — чисто):
- `_title_patterns` → `title_patterns` (workload/config.py), из теста убран `pyright: ignore` — кабан, по замечанию
  мамы (то же отмечала свекровь).
- tests/test_workload_sync.py: тест переименован в `test_broken_config_file_is_last_error_…` (ошибка конфига
  последняя, `parts[3]`); `test_all_sources_failing_…` пропускается под root (`skipif geteuid() == 0`) — доеба, по
  замечанию мамы.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план шага 25 (одна партия рефакторинга + гейт `make check`). Масштаб — по «Итогу» шага 24
(`docs/plan-24-micronutrients.md`, партия 5 «починка» — близкая по объёму механическая правка). Цены — тариф
metrics.py от 2026-10-25 (https://platform.claude.com/docs/en/about-claude/pricing, страницу не сверял); fable —
по ценам Opus. Модели — `grep -H '^model:' ~/.claude/agents/<роль>.md`: kaban sonnet, kaban-doeba sonnet,
mama-kaban opus, kaban-svekrov opus, kaban-test opus, svinopas opus, kaban-dekart fable; мой запуск — opus-5-5.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Подписки, API, хостинг, БД | 0 | qlty, pytest, pyright, vulture, mutmut — локальные, open-source | — | — | — |
| Прогон цепочки шага 25 (разово) | ~$7–12 за шаг | масштаб партии 5 шага 24 + перенос ~250 строк | Р1 = (3) пороги без кода: только kaban на конфиг | ~$4–6 | долг вернётся через 1–2 шага (снапшот растёт), правило «пороги как есть» нарушено |
| То же | | | две партии вместо одной | −$2–4 (дороже) | — не советую: два круга ревью/аудита |
| `make mutate` | 0 | локально, время машины | не запускать | 0 $ | только время |

| Партия | Время |
|---|---|
| 1. Тесты (doeba, TDD) | ~8–12 мин (шаг 24: doeba 8,0) |
| 2–3. Рефакторинг пп. 1–4 (kaban) | ~15–25 мин (шаг 24: 10 мин; здесь перенос двух модулей) |
| 4. Гейт `make check` (cov 3150 тестов) | ~5–10 мин машины, допущение |
| Ревью + аудит (мама, свекровь) | ~6–10 мин (шаг 24: 1,7 + 3,9) |
| Влад: проверка руками | ~5 мин |

| Роль | Модель | Токены (cache read / write / out) | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| papa-kaban (уже прошло) | fable | id в agents.md нет — интервал по шагу 24: 2–4M / 0,2–0,3M / 30–50K | 2–3,5 (интервал) |
| svinopas (уже прошло) | opus | id нет — интервал 0,3–1M / 0,05–0,1M / 5–10K | 0,4–1 (интервал) |
| kaban | sonnet | 4–7M / 0,2–0,35M / 30–50K | 1,2–2,2 |
| kaban-doeba | sonnet | 1–2M / 0,06–0,12M / 15–25K | 0,4–0,7 |
| mama-kaban | opus | 0,4–0,8M / 0,1–0,15M / 7–12K | 0,7–1,1 |
| kaban-svekrov | opus | 0,7–1M / 0,12–0,18M / 7–12K | 0,9–1,3 |
| orchestrator | opus | 6–10M / 0,3–0,4M / 30–40K | 3–4,5 |
| kaban-test (режим 3) | opus | 0,15M / 0,07M / 4K | ~0,45 |
| kaban-dekart | fable | 2 вызова (1 партия + сводный), выжимки до 400 KB ≈ 0,1M вход каждый | ~1–1,5 |
| **итого** | | | **~10–16** (без уже прошедшего ~$7–12) |

Дешевле по ролям: оркестратор — самая дорогая строка (~30–40 %); дешевле — /compact перед партией и ссылки на
файлы вместо пересказа (−$1–1,5), модель не меняем. kaban/doeba уже на sonnet; haiku на перенос кода — −$1, но
риск сломать порядок `notes`/`errors` и импорты под `fake_clock` — не советую. Ревью, аудит, маму, свекровь — не
трогаем. Вердикт: ок по бабкам, постоянных расходов нет; выбор Р1 влияет на деньги слабо (~$5), решать по долгу.

## Итог

- Закрыт BACKLOG 8 → docs/done/008-smells-vernut-make-check-v-zelenyj.md. Коммит 8437967 (партия 1, запушен);
  ревью и аудит чистые; `make check` → `check: OK` — первый зелёный с 401c68b.
- По плану: Р1 = рефакторинг, пороги как есть; Р2 = А (`cli/profile.py`); Р3 = А (`mcp_server/snapshot.py`);
  helper-ы tools публичные (решение 2). Отклонение: `_title_patterns` → `title_patterns` («Правки по ревью»).
- Проблемы: нет. Отложено (не в объёме, без «да»): `docs/architecture.md:178` — сигнатура `sync_workload` без
  `screen`.
- Стоимость — кабан-тесть, режим 3 (ниже).

**Источник токенов:** `metrics.py` по
`~/.claude/projects/-Users-vladislavahtamov-projects-ai-coach/54c04f63-675e-49ad-b941-0c7577e1b1f6.jsonl`;
**цены:** https://platform.claude.com/docs/en/about-claude/pricing, тариф metrics.py 2026-10-25 (страницу не
сверял — не проверено); fable — по ценам Opus.

| Партия | Смета | Факт |
|---|---|---|
| 1. Тесты (doeba) | ~8–12 мин | 5,0 мин (3,7 + 1,3); тестов меньше, чем ждали |
| 2–3. Рефакторинг (kaban) | ~15–25 мин | 26,3 мин (24,2 + 0,9 + 0,4 + 0,8); в пределах, 2 раза «ждёт свой фон» |
| 4. Гейт `make check` | ~5–10 мин | 2 мин 35 с (agents.md); cov быстрее допущения |
| Ревью + аудит | ~6–10 мин | мама 0,7 + свекровь 4,2 ≈ 5 мин; 2 круга ревью и 3 аудита всё равно короче сметы |
| Влад: проверка | ~5 мин | интервал 20:58–10:23, в т. ч. простой (ожидание 660 мин); время Влада не выделить |

| Роль | Модель | Токены (cache read / write / out) | $ |
|---|---|---|---|
| orchestrator | opus-5-5 | 9,11M / 0,46M / 37K | 4,89 (на момент подсчёта 06:58 UTC; смета 3–4,5) |
| papa-kaban | fable | 3,04M / 0,51M / 48K | 4,12 (смета 2–3,5; 3 сегмента вместо 1) |
| kaban | sonnet-5-5 | 2,64M / 0,36M / 30K | 1,45 (смета 1,2–2,2) |
| kaban-doeba | sonnet-5-5 | 0,77M / 0,10M / 9K | 0,43 (смета 0,4–0,7) |
| mama-kaban | opus-5-5 | 0,45M / 55K / 7K | 0,50 (смета 0,7–1,1) |
| kaban-svekrov | opus-5-5 | 0,81M / 52K / 13K | 0,68 (смета 0,9–1,3) |
| kaban-test | opus-5-5 | 0,13M / 66K / 3K | 0,42 (на момент подсчёта 06:58 UTC) |
| svinopas | opus | не запускался | 0 (смета 0,4–1) |
| kaban-dekart | fable | пока не запускался | 0 (смета ~1–1,5) |
| **итого** | | 16,9M / 1,61M / 147K | **12,49** |

**Итого:** смета ~$10–16 → факт $12,49 без Декарта (с ним ≈ $13,5–14) — в пределах сметы. Дороже сметы оркестратор
и папа (3 захода, вопрос о pyright); ревью, аудит, kaban и doeba — ниже или в пределах. Постоянных расходов нет.
Разбор — кабан Декарта.
