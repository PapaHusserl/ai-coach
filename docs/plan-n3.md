# Шаг Н3. Разметка работы «вызов/помеха»

Закрывает остаток BACKLOG 20 (вопросы чек-ина `--hindrance`, `--valuable` сделал Н1 — docs/plan-n1.md партия 3,
cab4c08; карточка 020 сошлётся на оба шага). План — папа-кабан, 2026-10-31, режим «встроить». Разведка на HEAD ee47a3b.
Решение Влада — NOTES.md 2026-10-30 («разметку категорий AW и событий календаря на „вызов / помеху“ (JD-R) предлагает
тренер, Влад правит»); основание — docs/research-brain.md п. 9 (JD-R: код/аналитика — вызов; груминги, согласования,
переписка — помеха) и п. 3 (ценность сделанного — уже вопрос вечера). Место в очереди — docs/plan-roadmap-r1.md:36
(«нужна до подсчёта состава нагрузки; AW-данные есть с 2026-10-12, разметка ложится задним числом»), Н3 → Н8 и
BACKLOG 12. Режим наблюдения — NOTES.md 2026-10-31. Живая база — только чтение (`?mode=ro`), в документе счётчики без
названий (репо публичное).

## Суть

Разметка — второй признак поверх категории `work`: «вызов» (challenge) или «помеха» (hindrance). Лежит там же, где вся
разметка нагрузки, — в `~/.config/ai-coach/workload.toml` вне репо (architecture.md:217 «Правила — вне репо»), потому
что названия приложений и заголовков в базу и репо не идут (README:63, `test_aw_reader_never_returns_titles`). В базу,
как и сейчас, идут только часы.

Что есть по коду (как встраиваем):

- **Экран.** `workload/config.py:174 _screen` читает `[screen] work/hobby/browser/meeting` и `[screen.title.<app>]`;
  `workload/screen.py:150 classify` → work/hobby/browser/unmarked, `:160 by_category` суммирует секунды по классам,
  `:173 read_screen` пишет четыре счётчика `screen_*_hours` (`store/workload.py:10 COUNTER_KINDS` — «новый признак =
  новый kind без миграции», 0015). Названия приложений живут только внутри `by_category`/`classify` — туда и ложится
  разметка вызов/помеха. Живая база: счётчики экрана за 20 дней с 2026-10-12 — пересчёт задним числом даёт
  `coach screen --days 20` (AW хранит сырьё, `upsert_counter` не трогает неизменённые kind).
- **Календарь.** `sync/workload_sync.py:37 stored_events` ставит `category` по названию календаря
  (`WorkloadConfig.category`, `config.py:64`); `calendar_events` хранит `title` (0015). Часы считаются на чтении
  (`workload/service.py:74 _day_row`). Живая база: рабочих встреч (timed, `category='work'`) всего 15, даты
  2026-10-05…10-20, после 20-го нет — источник тонкий (см. Р5). Пересчёт задним числом — `coach sync --days 30`
  (окно заменяется, `replace_calendar_window`).
- **Тренер.** Конфиг тренеру сейчас не виден (allow `.claude/settings.json:5-79` — только `coach …` и `cat` своих
  файлов); названия событий он видит через `get_workload(events=true)` на день, названия туду — `coach todo list`.
  Предложение разметки — текст, не код: тренер читает конфиг, предлагает блок TOML, Влад правит файл сам (у тренера
  нет Edit/Write — `coach.md:5 tools`). Бюджет промптов: `coach.md` 15 344 Б при лимите 15 360 (запас 16 Б — не
  трогаем); `coach-wellbeing.md` 6 414 Б при лимите 7 168 (`tests/test_skills_workload.py:10`, запас 754 Б);
  `coach-evening/SKILL.md` 3 766 Б при 4 096 (не трогаем, Р4); справка `coach-help/workload.md` 6 320 Б при 8 192
  (запас 1 872 Б) — рецепт идёт туда.
- **MCP/snapshot.** `workload_series` → `get_workload`, snapshot `workload` (7 дней) и `workload_ahead` (7 вперёд,
  `AHEAD_SKIP` `snapshot.py:51` режет счётчики), `get_overload.days` берёт только `SCREEN_HOURS` (`overload.py:49`) —
  новые поля туда не попадают сами. Новых инструментов нет → `coach.md:5`, `EXPECTED_TOOLS` не меняются.

**Правило:** было `by_category` → `{"work", "hobby", "browser", "unmarked"}` → станет + `"challenge"`, `"hindrance"`
(части `work`: секунды приложения из `[screen] challenge`/`hindrance`); было `stored_events`: `{**row, "category":
category, "synced_at": stamp}` → станет + `"demand": config.demand(category, title)` (партия 2); было `_day_row`: часы
по `HOURS` → станет + `challenge_hours`, `hindrance_hours` (рабочие timed-события по `demand`, партия 2). Формула
нагрузки `hours`/`total_load` (`overload.py:52,60`), отклонения, обзор — не меняются.
**Поведение:** меняется — (1) новые ключи конфига; (2) два новых счётчика экрана и две колонки часов календаря в
`get_workload`/snapshot `workload`; (3) `coach screen` печатает «вызов N ч, помехи M ч» (при Р4 = 1); (4) итог sync —
замечание «экран: вызов/помеха не размечены», пока списков нет; (5) тренер по просьбе предлагает разметку (текст).
Не меняется: вечерний чек-ин (вопросы про помехи и ценность уже есть), `overload`, `get_deviations`, недельный обзор,
`workload_ahead` (режим наблюдения).
**Вне репо:** `workload.toml` — Влад вписывает разметку (после предложения тренера); `.claude/settings.json` — строка
allow `Bash(cat ~/.config/ai-coach/workload.toml)` руками Влада (среда запрещает агентам, прецедент Н2); MCP-сервер
перезапустить после партии 2 (описание `get_workload`; handoff «после правок MCP-схемы»). Новых зависимостей нет
(AW `categorize` по заголовкам для demand не используется — Р1 (1)).

## Решения

Влад, 2026-10-31 (окна по одному):

- Р1 — (1): ключи `challenge`/`hindrance` по приложениям, `[calendar.demand] challenge` regex; окна браузера не
  размечаем.
- Р2 — (2): рабочая встреча без правила — помеха по умолчанию.
- Р3 — (1): тренер читает `workload.toml` (`cat`), строку allow ставит Влад.
- Р4 — (1): `coach screen` печатает «вызов/помехи», `coach sync` — замечание «не размечены».
- Р5 — (1): партия 2 (календарь) — в этом шаге.
- Умолчания 1–12 — приняты целиком.
- Умолчание 13 (отступления кабана п1, принял папа) — Влад принял окном, 2026-10-31 (аудит свекрови п1).

## Справка (правило AGENTS.md)

Новые функции: ключи конфига, поля `screen_challenge_hours`, `screen_hindrance_hours`, `challenge_hours`,
`hindrance_hours`, строка `coach screen`, замечание sync, просьба «предложи разметку вызов/помеха». Правки:

- `.claude/agents/coach-help/workload.md` — новый раздел «## Вызов и помеха» после «Экранное время» (партия 1; партия 2
  дописывает абзац про календарь): что это (JD-R одной строкой: вызов — код, аналитика, задачи, которые двигают; помеха —
  согласования, переписка, неясности; обе грузят, но по-разному); как разметить — ключи `[screen] challenge`/`hindrance`
  (приложения из `work`/`meeting`), `[calendar.demand] challenge = [regex на заголовок]` (и `hindrance` при Р2 = 1), файл
  вне репо; как попросить тренера — «предложи разметку вызов/помеха»: тренер читает `~/.config/ai-coach/workload.toml`,
  предлагает блок TOML по правилу выше (приложения созвонов — помеха), вы правите файл сами, затем `uv run coach screen
  --days 20` и `uv run coach sync --days 30` — разметка ложится задним числом; что получу — поля в `get_workload`
  (`screen_challenge_hours`, `screen_hindrance_hours` — часть `screen_work_hours`; `challenge_hours`, `hindrance_hours`
  — часть `work_hours` календаря; null — не размечено), строка `coach screen`; «тренер пока только копит, в нагрузку
  и сигналы не входит». Размер после правки — кабан меряет `wc -c`, лимит 8 192.
- `.claude/agents/coach-help.md:17` — в строку «Нагрузка вне тренировок» добавить «вызов/помеха» (3 333 Б, лимит 6 144).
- `.claude/agents/coach-wellbeing.md:7` — поля `screen_challenge_hours`, `screen_hindrance_hours` (партия 1),
  `challenge_hours`, `hindrance_hours` (партия 2) одной фразой; `:22` — «экран: вызов/помеха не размечены» → предложи
  разметку по справке «нагрузка» (`cat .claude/agents/coach-help/workload.md`). Лимит 7 168, запас 754 Б.
- `tests/test_skills_help.py:190 test_workload_topic` — needles `challenge`, `hindrance`, `screen_challenge_hours`,
  `coach screen --days`; новый тест «ключи конфига в справке = константа `DEMANDS`» по образцу
  `test_workload_topic_signal_thresholds_match_overload` (`:224`); `tests/test_skills_workload.py:17
  test_coach_wellbeing_describes_all_screen_fields` — +2 поля (регресс в партию 1, правило 9).

## Модули, файлы, функции

Партия 1 — экран:

- `src/ai_coach/workload/config.py`: `DEMANDS = ("challenge", "hindrance")` — новая константа; `ScreenConfig` (:32) —
  поля `challenge: frozenset[str]`, `hindrance: frozenset[str]`; `_demand_apps(section, apps) -> dict[str, frozenset]`
  — новая: читает `[screen] challenge/hindrance` через `_strings` (:129), нижний регистр, проверки: пересечение
  списков — `WorkloadConfigError` («приложение в challenge и hindrance сразу»), приложение не из `work ∪ meeting ∪
  title` — `WorkloadConfigError` («… не размечено как work/meeting»); `_screen` (:174) — вызов `_demand_apps`.
- `src/ai_coach/workload/screen.py`: `demand_of(app, config) -> str | None` — новая (challenge/hindrance/None, через
  `lower()`, как `classify` :150); `by_category` (:160) — к четырём ключам + `challenge`, `hindrance`: секунды, попавшие
  в `work` (по заголовку или по приложению), дополнительно суммируются в `demand_of(app)`; `read_screen` (:173) — при
  `config.challenge or config.hindrance` ещё два ряда `screen_challenge_hours`, `screen_hindrance_hours` (округление
  как у остальных); иначе ряды не пишутся и в `notes` — «экран: вызов/помеха не размечены» (образец `:222`).
- `src/ai_coach/store/workload.py:10 COUNTER_KINDS` — +2 kind.
- `src/ai_coach/workload/service.py:18 SCREEN_COUNTERS` — +2 (далее `workload_series` отдаёт их сам, `float`);
  docstring `workload_series` (:114).
- `src/ai_coach/mcp_server/snapshot.py:51 AHEAD_SKIP` — +2 (иначе красный `test_snapshot_workload_ahead_has_no_screen_fields`).
- `src/ai_coach/mcp_server/server.py:78` — описание `get_workload`: «…, `screen_challenge/hindrance_hours` — вызов и
  помехи внутри экранной работы (null — не размечено)».
- `src/ai_coach/cli/main.py:332 SCREEN_LABELS` — при Р4 = 1 + `("screen_challenge_hours", "вызов")`,
  `("screen_hindrance_hours", "помехи")`; `screen` (:341, :376) — печатать только kind, что есть в `hours`
  (сейчас `hours[kind]` упадёт KeyError, если разметки нет).
- Тексты: справка (раздел выше), `coach-wellbeing.md:7,22`, `README.md:62-63` (счётчики и ключи конфига),
  `docs/architecture.md` — раздел «## Н3: вызов и помеха» после «## Н2» (:227-230).
- Тесты: `tests/test_workload_config.py`, `tests/test_workload_screen.py`, `tests/test_store_workload.py:159`
  (параметризация +2), `tests/test_workload_service.py`, `tests/test_mcp_snapshot_workload.py`, `tests/test_cli_screen.py`,
  `tests/test_workload_sync.py` (замечание), `tests/test_skills_help.py`, `tests/test_skills_workload.py`.

Партия 2 — календарь:

- `src/ai_coach/store/migrations/0025_calendar_demand.sql` — новая: `ALTER TABLE calendar_events ADD COLUMN demand TEXT
  CHECK (demand IN ('challenge', 'hindrance'))` (NULL-able, старые строки живы; CHECK в ADD COLUMN SQLite допускает).
- `src/ai_coach/workload/config.py`: `WorkloadConfig` (:47) — поле `demand_rules: dict[str, list[str]]`
  (`{"challenge": [regex], "hindrance": [regex]}`) и метод `demand(category, title) -> str | None` — новый: только для
  `category == "work"`; совпадение regex (`(?i)`, как `title_regex` :26) → класс, challenge проверяется первым; без
  совпадения — при Р2 = 2 `"hindrance"`, при Р2 = 1 `None`; `_calendar_demand(section) -> dict` — новая: читает
  `[calendar.demand]` (`_table` :91, `_strings` :129, проверка regex и кавычек как `title_patterns` :137; чужой ключ —
  ошибка, как `_title_rules` :154); `load_config` (:192) — вызов.
- `src/ai_coach/sync/workload_sync.py:37 stored_events` — `"demand": config.demand(category, event.get("title"))`;
  `own_events` (:55) — `demand` не ставится (события коуча с категорией — task/rest/sleep, `agenda/service.py:70`;
  focus-блоки Н13 категории не имеют и в `calendar_events` не попадают).
- `src/ai_coach/workload/service.py`: `_day_row` (:74) — `challenge_hours`, `hindrance_hours` из `mine` при
  `category == "work"` по `e["demand"]` (`_hours(_clip(...))`, как `work_hours`; без `_evening_` вариантов);
  `EVENT_FIELDS` (:25) — + `demand` (видно в `events=true`); docstring `workload_series`.
- `src/ai_coach/mcp_server/snapshot.py:51 AHEAD_SKIP` — + `challenge_hours`, `hindrance_hours` (умолчание 8).
- `src/ai_coach/mcp_server/server.py:78` — описание `get_workload` (+ календарные поля).
- `tests/workload_fakes.py:31 stored_event` — поле `demand=None` по умолчанию (иначе `upsert` без колонки — ок, но тесты
  сервиса должны уметь задать demand).
- Тексты: справка (абзац про календарь), `coach-wellbeing.md:7`, `README.md:64`, architecture (тот же раздел).
- Тесты: новый `tests/test_store_migration_0025.py` (образец 0021/0024), `tests/test_workload_config.py`,
  `tests/test_workload_sync.py`, `tests/test_workload_service.py`, `tests/test_mcp_workload.py`, `tests/test_skills_help.py`.

Не трогаем: `load/overload.py`, `load/deviations.py`, `review/service.py`, `.claude/skills/coach-evening/SKILL.md`,
`.claude/agents/coach.md`, `agenda/*`, `workload/calendar_eventkit.py` (поля события те же), `bin/trener`.

## Партии

Две партии — по источникам: экран (главный источник, 20 дней данных) и календарь (миграция, тонкий источник — Р5).
Каждая самодостаточна: своя проверка руками, свой коммит после ревью и тестов, аудит по коммиту. Одной партией можно
(Н2 — 17 файлов одной партией, churn 0), но миграция + конфиг + два источника в одном ревью тяжелее, а Р5 может снять
партию 2 целиком — граница оставлена. Внутри партии — порядок family.md: кабан-доеба (красные тесты) → кабан →
`make check` → ревью, аудит → коммит → проверка Влада; `docs/pipeline.md` — строка на партию (оркестратор).

1. **Экран** — `config.py`, `screen.py`, `store/workload.py`, `service.py`, `snapshot.py`, `server.py`, `cli/main.py`,
   справка, `coach-wellbeing.md`, README, architecture. На выходе: с `[screen] challenge = [...]`, `hindrance = [...]` в
   конфиге `uv run coach screen --days 20` пишет `screen_challenge_hours`/`screen_hindrance_hours` за 20 дней и печатает
   «Экран <день>: работа N ч, …, вызов A ч, помехи B ч» (Р4 = 1); без списков — старый вывод и замечание в `coach sync`;
   `get_workload` отдаёт поля. Объём: ~50 строк кода, ~150 строк тестов (ожидание, не проверено; аналог — экран v2.8 и
   Н1 партия 1: 715 строк вставок в 16 файлах). После партии — предложение тренера и правка конфига Владом («Проверка
   руками»).
2. **Календарь** — миграция 0025, `config.py`, `workload_sync.py`, `service.py`, `snapshot.py`, `server.py`, fakes,
   справка, README, architecture. На выходе: `uv run coach sync --days 30` → у рабочих встреч `demand`, `get_workload`
   отдаёт `challenge_hours`/`hindrance_hours`, `events=true` показывает `demand` у события. Объём: ~45 строк кода +
   миграция, ~120 строк тестов (ожидание, не проверено). После партии — перезапуск MCP.

## Тесты (кабан-доеба)

Партия 1 (образцы — `tests/test_workload_config.py`, `tests/test_workload_screen.py` с `FakeAw` из `workload_fakes.py:148`):

- Конфиг: `[screen] work = ["A", "B"], meeting = ["M"], challenge = ["a"], hindrance = ["B", "m"]` → `challenge ==
  {"a"}`, `hindrance == {"b", "m"}` (нижний регистр); приложение в обоих списках → `WorkloadConfigError` с обоими
  словами; приложение не из work/meeting/title → `WorkloadConfigError`; приложение с `[screen.title.<app>]` в `challenge`
  — ок; не список / не строки → ошибка (параметризация как `:185`); без ключей — пустые множества, `load_config` жив;
  старые тесты `[screen]` не меняются.
- `by_category`: `{("a",""): 3600, ("b",""): 1800, ("h",""): 600}` при work={a,b,h}, challenge={a}, hindrance={b} →
  `work 6000`, `challenge 3600`, `hindrance 1800` (`work` не уменьшается); hobby/browser-приложение в списках не бывает
  (конфиг не пустит) — приложение из `meeting` без другой разметки в `hindrance` → считается и в `work`, и в
  `hindrance`; класс по заголовку `hobby` у приложения из `challenge` → в `challenge` не идёт; `work` по заголовку →
  идёт.
- `read_screen`: со списками — ряды `screen_challenge_hours`, `screen_hindrance_hours` за каждый день с событиями, с
  округлением до двух знаков, нули пишутся (как `test_zero_category_is_stored_as_zero_not_skipped` :307); без списков —
  этих kind нет и в `notes` ровно одно «экран: вызов/помеха не размечены» (на все дни, не на каждый); названия
  приложений в рядах и notes не появляются (`test_title_does_not_reach_rows_or_notes` :486 расширить).
- `upsert_counter`: параметризация `:159` +2 kind; `workload_series` отдаёт `screen_challenge_hours` как `float` и
  `None` без данных; snapshot `workload` содержит поле, `workload_ahead` — нет (`:84` уже проверяет префикс `screen_`).
- `coach screen` (Р4 = 1): с рядами demand → строка с «вызов A ч, помехи B ч»; без них → строка как раньше, без
  KeyError (`test_screen_prints_hours_by_category` :80 + новый); `sync_workload` с `[screen]` без списков → в итоге
  «экран: вызов/помеха не размечены», со списками — нет.
- Тексты: `workload.md` содержит `challenge`, `hindrance`, `screen_challenge_hours`, `coach screen --days`, «предложи
  разметку»; ключи из `DEMANDS` оба в справке; `coach-wellbeing.md` содержит 6 полей `screen_*` и фразу про «не
  размечены»; размеры в лимитах (существующие тесты).

Партия 2:

- Миграция 0025: `schema_version >= 25`; колонка `demand` есть, старые строки живы (вставка без `demand` → NULL);
  `demand='foo'` → `IntegrityError`.
- Конфиг: `[calendar.demand] challenge = ["(?i)воркшоп", "design"]` → `demand("work", "Design review") == "challenge"`;
  при Р2 = 2 `demand("work", "Синк") == "hindrance"`, при Р2 = 1 — `None`; `demand("personal", …) is None`;
  `title=None` → умолчание (не падает); плохая regex / кавычка / чужой ключ → `WorkloadConfigError`; без секции —
  правил нет, поведение по умолчанию (Р2).
- `stored_events` (через `sync_workload`, `tests/test_workload_sync.py`): рабочее событие получает `demand` в базе,
  личное — NULL; повторный sync с изменённым конфигом перезаписывает `demand` (ключ `_same` видит разницу).
- `_day_row`: два рабочих события 10–11 (challenge) и 11–12 (hindrance) → `challenge_hours 1.0`, `hindrance_hours 1.0`,
  `work_hours 2.0`; пересечение двух challenge-событий — объединение (`_hours`); отменённое/отклонённое не считается;
  all-day — не считается; событие без `demand` → в обе колонки не входит; `events=true` отдаёт `demand`.
- MCP: `get_workload` за период содержит оба ключа; `workload_ahead` — нет (при умолчании 8); `get_overload.days` без
  новых ключей (`SCREEN_HOURS` не менялся); `test_snapshot_fits_total_limit` зелёный.

Проверка руками (Влад), партия 1: в `тренер` — «предложи разметку вызов/помеха» → тренер `cat` конфиг (строка allow
добавлена заранее), предлагает блок `[screen] challenge = […] hindrance = […]` (созвоны — помеха), Влад правит и
вписывает в `workload.toml` сам → `uv run coach screen --days 20` → строка с «вызов … ч, помехи … ч» → `uv run coach
sync` → замечания про разметку нет → в `тренер`: «покажи нагрузку за неделю» → `get_workload` с новыми полями; вечером
`тренер вечер` — вопросы и итог как раньше. Партия 2: при необходимости `[calendar.demand] challenge = [...]` →
`uv run coach sync --days 30` (Garmin тоже за 30 дней, ~15–30 с) → «покажи события за <день с встречей>» → у события
`demand`; `get_workload` за неделю — `challenge_hours`/`hindrance_hours`.

Для mutmut (`модуль:функция` — TESTS по `grep -l`): `workload.config:_screen` и `workload.config:load_config` —
`tests/test_workload_config.py`, `tests/test_workload_screen.py`; `workload.config:_demand_apps` (новая),
`workload.config:_calendar_demand` (новая), `workload.config:WorkloadConfig.demand` (новая) — `tests/test_workload_config.py`;
`workload.screen:by_category`, `workload.screen:demand_of` (новая) — `tests/test_workload_screen.py`,
`tests/test_cli_screen.py`; `workload.screen:read_screen` — `tests/test_workload_screen.py`; `sync.workload_sync:stored_events`
— прямых тестов нет (`grep -l stored_events tests/` пуст), через `sync_workload` — `tests/test_workload_sync.py`;
`workload.service:_day_row` — `tests/test_workload_service.py`, `tests/test_load_overload.py`; `cli.main:screen` —
`tests/test_cli_screen.py`. Каталоги — по правилу проекта (`make mutate`, фоном вне агента; долги Н2/Н13 — handoff:21-24).

## Развилки и риски

Видимое Владу — развилки, решает Влад. Первая — блокирующая для партии 1.

- **Р1. Форма разметки в конфиге (Влад пишет ключи сам).** (1) `[screen] challenge = [приложения]`, `hindrance =
  [приложения]` (подмножество `work`/`meeting`/приложений с `[screen.title]`) и `[calendar.demand] challenge = [regex
  на заголовок]` (+ `hindrance` при Р2 = 1); ключи английские, как `work/hobby/rest`. (2) Те же, но ещё `[screen.title.<app>]
  challenge/hindrance = [regex]` — разметка окна браузера на «почта/таск-трекер» против «документы/аналитика»: требует
  иерархических классов в `categorize` (`screen_query` :86-99, `_category_of` :105 — «work/challenge»), +~30 строк и
  тесты запроса. (3) Русские ключи `вызов`/`помеха`. Рекомендую (1): минимум; браузерная работа остаётся «без разметки»
  (входит в `screen_work_hours`, не входит ни в вызов, ни в помехи) — если по данным окажется большой, (2) отдельным
  пунктом беклога. Разблокирует партию 1.
- **Р2. Рабочая встреча календаря без правила.** (1) `demand = NULL` — в `challenge_hours`/`hindrance_hours` не входит,
  тренер видит «не размечено». (2) «помеха» по умолчанию — встреча = согласование (research-brain п. 9: «груминги,
  согласования — помеха»), `[calendar.demand] challenge` — список исключений (воркшопы, парное программирование).
  Рекомендую (2): конфиг из одного ключа, новые названия встреч не требуют правки; минус — рабочий блок «фокус» в
  рабочем календаре без regex сойдёт за помеху. Разблокирует партию 2.
- **Р3. Откуда тренер берёт кандидатов для предложения.** (1) Читает `~/.config/ai-coach/workload.toml` (`cat`,
  строка allow): названия приложений попадают в сессию тренера (как названия туду через `coach todo list` и заголовки
  событий через `events=true`), в базу и репо — нет; предлагает только из уже размеченных `work`/`meeting`. (2) Тренер
  не читает конфиг: даёт общее правило, Влад пишет списки сам. (3) Новая команда `coach screen --apps [--days N]` —
  живые часы по приложениям из AW (видит и неразмеченные; +~25 строк, названия приложений на экран и в сессию).
  Рекомендую (1): без кода, кандидаты — ровно те приложения, что уже считаются работой; календарные заголовки тренер
  при желании смотрит `get_workload(events=true)` по дням или спрашивает Влада. Разблокирует текст справки.
- **Р4. Что видно в режиме наблюдения.** (1) `coach screen` печатает дополнительно «вызов A ч, помехи B ч» (только
  когда разметка есть); `coach sync` — замечание «экран: вызов/помеха не размечены», пока списков нет (как «экран не
  настроен»); `get_workload`/snapshot `workload` — поля; `coach-evening` не меняется. Риск: вечерний скил запускает
  `coach screen` (п. 0) и видит эти цифры перед вопросом «сколько дня ушло на помехи 1–5» — подсказка тренеру, не Владу
  (вопрос задаёт тренер, отвечает Влад); в скил «не называй» не добавляем (запас 330 Б, режим наблюдения). (2) Вывод
  `coach screen` не меняется, цифры только в `get_workload`. Рекомендую (1): Владу есть где увидеть, что разметка
  работает; если тренер начнёт комментировать вызов/помехи вечером — пункт беклога на промпт, не код.
- **Р5. Календарь — делать ли партию 2 сейчас.** Факт по живой базе: рабочих timed-встреч 15, даты 2026-10-05…10-20,
  после 20-го — ни одной; экран — 20 дней подряд. (1) Делать: ~45 строк + миграция, пункт 20 закрывается целиком, помеха
  «встречи» — классическая. (2) Только экран; календарь — когда встречи снова пойдут, остаток пунктом беклога (20 тогда
  закрыт частично, третьим шагом). Рекомендую (1), но вопрос Владу: рабочий календарь ещё читается (`coach sync` не
  пишет «неразмеченные календари»)? Если встреч больше не будет — (2).

Риски:

- Разметка приложения «целиком»: терминал с Claude Code — вызов, но в нём же `git`-рутина; мессенджер — помеха, но
  в нём же обсуждение задачи. Грубость осознанная (n-of-1, research-brain «Сводная»); уточнение по заголовкам — Р1 (2).
- Двойной счёт между источниками: созвон = приложение созвонов в AW (помеха) и событие календаря (помеха). Как и сейчас
  у `work_hours` против `screen_work_hours` — колонки раздельные, суммировать их будет v2.9/Н6 по формуле `hours`
  (ручные > экран > календарь), не Н3.
- Allow `Bash(cat ~/.config/ai-coach/workload.toml)`: совпадение шаблона с `~` не проверено — если Claude Code не
  сопоставит, спросит разрешение разово (Влад рядом); тогда строка в allow — с полным путём.
- Snapshot `workload`: 4 новых ключа × 7 строк — 112 Б на строку по длине ключей (`python3 -c len(...)`), до 784 Б
  (расчёт, не прогон); лимит 20 000 держит `test_snapshot_fits_total_limit`; `workload_ahead` не растёт (AHEAD_SKIP).
- Пересчёт задним числом: `coach screen --days 20` — один POST с 40 периодами (как сейчас при `--days N`);
  `coach sync --days 30` тянет и Garmin за 30 дней (`run_sync`, пауза 0,5 с/день) — разово терпимо, отдельной команды
  «только календарь» нет и не добавляем.
- `coach-wellbeing.md` запас 754 Б на две партии (две фразы); при нехватке — вынос в `coach-wellbeing/` по образцу
  `coach-nutrition/variety.md` (новая строка allow), не раньше.
- `screen` в `cli/main.py` — длина под порогом qlty: правка — одна строка `parts` с фильтром по наличию kind.
- Миграция 0025 через `ALTER TABLE … ADD COLUMN … CHECK` — старые строки NULL проходят CHECK; тест миграции закрепит.
- Режим наблюдения: тренер может сам начать «читать» вызов/помехи в утренней сводке (как риск Н1 партии 3) — наблюдать
  к К1, при появлении — пункт беклога на `coach.md`.

## Умолчания (внутреннее)

1. Имя оси — `demand` (JD-R «job demands»); значения `challenge`/`hindrance`; константа `DEMANDS` в `workload/config.py`.
2. Kind счётчиков — `screen_challenge_hours`, `screen_hindrance_hours` (`source='screen'`, два знака, как остальные);
   пишутся только при непустых списках; «работа без разметки» = `screen_work_hours − сумма` считается читателем, не
   хранится. Вечерних вариантов (`*_evening_*`) нет.
3. Demand экрана считается только для секунд, попавших в `work` (по заголовку `work` или по приложению из `work`/`meeting`);
   секунды `hobby`/`browser`/`unmarked` в demand не идут, даже если приложение в списке (конфиг такое и не пропустит,
   кроме приложений с `[screen.title]`, где класс решает сервер).
4. Проверки конфига: пересечение `challenge ∩ hindrance` — ошибка; приложение не из `work ∪ meeting ∪ title` — ошибка
   (опечатка видна сразу, а не нулём в базе); регистр — `lower()`, как у `work`.
5. Замечание «экран: вызов/помеха не размечены» — из `read_screen` в `notes` (одно на вызов), в итоге `coach sync`;
   `coach screen` notes не печатает (как сейчас). Порога «% без разметки» нет — при Р4 это и так видно по цифрам.
6. Календарь (партия 2): `demand` ставится в `stored_events` при sync, не на чтении (как `category`); `(?i)` на
   заголовок, первое совпадение `challenge`, потом `hindrance`, затем умолчание по Р2; `title` NULL → умолчание.
   `own_events` (календарь коуча) — `demand` NULL.
7. Поля дня: `challenge_hours`, `hindrance_hours` — из timed-событий `category='work'` с учётом `_counted` и `_hours`
   (объединение пересечений внутри класса); all-day не даёт; `EVENT_FIELDS` + `demand`.
8. `AHEAD_SKIP` + четыре новых ключа — `workload_ahead` остаётся «часы по категориям без счётчиков»; `get_overload.days`
   и `SCREEN_HOURS` не трогаются.
9. Миграция 0025 `calendar_events.demand` (следующая после 0024); тест `tests/test_store_migration_0025.py`.
10. Строки `SCREEN_LABELS` при Р4 = 1: `вызов`, `помехи`; формат строки `coach screen` прежний, новые части в конце.
11. Справка — в существующей теме `workload.md` (запас 1 872 Б), новой темы и строки allow на тему не нужно.
12. Коммит после каждой партии; `docs/pipeline.md` — строка на партию (оркестратор); ROADMAP, карточка 020 и handoff —
    после аппрува и закрытия.
13. При Р4 = 1 (уточнение по партии 1, 2026-10-31): замечание «экран: вызов/помеха не размечены» — только если за
    период есть ряды экрана (`read_screen`: `rows and not marked`); нет событий окон — замечаний нет, как и у
    «неразмеченное N %». Порядок в `notes`: сначала «неразмеченное N %», затем «не размечены»; «ровно одно» в тестах
    партии 1 — одно такое замечание на период, не единственный пункт `notes`.

## Открытые вопросы

1. Р1 — форма ключей конфига (`src/ai_coach/workload/config.py:174 _screen`); рекомендую (1); разблокирует партию 1;
   решает Влад. Блокирующий.
2. Р4 — что печатает `coach screen` и замечание sync (`src/ai_coach/cli/main.py:341 screen`, `workload/screen.py:173
   read_screen`); рекомендую (1); разблокирует CLI и тексты партии 1; решает Влад.
3. Р3 — источник кандидатов для предложения тренера (справка `coach-help/workload.md`, allow `settings.json`);
   рекомендую (1); разблокирует текст справки и строку allow; решает Влад.
4. Р5 — делать ли календарь сейчас; факт: 15 рабочих встреч, последняя 2026-10-20 — календарь работы ещё читается?
   рекомендую (1); разблокирует партию 2; решает Влад.
5. Р2 — умолчание для рабочей встречи без правила (`sync/workload_sync.py:37 stored_events`, новый
   `WorkloadConfig.demand`); рекомендую (2); разблокирует партию 2; решает Влад.

## Правки по ревью

Партия 1 (ревью мамы, аудит свекрови, 2026-10-31):
- README «Разметка экрана» — перечень категорий с вызовом/помехами вместо «четырёх» (мама; кабан).
- coach-help/workload.md ужат до 7705/8192 Б — место под абзац календаря партии 2 (мама; кабан).
- Тест snapshot `workload`: `screen_challenge_hours`/`screen_hindrance_hours` (мама; доеба).
- Тест ошибки «demand в обоих списках» проверяет challenge и hindrance (мама; доеба).
- Умолчание 13 — принято Владом окном (свекровь).
- pyright: аннотация `per_app` float в test_by_category_counts_demand_inside_work (make check; доеба).
- Мини-задача вне партии (окно Влада «мини-задача кабану»): pyproject [tool.mutmut] also_copy + `.claude/`,
  `.qlty/`, `bin/`, `docs/`, `AGENTS.md`, `README.md` — mutmut падал на сборе (тесты читают эти пути); ревью мамы чистое. Полный список путей — Влад окном «оставить весь список» (аудит свекрови).
- mutmut screen+config: 27 выживших в функциях партии; доеба закрыл 18 тестами (test_workload_screen/config).
  Оставлены 9: read_screen_30–32, 44–46 — только текст ScreenError; read_screen_35, 38, 39 — `strict` у zip
  эквивалентен (длины проверены до цикла). Остальные 74 выживших — старый код вне партии.
  Повтор mutmut по 27 (23:11): killed 17, survived 10 — 9 названных и `_screen_10` (обрамление «XX…XX» текста
  ошибки screen.url; тест проверяет `match`, т.е. подстроку — шум текста, как read_screen_30–32).
  Влад окном «добить мутанта»: доеба перевёл тесты текста ошибок screen.url / screen.<key> на полное сравнение.
  Повтор mutmut по 10 мутантам config (23:13): killed 10. Итог п1: 9 выживших с обоснованием (read_screen).
- Инцидент: пустой `cat >>` доебы в файл тестов — в отклик (свекровь).

## Смета (кабан-тесть, режим 1)

**Что проверено:** план Н3 (Суть, Модули, Партии, Тесты, Развилки и риски). Платного нового нет: локальный
SQLite/TOML, без API и подписок, расход — только прогон цепочки кабанов. Масштаб: ~50 + ~45 строк кода и ~270 строк
тестов (по «Модули/файлы») против Н13 (~250–350 строк кода, ~400 тестов; «Итог» Н13, docs/plan-n13.md:553, факт $21,98):
код ×~0,35, но тестовых файлов много (9 + 6) — кабан и доеба ×~0,4–0,45, ревью/аудит ×~0,5. Тариф metrics.py от
2026-10-25 (https://platform.claude.com/docs/en/about-claude/pricing), страницу не сверял; fable — по ценам Opus.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Новые платные сервисы | 0 | шаг локальный | — | — | — |
| Прогон цепочки Н3 (разово) | ~$9,7–13,8 без Декарта, ~$13,2–17,3 с ним | см. таблицы | см. ниже | — | — |
| Партия 2 (календарь) целиком | ~$3–4,5 | Р5: 15 встреч, последняя 2026-10-20 | Р5 = (2): только экран, остаток отдельным шагом | ~$3–4,5 | пункт 20 закрыт частично, встречи без вызов/помеха |
| Декарт (2 партии + 1 сводный = 3 вызова) | ~$3,5 | $ вызова ≈ $1,16 (Ш9: $3,47 на 3 вызова; Ш8 $1,66) | не звать, как в Н14 | ~$3,5 | разбор процесса шага |
| Оркестратор (opus) | ~$2,5–3,8 | Н13 $6,36 при 16,7M; здесь две партии | /compact между партиями | ~$0,5 | ничего, если состояние в документе шага |
| Папа: перезапуск после решений Влада | ~$1–2 | уже прошло $1,95 | собрать Р1–Р5 одним окном до запуска | ~$1 | — |

Ревью (мама) и аудит (свекровь) не трогаю; слабую модель маме, свекрови, оркестратору не предлагаю.

| Партия | Время |
|---|---|
| 1. Экран | ~25–40 мин (код ~50 строк, но 9 файлов тестов и тексты; Н13 п.1 было 35–50 при ×2 кода) |
| 2. Календарь | ~20–30 мин (миграция + 6 файлов тестов) |
| Декарт + тесть р.3 | ~10–15 мин |
| Весь шаг | ~55–85 мин (без Декарта ~45–70); при Р5 = (2) минус ~20–30 мин |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| orchestrator | opus-5-5 | ~6–9M | ~2,5–3,8 |
| papa-kaban — уже прошло: $1,95 (a175d9e059b1c50fa, metrics.py; 1,23M) + перезапуски | fable (по Opus) | ~2,5–4M | ~3–4 (нижняя граница ≥ 1,95) |
| kaban | sonnet | ~3,5–5M | ~1,2–1,8 |
| kaban-doeba | sonnet | ~1,2–1,8M | ~0,6–0,9 |
| mama-kaban | opus | ~1,2–1,6M | ~1,0–1,3 |
| kaban-svekrov | opus | ~1,0–1,5M | ~0,9–1,3 |
| kaban-test (р.1 + р.3; свой запуск не включён) | opus | ~0,4M | ~0,5–0,7 |
| kaban-dekart ×3 | fable (по Opus) | ~3–4M | ~3,5 |
| **итого** | | ~16–24M (с Декартом ~19–28M) | **~$9,7–13,8** (с Декартом ~$13,2–17,3) |

Модели (`grep -H '^model:'`): kaban.md: sonnet; kaban-doeba.md: sonnet; mama-kaban.md: opus; kaban-svekrov.md: opus;
kaban-test.md: opus; kaban-dekart.md: fable; papa-kaban.md: fable. Текущий запуск тестя — claude-sonnet-5-5 (metrics.py
считает его по Sonnet), по файлу роли — opus; в смете взят opus. Вердикт: ок по бабкам; самое дорогое
необязательное — партия 2 (Р5) и Декарт.
