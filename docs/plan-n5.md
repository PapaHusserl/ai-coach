# Шаг Н5. Транскрипты Claude Code как источник «решающих событий»

Спайк по BACKLOG 21 (к BACKLOG 12; источник для Н6 — BACKLOG 19 «Claude вечером», Н7 — BACKLOG 14 «Claude в сб/вс», Н8 — BACKLOG 22
«разные репо в час»). План — папа-кабан, 2026-11-01, HEAD 92cd32f; переписан под «Решения» Влада 2026-11-01. Режим — «встроить»:
источник ложится в `day_counters` рядом с туду, грумингом и экраном (docs/architecture.md «v2: нагрузка вне тренировок», «v2:
экранное время»). Основание — решение Влада NOTES.md 2026-10-30 («посчитать вопросы и решённые задачи через Claude как прокси
„числа решений“; источник — локальные транскрипты, проверить на спайке»), docs/research-cycles.md тема 2 («честнее „решающие
события“», п. 4; «Claude-прокси подавать как решающие события», :142), docs/plan-roadmap-r1.md:38,62 (спайк дешёвый — до Н6–Н8;
«непригодно» — шаги идут без Claude). Разведка сделана на живых файлах `~/.claude/projects/` (скрипты в scratchpad, только
счётчики; содержимое сообщений, названия сессий и каталогов в документ не идут — репо публичное, handoff «Что важно помнить»).

## Суть

Вердикт разведки: **пригодны с оговорками**. В транскриптах есть всё, что нужно Н6–Н8 — реплики Влада с временем, окна вопросов
(`AskUserQuestion`), каталог проекта; нет только «времени Влада» (есть время агентов) и истории старше 30 дней. Считать можно по
стабильным полям; подвижную схему страхуем фильтрами по содержимому и синтетическими фикстурами.

Что лежит в файлах (измерено 2026-11-01):

- **Раскладка.** `~/.claude/projects/<каталог-по-пути-cwd>/<session>.jsonl` — основная сессия; `<session>/subagents/agent-*.jsonl` —
  субагенты (`isSidechain: true`, `agentId`); рядом `*.json`, `*.txt`, `memory/` (не читаем). Всего 51 каталог, 3 850 jsonl,
  3,65 ГБ (`du`, скрипт `inv.py`); каталог ai-coach — 388 МБ, 121 сессия + 341 файл субагентов.
- **Записи.** В ai-coach 116 668 строк: `attachment` 33 %, `assistant` 17 %, `user` 13 %, `api-request*` 11 %, остальное служебное.
  У `user` и `assistant`: `timestamp` (ISO UTC, `…Z`, у всех 734 494 записей один формат), `cwd`, `sessionId`, `version`,
  `gitBranch`, `entrypoint` (`cli` / `sdk-cli` / `claude-desktop`), `isMeta`, `isSidechain`, `message.content` (строка или список
  блоков `text` / `tool_use` / `tool_result` / `thinking`), у части — `promptSource`, `turnOrigin`, `origin`, `isCompactSummary`.
- **Реплика Влада** = `user` основного файла, не `isMeta`, не `isCompactSummary`, без `tool_result`, текст не начинается с `<`
  (`<command-name>`, `<local-command-stdout>`, `<task-notification>`, `<bash-input>`, `<bash-stdout>`, `<system-reminder>`,
  `<command-message>`) и не с `[Request interrupted`; `entrypoint != sdk-cli` (SDK-агент из другого каталога даёт 3 352 записи
  `user` — не Влад). `promptSource` у 10–25 % реплик пуст (26 версий CLI за 30 дней) — не используем. Та же логика у
  `etalon/bin/metrics.py` семьи (`user_text`).
- **Сессии с агентом.** `agent-setting` в начале файла: 200 сессий за 30 дней, из них 29 — `coach` (сессии `тренер`), 3 —
  `spike-coach`. По Р4 = 3 сессии `coach` не считаются и не хранятся.
- **Субагенты и сжатия.** Реплики `user` в `subagents/` — промпты оркестратора (исключаем файлом). `isCompactSummary` после
  `compact_boundary` — не реплика.
- **Решения.** `AskUserQuestion` — `tool_use` с `input.questions`; вызовов 29–182 в день, вопросов 55–189; без ответа ≤ 1 в день.
  Разрешения руками (`permissionDecision.source = user_temporary`) совпадают с окнами вопросов — отдельного сигнала не дают.
- **Коммиты** — измерены (точность против `git log` 6 дней из 7), но по Р2 не считаются.
- **Репо и переключения.** Каталог — папка проекта; поле `cwd` (у 13 каталогов больше одного cwd — подкаталоги, worktrees).
  Каталогов с репликами — 2–9 в день, переключений у соседних реплик — 2–12 в час активного окна.
- **Время.** Объединение активности сессий — 5,4–11 ч в день; это время агентов, не Влада; терминал уже в `screen_work_hours`.
  По Р7 не считаем.
- **Цифры по дням за 14 полных дней (все репо, день 04:00→04:00, +05).** Реплик 78–284 (медиана ~180), из них ≤ 10 символов
  30–50 %, вечером 16–51 %; в сессиях `coach` 0–34 (исключаются); вопросов 55–189; сессий с репликами 8–27.
- **Хранение — 30 дней** (code.claude.com/docs/en/data-usage, «Data retention», `cleanupPeriodDays`); подтверждено `find -mtime
  +30` → 0, самый старый файл — 2026-10-02. По Р10 оставляем 30: история копится в базе с первого прогона (Р9 — сразу после
  партии 1, за 29 дней).
- **Стоимость чтения.** Префильтр строк по подстроке — 33 с на 3,65 ГБ; mtime за 7 дней — 894 файла, 1,1 ГБ, 7,8 с; за 1 день —
  1,1 с (`win7.py`). Для `coach sync --days 7` — ~8 с сверху (ожидание по замеру скрипта, не прогон модуля).
- **Сводка у лимита.** `workload` в снапшоте за 7 дней — 3 938 / 4 000 Б (`SNAPSHOT_CHARS`, `snapsize.py`); поля Claude в нём
  порежут дни → по Р8 отдельный ключ `claude`.
- **Образцы в коде.** Читатель — `workload/todo.py:40 read_todo`; подключение — `sync/workload_sync.py:140 read_counters`, `:173
  sync_workload`; белый список — `store/workload.py:10 COUNTER_KINDS`, `:79 upsert_counter` (принимает `raw_json`, `:81`);
  типы — `workload/service.py:18 INT_COUNTERS`, `:27 COUNTERS`, `:78 _day_row`; названия по `events=true` — `workload/service.py:136
  workload_day` (`row["events"]`, `:154`); конфиг — `workload/config.py:91 default_config`, `:122 _path`, `:256 load_config`; команда
  одного источника — `cli/main.py:345 screen`, `SCREEN_LABELS` :334; снапшот — `mcp_server/snapshot.py:174`, `:52 AHEAD_SKIP`;
  `get_workload` — `mcp_server/server.py:83` (`events` :96); тесты — `tests/test_workload_sources.py`, `tests/test_cli_screen.py`,
  `tests/test_workload_sync.py:125,139,192`, `tests/test_mcp_workload.py:119–164` (названия только при `events=true`).
- **Тексты и лимиты** (`wc -c`, HEAD): `coach-help/workload.md` 8 080 / 8 192 → отдельный файл; `coach-wellbeing.md` 10 848 /
  11 264 (запас 416 Б); `coach.md` 16 173 / 16 384 (запас 211 Б); `coach-help.md` 3 779 / 6 144.

**Правило:** новое — `workload/claude.py`. Учитываются только основные файлы (не `subagents/`) сессий без `agent-setting = coach`
(Р4 = 3: такие сессии пропускаются целиком — ни в один счётчик и ни в имена). `claude_prompts(day)` = число записей-реплик (см.
выше) с днём `local(timestamp) − 4 ч`; `claude_prompts_evening` — из них с местным часом ≥ 19 или < 4; `claude_decisions` =
`Σ len(input.questions)` по `tool_use` `AskUserQuestion` (Р3 = 1); `claude_repos` — число каталогов с ≥ 1 репликой, в `raw_json`
этой строки — короткие имена каталогов (Р6 = 2, формат — Р11); `claude_switches` — число пар соседних по времени реплик дня с
разными каталогами. Коммиты не считаются (Р2), время — тоже (Р7). Существующее не меняется: `total_load` (`load/overload.py:71`),
`find_overload`, `find_deviations`, `weekly_review`, `hours` — режим наблюдения (NOTES.md 2026-10-31; веса — v2.9).
**Поведение:** меняется — (1) `coach sync` читает ещё один источник, замечание «Claude: каталог не найден» / «записей не
распознано»; (2) новая команда `coach claude [--days N]`; (3) `get_workload` отдаёт поля `claude_*`, при `events=true` на один день
— ещё и имена каталогов дня (Р11); (4) в сводке ключ `claude` (7 дней, без имён); (5) тренер знает поля и отвечает по справке;
(6) отчёт `docs/research-claude.md`. Не меняется: `total`, сигналы, план дня, недельный обзор, Garmin, экран.
**Вне репо:** `.claude/settings.json` — строку `"Bash(uv run coach claude:*)"` добавляет Влад (AGENTS.md, решение 2026-11-01),
строку `cat` темы справки — кабан (прецедент Н14); MCP-сервер перезапустить после партии 2; сразу после партии 1 — первый прогон
`uv run coach claude --days 29` (Р9); `[paths] claude_projects` — только если каталог не `~/.claude/projects`. `cleanupPeriodDays`
не трогаем (Р10). Новых зависимостей нет.

## Решения

Влад, 2026-11-01 (окна):

- Р1 — (1) сразу модуль двумя партиями, отчёт `docs/research-claude.md`.
- Р2 — коммиты не считать: многие коммиты делают кабаны, это смажет картину; Влад дробит задачу на несколько
  коммитов. Остальные счётчики (реплики, вечер, решения, репо, переключения) — остаются.
- Р3 — (1) каждый вопрос в окне — одно решение.
- Р4 — (3) сессии тренера не считать и не хранить.
- Р5 — (1) команда `coach claude [--days N]`; allow-строку добавляет Влад.
- Р6 — (2) хранить короткие имена каталогов, отдавать в `get_workload(events=true)` на один день.
- Р7 — (1) время Claude не считать.
- Р8 — (1) отдельный ключ `claude` в сводке.
- Р9 — (1) первый прогон за 29 дней сразу после партии 1.
- Р10 — (1) `cleanupPeriodDays` оставить 30.
- Р11 — (1) имя папки проекта, список `[{repo, prompts}]` по убыванию реплик (окно, рекомендация папы).
- Р12 — (1) имена в `coach claude` не печатать.
- Р13 — (1) каталог без `cwd` — имя `unknown`, как есть (окно, рекомендация папы).
- Р14 — (1) отдельный лимит `WORKLOAD_CHARS = 5000` для `workload` в сводке, 7 дней — в партии 2 (окно, рекомендация папы).
- Вне репо: строку `cat` для справки в `.claude/settings.json` добавляет Влад, не кабан (AGENTS.md; классификатор
  запретил оркестратору передать эту правку кабану, 2026-11-01).

## Справка (правило AGENTS.md)

Новые функции: источник Claude в `coach sync`, команда `coach claude`, поля `claude_*` и имена каталогов в `get_workload`, ключ
`claude` в сводке.

- `.claude/agents/coach-help/claude.md` — новая тема «Решающие события в Claude Code» (лимит 8 192; оценка ~2,5 КБ, не проверено):
  что это (реплики, вопросы-решения, репо, переключения по дням из `~/.claude/projects`; что не считается — субагенты, служебные
  строки, SDK-агенты, сессии `тренер`, коммиты, время); зачем (прокси «числа решений» к BACKLOG 12, источник для Н6–Н8,
  наблюдение); как запустить (`coach sync`, `uv run coach claude [--days N]`, до 04:00 — вчера; первый раз `--days 29`); что
  получу (поля `get_workload`, имена каталогов дня — только `events=true` на один день, ключ `claude` в сводке без имён);
  оговорки (транскрипты хранятся 30 дней — история только в базе; только этот Mac); разметка не нужна.
- `.claude/agents/coach-help.md:17` — строка оглавления после «Нагрузка вне тренировок»: «Решающие события в Claude Code - реплики,
  вопросы-решения, репо, переключения по дням из транскриптов, `coach claude` - `claude.md`» (~170 Б → ~3 950 / 6 144).
- `.claude/settings.json` — `"Bash(cat .claude/agents/coach-help/claude.md)"` рядом с темами (`:56–67`) — кабан;
  `"Bash(uv run coach claude:*)"` рядом с `screen` (`:6`) — Влад.
- `tests/test_skills_help.py`: `test_claude_topic_has_commands_and_fields` (новая: «coach sync», «coach claude», `get_workload`,
  `claude_prompts`, `claude_decisions`, `events`, «30 дней», «04:00»), `test_help_index_lists_claude` (новая); существующие
  `test_every_cli_command_is_in_help` (:381), `test_every_mcp_tool_is_in_help`, `test_index_mentions_every_topic_file`,
  `test_allow_has_every_topic_file` — зелёные с новым файлом.
- `docs/architecture.md` — раздел «## Н5: решающие события Claude» после «## Н13» (`:260`); `README.md:59` — абзац после
  «`coach sync` … читает календарь, туду, груминг»; `docs/research-claude.md` (разделы «Что лежит в файлах», «Цифры», «Критерии»,
  «Вердикт» — из «Сути», без названий каталогов и сессий).

## Модули, файлы, функции

Партия 1 — данные:

- `src/ai_coach/workload/claude.py` — новый (образец `todo.py`): `SOURCE = "claude"`, `class ClaudeError(Exception)`,
  `CLAUDE_COUNTERS = ("claude_prompts", "claude_prompts_evening", "claude_decisions", "claude_repos", "claude_switches")`,
  `SERVICE_PREFIXES = ("<", "[Request interrupted")`, `scan_claude(root: Path, start: date, end: date, tz=None) -> tuple[list[dict], int, int]` (rows, файлов, разобранных записей окна) и обёртка `read_claude(root, start, end, tz=None) -> list[dict]` (правки по ревью мамы п1)
  — обходит `root/*/*.jsonl` (только основные файлы; `subagents/` не открывает) с mtime не раньше `start 04:00` местного, строки без
  подстрок `"type":"user"` / `"type":"assistant"` / `"agent-setting"` не разбирает, битую строку пропускает, сессию с
  `agent-setting = coach` пропускает целиком, нечитаемый каталог — `ClaudeError`; за каждый день `start..end` строка на kind (0, если
  ничего); у строки `claude_repos` — `raw_json = {"repos": [...]}` по Р11 (пустой день — `[]`); нет каталога — `[]`.
  Вспомогательные (новые): `_is_prompt(record) -> bool`, `_day(ts: str, tz) -> tuple[str, bool]`, `_agent_of(lines)`,
  `_count_questions(block)`, `_repo_name(cwd: str) -> str` (Р11).
- `src/ai_coach/workload/config.py` — `WorkloadConfig.claude_projects_path: Path` (`:59`), `default_config` (`:91`) — `home /
  ".claude" / "projects"`, `load_config` (`:256`) — `_path(paths, "claude_projects", …)`; docstring `:54`.
- `src/ai_coach/store/workload.py:10 COUNTER_KINDS` — + `CLAUDE_COUNTERS`.
- `src/ai_coach/workload/service.py:18 INT_COUNTERS` — + `CLAUDE_COUNTERS`; docstring `workload_series` (:129) — новые ключи;
  `__init__.py` пакета `workload` — экспорт `read_claude`, `ClaudeError`.
- `src/ai_coach/sync/workload_sync.py:140 read_counters` — после груминга `claude_counters` (новая) → `scan_claude(config.claude_projects_path, first, today)`; `ClaudeError` → `errors.append(f"Claude: {e}")`; нет каталога → `notes.append("Claude: каталог не найден")`; файлы есть,
  распознанных записей 0 → «Claude: записей не распознано» (умолчание 6). `raw_json` доходит до `upsert_counter` (проверить, что
  `read_counters` его не отбрасывает — кабан, grep по `raw_json` в `workload_sync.py`).
- `src/ai_coach/cli/main.py` — команда `claude(days: int = 1)` после `screen` (`:345`, образец целиком): `load_config`,
  `wellbeing_day(now)`, `read_claude`, `upsert_counter` в одной транзакции, печать «Claude {day}: реплик N (вечером K), решений M,
  репо R, переключений S» (`CLAUDE_LABELS` по образцу `SCREEN_LABELS` :334; имена каталогов не печатает — Р12); нет каталога —
  «Claude {day}: транскриптов нет.», `ClaudeError` — `fail`, код 1.

Партия 2 — MCP, сводка, тексты:

- `src/ai_coach/workload/service.py:136 workload_day` — при `events=True` ещё `row["claude_repos_names"]` из `raw_json` счётчика
  `claude_repos` дня (через `list_counters`; нет строки — `None`); `workload_series` / `_rows` имён не отдают.
- `src/ai_coach/mcp_server/server.py:83` — описание `get_workload`: «claude_prompts (реплики пользователя в Claude Code за день
  04:00–04:00, без сессий тренера), claude_prompts_evening (после 19:00), claude_decisions (вопросы-решения AskUserQuestion),
  claude_repos (каталогов проектов), claude_switches (переключения между ними); null — не считалось; events=true на один день — ещё
  claude_repos_names». `INSTRUCTIONS` (:38–41) — «…экранное время и события Claude Code; названия событий и каталогов Claude —
  только get_workload(events=true) на один день».
- `src/ai_coach/mcp_server/snapshot.py` — `AHEAD_SKIP` (:52) + `CLAUDE_COUNTERS`; `workload` (:174) — строки без `claude_*`
  (`WORKLOAD_SKIP = CLAUDE_COUNTERS`); новый `snapshot["claude"] = part([{date, prompts, evening, decisions, repos, switches} …])`
  за 7 дней, `newest=True`, без имён; описание `get_morning_snapshot` (:62) — ключ `claude`.
- `.claude/agents/coach-wellbeing.md:7` — в «Поля дня» хвост: «`claude_prompts` / `claude_prompts_evening` / `claude_decisions` /
  `claude_repos` / `claude_switches` - реплики, вопросы-решения, каталоги и переключения в Claude Code за день (наблюдение: в
  `total` не входят; null - не считалось; в сводке `claude` за 7 дней; имена каталогов - `events=true`)» (~280 Б → ~11 130 /
  11 264; ожидание, не проверено — риск). `coach.md:10` — `claude` в списке Bash (+7 Б → 16 180 / 16 384).
- Справка — раздел выше; `README.md`, `docs/architecture.md`, `docs/research-claude.md`.

Не трогаем: `load/overload.py`, `load/deviations.py`, `review/service.py`, `workload/screen.py`, `workload/todo.py`,
`workload/grooming.py`, миграции (новый kind — без миграции, architecture.md:174), `coach-day.md`, `coach-week.md`, `recalc.md`.

## Партии

Две партии. Внутри — порядок family.md: кабан-доеба (красные тесты) → кабан → `make check` → ревью, аудит → коммит → проверка
Влада; `docs/pipeline.md` — строка на партию (оркестратор). Между партиями не тянуть: каждый день до первого прогона теряет день
истории.

1. **Читатель, конфиг, sync, kind, `coach claude`, отчёт** — `workload/claude.py`, `config.py`, `store/workload.py`, `service.py`
   (INT_COUNTERS), `workload_sync.py`, `cli/main.py`, тесты, `docs/research-claude.md`. На выходе: `uv run coach claude --days 29`
   → в `day_counters` строки `source='claude'` за 29 дней, у `claude_repos` в `raw_json` имена по Р11; `coach sync` — без ошибок;
   сверка `claude_prompts` за вчера против `events3.py` (scratchpad папы) — ожидаемое расхождение на число реплик сессий `coach`
   (скрипт их считал), после вычета ± 0; `SELECT` по `day_counters`: кроме чисел — только имена каталогов в `raw_json`
   `claude_repos`. Объём: ~130 строк кода, ~240 строк тестов (ожидание, не проверено). Сразу после — первый прогон за 29 дней (Р9).
   **Граница п1 (папа, 2026-11-01, после хэнд-бэка п1):** партия коммитится только зелёной (`make check`). Из п2 в п1 перенесены:
   (а) `mcp_server/snapshot.py` — `WORKLOAD_SKIP = CLAUDE_COUNTERS`, `snapshot["workload"]` без ключей `claude_*` (ключа `claude` ещё
   нет — он в п2); тест `test_mcp_snapshot_workload.py` — `workload` без `claude_*`, набор дней не зависит от данных Claude
   (`test_snapshot_workload_days_do_not_depend_on_claude_data`, доеба — принят папой 2026-11-01; «7 дней не режутся» снято:
   предел давний, см. Р14); (б) справка в части п1 —
   `coach-help/claude.md` (что, зачем, `coach sync`, `uv run coach claude [--days N]`, 04:00, 30 дней, что не считается),
   строка оглавления `coach-help.md`, строка `cat` в `settings.json`; тест `test_claude_topic_has_commands_and_fields` в п1 — без
   `get_workload`/`events`/`claude_decisions` (их добавляет п2), `test_help_index_lists_claude`.
   Отступления кабана (`unrecognized`, `tz`, `claude_projects_path` четвёртым, kind строками, Р11 — самый короткий `cwd` и слияние
   одноимённых) — приняты; к строкам kind — тест `set(CLAUDE_COUNTERS) <= set(COUNTER_KINDS)`.
   **Правки по ревью мамы п1 (папа, 2026-11-01):** приняты — новая публичная `scan_claude(root, start, end, tz=None) -> (rows,
   files, seen)` (один обход каталога; пояс — системный на каждую запись, не смещение на `now`); `read_claude` — обёртка
   `scan_claude(...)[0]`; `unrecognized` удалена, `sync.claude_counters` решает по `files`/`seen` (каталога нет → «каталог не
   найден»; `files > 0`, `seen == 0` → «записей не распознано»; сессии `coach` в `seen` входят — ложного замечания нет). Мёртвый
   `now` не оставлять: было `read_claude(root, start, end, now, tz=None)` → станет `read_claude(root, start, end, tz=None)`;
   вызовы в `cli/main.py` и тестах — без `now`. Тесты доебы: пояс (запись по разные стороны перехода DST — день по своему
   смещению), `seen` при окне только из сессий `coach` → нет замечания, `files=0` при пустом каталоге.
2. **MCP, сводка, тексты** — `service.py:workload_day`, `server.py`, `snapshot.py` (ключ `claude`, `AHEAD_SKIP`), `coach-wellbeing.md`,
   `coach.md`, `coach-help/claude.md` (дописать `get_workload`, `claude_repos_names`, ключ `claude`), README, architecture, тесты. На выходе:
   `get_workload("2026-10-20", "2026-11-01")` отдаёт `claude_*` целыми, без имён; `get_workload` на один день с `events=true` —
   `claude_repos_names`; сводка — ключ `claude` 7 строк, `workload_ahead` без `claude_*` (тест доебы, отложенный из п1);
   `workload` — 7 дней или 6, по Р14 (замер `snapsize.py` — цифру в «Итог»).

**Р14 — развилка (папа, 2026-11-01, после находки доебы в п1; решает Влад):** `snapshot["workload"]` режется до 6 дней из 7
уже на HEAD, без Н5: пустая база, `morning_snapshot(conn, "2026-10-07")` — 6 строк, `truncated=true`, 3 448 символов; 7 строк —
4 023 > `SNAPSHOT_CHARS = 4000` (замер скриптом папы на HEAD через `git worktree` и на рабочей копии — одинаково). Давний предел:
ключей прибавилось с `screen_challenge/hindrance_hours` (Н3, bebae69). Регрессом Н5 не является (`WORKLOAD_SKIP` держит
`workload` как на HEAD); цифра «3 938 / 4 000» в «Сути» — на живых данных, на пустой базе (null) строки длиннее. Видимое: тренер
в сводке видит 6 дней нагрузки вместо 7, самый старый день пропадает.
Варианты: (1) в п2 — свой лимит ключа: `WORKLOAD_CHARS = 5000` (новая константа `snapshot.py`), `workload` = `tools.cap(rows,
SNAPSHOT_ROWS, WORKLOAD_CHARS, True)`; весь снапшот на пустой базе 9 833 / 32 768 — запас есть; тест «7 строк, `truncated=false`
на пустой базе»; (2) оставить 6 дней, пункт BACKLOG «сводка: workload 7 дней не влезает в 4000»; (3) сократить ключи `workload`
(например, убрать `*_evening_hours`) — меняет то, что видит тренер, и тексты агентов. Рекомендую (1): одна константа, план и так
обещает 7 дней (Поведение (4), Р8), запас общего лимита большой.
   Объём: ~30 строк кода, ~3 КБ текста, ~70 строк тестов (ожидание, не проверено). Перезапуск MCP.

## Тесты (кабан-доеба)

Фикстуры — синтетические jsonl в `tmp_path`: помощники `write_session(dir, session_id, records)` и `record(kind, ts, **fields)` в
`tests/test_workload_sources.py`, компактный JSON (`separators=(",", ":")`). Имена каталогов в фикстурах — выдуманные.

Партия 1 — `tests/test_workload_sources.py`, блок `# --- claude ---`:

- реплика считается: `content` строкой и списком `[{"type":"text"}]` → 1 и 1;
- не считаются: `tool_result`; `isMeta`; `isCompactSummary`; `<command-name>`, `<local-command-stdout>`, `<task-notification>`,
  `<bash-input>`, `<system-reminder>`; `[Request interrupted…`; `entrypoint: sdk-cli`; файл в `<session>/subagents/` → 0;
- день: `…T22:30:00Z` при +05 → предыдущий день; `…T23:00:00Z` → следующий; ровно 04:00 — сегодня; пояс подменяется (умолчание 7);
- вечер: 18:59 → нет, 19:00 → да, 03:59 следующего дня → вечер того же дня самочувствия;
- строка на каждый день окна, в т. ч. 0; вне окна не считается; файл с mtime раньше окна не открывается (`os.utime`);
- Р4 = 3: сессия с `agent-setting` `coach` — реплики, `AskUserQuestion` и её каталог не входят ни в один счётчик и не попадают в
  имена; `agent-setting` с другим именем → считается;
- `claude_decisions`: `input.questions` из 3 → 3; в субагенте → 0; без `questions` → 0, не падает;
- `claude_repos`: реплики в двух каталогах → 2, `raw_json["repos"]` — два имени по Р11; день без реплик → 0 и `[]`;
  `claude_switches`: A, B, A → 2; A, A, B → 1; один каталог → 0; сортировка по времени между файлами;
- `_repo_name`: путь `cwd` → имя по Р11 (обычный, подкаталог, worktree);
- нет каталога → `[]`; пустой каталог → нули; битая строка → пропуск; `chmod 000` → `ClaudeError`; файлы есть, записей 0 → нули;
- `test_claude_counters_have_no_text_or_paths`: в `json.dumps(counters)` нет текста реплики, полного пути, `sessionId`; имена
  каталогов — только в `raw_json` строки `claude_repos`;
- `test_claude_files_are_not_modified`: mtime и содержимое те же.

`tests/test_workload_config.py`: `claude_projects` раскрыт; без ключа — `~/.claude/projects`. `tests/test_store_workload.py`: новые
kind проходят `upsert_counter`, `raw_json` сохраняется. `tests/test_workload_service.py`: `claude_prompts` → `int`, без данных →
`None`. `tests/test_workload_sync.py`: счётчики за окно, `raw_json` у `claude_repos` записан; нет каталога → замечание; `ClaudeError`
→ `status='error'`, туду и груминг записаны; `test_sync_does_not_store_file_names_or_titles` (:139) — имена Claude только в
`claude_repos.raw_json`. `tests/test_cli_sync_workload.py:108` — транскрипты не изменены. `tests/test_cli_claude.py` (новый,
образец `tests/test_cli_screen.py:67–148`): пишет за день самочувствия; печатает числа без имён; 03:59 → вчера, 04:00 → сегодня;
1 день по умолчанию; повтор заменяет; нет каталога → «транскриптов нет», код 0; `ClaudeError` → код 1.

Партия 2: `tests/test_mcp_workload.py` — `claude_*` целыми, без данных `None`; без `events` и на диапазоне — нет
`claude_repos_names` (образец :147–164); `events=true` на один день — `claude_repos_names` списком; описание `get_workload` содержит
`claude_prompts`, `claude_decisions`, `claude_repos_names`. `tests/test_mcp_snapshot_workload.py` — `workload_ahead` и `workload`
без `claude_*`; `snapshot["claude"]` 7 строк с короткими ключами, без имён; `test_snapshot_has_all_sections` (+`claude`); сводка ≤
`SNAPSHOT_MAX_CHARS`. `tests/test_skills_workload.py` — `coach-wellbeing.md` содержит `claude_prompts`, «наблюдение», ≤ 11 264;
`tests/test_skills_help.py` — раздел «Справка»; `test_mcp_no_push` — состав инструментов не меняется.

Проверка руками (Влад): после партии 1 — `uv run coach claude --days 29` → «Claude <вчера>: реплик N (вечером K), решений M, репо R,
переключений S»; числа похожи на память; `uv run coach sync` — без ошибок. После партии 2 и перезапуска MCP — `тренер`: «сколько я
вчера решал в Claude?» → реплики и решения за день; «в каких репо я вчера был?» → имена каталогов (через `events=true`); «что ты
знаешь про сессии Claude?» → ответ по справке с оговоркой про 30 дней.

Для mutmut (TESTS по `grep -l`): `workload.claude:read_claude`, `workload.claude:_is_prompt`, `workload.claude:_day`,
`workload.claude:_agent_of`, `workload.claude:_count_questions`, `workload.claude:_repo_name` (все новые) —
`tests/test_workload_sources.py`, `tests/test_workload_sync.py`, `tests/test_cli_claude.py`; `sync.workload_sync:read_counters` —
`tests/test_workload_sync.py`, `tests/test_cli_sync_workload.py`; `workload.config:load_config`, `workload.config:default_config` —
`tests/test_workload_config.py`, `tests/test_workload_config_coach.py`; `cli.main:claude` (новая) — `tests/test_cli_claude.py`;
`workload.service:workload_day` — `tests/test_mcp_workload.py` и остальные по `grep -l workload_day tests/`;
`mcp_server.snapshot:morning_snapshot` — `tests/test_mcp_snapshot.py`, `tests/test_mcp_snapshot_workload.py` и остальные по
`grep -l morning_snapshot tests/`. Каталоги — `make mutate` по правилу проекта (`Makefile:5`; фоном вне агента); время — как Н11 п1
(~1–5 мин + разбор, docs/plan-n11.md «Итог»).

## Развилки и риски

Р1–Р10 решены (раздел «Решения»). Новые — из Р6 = 2, видимые Владу:

- **Р11. Что такое «короткое имя каталога» и в каком виде отдаётся.** (1) Последняя часть пути `cwd` git-корня каталога
  (`ai-coach`, `dashboard`; подкаталог и worktree сводятся к имени папки проекта, взятой у самого частого `cwd` в каталоге), список
  `[{repo, prompts}]` по убыванию реплик. (2) То же, но просто имена по алфавиту без чисел. (3) Имя папки в `~/.claude/projects`
  как есть (`-Users-…-projects-ai-coach`) — без обработки, но с домашним путём. Рекомендую (1): тренер ответит «где был основной
  день», Н8 получит основу для «разные репо в час»; в базе — без полного пути. Разблокирует: `_repo_name`, формат `raw_json`, тесты.
- **Р12. Имена в `coach claude`.** (1) Не печатать — только числа (как `coach screen` без названий приложений). (2) Хвостом строки
  «(ai-coach 40, dashboard 12)». Рекомендую (1): Р6 просил имена в `get_workload(events=true)`, не в CLI.

- **Р13 (после п1). Каталог без `cwd` в именах дня.** Кабан пишет `"unknown"` (`workload/claude.py:29 UNKNOWN_REPO`).
  (1) Оставить `{"repo": "unknown", …}` — реплики видны, `claude_repos` честный. (2) Не включать в имена, но считать в
  `claude_repos`. Рекомендую (1): суммы в списке сходятся с `claude_prompts`; случай редкий. Не блокирует коммит п1.

Риски:

- Схема транскриптов недокументирована и меняется: фильтр по стабильным полям, синтетические фикстуры, замечание «записей не
  распознано»; при смене формата — правка `_is_prompt`.
- Префильтр по подстроке зависит от компактного JSON (проверено на 734 494 записях); формат с пробелами → нули и замечание.
- ~8 с на `coach sync --days 7` (замер скриптом); если мешает — `--days 1` у `coach claude` в вечернем чек-ине.
- `coach-wellbeing.md` после строки — ~11 130 / 11 264 (ожидание): следующий текст упрётся в лимит (BACKLOG 34, 39).
- Личные данные: имена каталогов теперь в локальной базе (Р6); наружу — только `events=true` на один день; в сводке, CLI (при
  Р12 = 1), документах и фикстурах — нет. Тест «имена только в `claude_repos.raw_json`».
- Сессии `coach` исключены целиком (Р4 = 3): нагрузку вечера от самого тренера Н6 не увидит — осознанный выбор Влада.
- Другие машины: считается только этот Mac (`claude-desktop` — 7 реплик за 30 дней, как обычные).
- День 04:00 и UTC: пояс системы (`astimezone()`), как у `wellbeing_day`.

## Умолчания (внутреннее)

1. Хранилище — `day_counters`, `source='claude'`, kind `CLAUDE_COUNTERS` без миграции (architecture.md:174); все целые; день без
   событий — 0; нет каталога — строк нет (`None`).
2. Модуль — `workload/claude.py`, `ClaudeError`, конфиг `[paths] claude_projects`, по умолчанию `~/.claude/projects`;
   `$CLAUDE_CONFIG_DIR` не учитываем.
3. Реплика — по правилу; `promptSource`, `turnOrigin`, `origin` не используются; `claude-desktop` — как обычные.
4. Решения — `tool_use` `AskUserQuestion` (не `tool_result`).
5. Открываются только `root/*/*.jsonl` с mtime ≥ начала окна; `subagents/` не обходится вовсе (коммитов нет — Р2); имя агента —
   из `agent-setting` того же файла.
6. Файлы есть, распознанных 0 → нули + «Claude: записей не распознано»; пустой каталог → нули без замечания.
7. Время: UTC → `astimezone()` → день −4 ч; вечер `EVENING_FROM` 19:00 … `EVENING_CUTOFF` 04:00 (`workload/service.py:15`,
   `store/journal.py:9`); в тестах пояс параметром `tz`.
8. Переключения — по всем каталогам, реплики дня по времени; субагенты и сессии `coach` не участвуют (при Р4 = 3).
9. `coach sync` — счётчик источников не меняется (`summary` :202); `CLAUDE_LABELS` («реплик», «вечером», «решений», «репо»,
   «переключений»).
10. Ключи сводки короткие (`prompts`, `evening`, `decisions`, `repos`, `switches`), в `get_workload` — полные; имя поля имён —
    `claude_repos_names`, `raw_json` — `{"repos": …}` (форма элементов — при Р11).
11. В нагрузку, сигналы, обзор и план дня не входит — наблюдение до v2.9.
12. Отчёт `docs/research-claude.md` — без названий каталогов, сессий и агентов, кроме `coach`.
13. Коммит после каждой партии; ROADMAP (Н5 ✅), карточка done 021, handoff — после закрытия; BACKLOG 12, 22 не закрываются.

## Открытые вопросы

1. Формат имён каталогов (Р11) — `src/ai_coach/workload/service.py:136 workload_day`, `workload/claude.py` (новый).
   варианты: (1) имя папки проекта, `[{repo, prompts}]` по убыванию (2) имена по алфавиту (3) имя папки `~/.claude/projects` как
   есть; рекомендую (1) — полезно тренеру и Н8, без полного пути; разблокирует: тесты партии 1; решает: Влад. Блокирующий.
2. Имена в выводе `coach claude` (Р12) — `src/ai_coach/cli/main.py:345` (образец `screen`).
   варианты: (1) нет (2) хвостом строки; рекомендую (1) — Р6 про `events=true`; разблокирует: `tests/test_cli_claude.py`; решает: Влад.

## Правки по ревью

Партия 1, ревью мамы (2026-11-01):
- Пояс: `read_claude` при `tz=None` считает день в системной зоне по смещению записи, не по смещению момента запуска
  (переход на летнее время). Исправил кабан; решение — мама, принято папой.
- Ложное «записей не распознано» при окне из одних сессий coach: новая `scan_claude` → (rows, files, seen),
  `unrecognized` удалена, sync решает по files/seen. Отступление принято папой (абзац «Правки по ревью мамы п1»).
- Аргумент `now` убран из `read_claude` — решение папы.
- Тесты под новый API и сценарии DST, окна из сессий coach, пустого каталога — доеба.
- Строки allow в `.claude/settings.json` добавил Влад (Р5, «Вне репо»), кабан их не трогал.
- Аудит свекрови: Р13 и Р14 уже решены Владом (раздел «Решения»); Р9 — первый прогон после коммита п1.
- BACKLOG не заводился.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план Н5 («Суть», «Модули, файлы, функции», «Партии», «Тесты», «Развилки и риски»); сценарий — решения Влада Р1–Р12 (2026-11-01): две партии, без коммитов (Р2), сессии `coach` пропускаются (Р4 = 3), `coach claude` есть (Р5), имена каталогов в базе (Р6 = 2), `cleanupPeriodDays` 30 (Р10 = 1), Декарта по умолчанию зовут. Цены — тариф metrics.py от 2026-10-25 (https://platform.claude.com/docs/en/about-claude/pricing, страницу не сверял), fable — по ценам Opus. Масштаб по «Модулям/файлам»: п1 ~130 строк кода, ~240 строк тестов; п2 ~30 строк кода, ~3 КБ текста, ~70 строк тестов — против Н12 (docs/plan-n12.md «Итог»: п1 ~110 / ~220, п2 ~15 / ~70; факт $21,20, 33,85M, 70 мин, churn 32 %). Объём около Н12 (код п1+п2 160 против 125, тесты 310 против 290), но без миграции, нового MCP-инструмента и правки лимита сводки; добавлены свой парсер jsonl, тесты mtime/пояса и тест «нет текста и путей» — границу держу около факта Н12. Подписок, хостинга, БД и внешних API шаг не добавляет: платное — токены LLM; Р10 = 1 диска и денег не стоит.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Токены конвейера Н5 | разово $15,4–25,3 без Декарта; $25,8–35,7 с ним | один шаг; в месяц — по числу шагов (Н12 $21,2) | не звать Декарта (как Н3, Н4, Н11, Н12, Н14) | ~$10,4 (3 × $3,47) | разбор конвейера по шагу; решает Влад |
| Оркестратор (opus) | $4,5–8 | 13–20M токенов; в Н12 15,2M, $6,07 | Р11, Р12 одним ответом (открытые вопросы); /compact только по handoff | до ~$1 | ничего, порядок вопросов |
| Партия 2 отдельно | ~$4–7 из общей суммы | ~30 строк кода, ~3 КБ текста; свой круг ревью, аудита, mutmut | слить п2 в п1 | ~$2–3, ~15 мин | граница «данные / MCP-тексты», откат отдельным коммитом; п2 всё равно ждёт перезапуска MCP; Влад решил две партии (Р1) |
| Команда `coach claude` (Р5 = 1) | ~$0,8–1,5 (~35 + ~60 строк) | команда и `tests/test_cli_claude.py` | первый прогон за 29 дней через `coach sync --days 29` | ~$0,8–1,5 | 29 дней запросов к Garmin (429); решено Владом, не предлагаю |
| Тест «нет текста и путей» и фикстуры Р4/Р11 | ~$0,3–0,6 | ~6 тестов на приватность | — | — | публичное репо, Влад требует; не трогаю |
| Доеба, кабан (sonnet) | $2,6–4,5 | уже sonnet | haiku-5-5 (тариф $0,10/$0,50) | ~$1 | качество красных тестов (догадка) — не рекомендую |
| Папа (fable по Opus), доработки плана | прошло $3,83 (2 запуска) + $0,7–2,2 | ещё 1–2 запуска: мутанты, ROADMAP | мелкие замечания — правкой оркестратора | ~$1 | план может расползтись; решает оркестратор |
| mutmut | $0 токенов | фоном вне агента, локально | — | — | — |

Ревью и аудит (мама, свекровь) не трогаю; слабую модель им и оркестратору не предлагаю.

| Партия | Время |
|---|---|
| План (папа, 2 запуска) | уже прошло: 23,9 мин (metrics.py: a3d001cb1235d4a4d 21,5 + ad2b976820d454473 2,4) |
| 1. Читатель, конфиг, sync, kind, `coach claude`, отчёт | ~30–50 мин (Н12 п1 ~40 мин; код и тесты крупнее, но без миграции и лимита сводки; mutmut +10 мин, если не пропускать; первый прогон за 29 дней ~8–30 с) |
| 2. MCP, сводка, тексты | ~20–35 мин (Н12 п2 ~29 мин; здесь код меньше, но ключ `claude` в сводке и замер `snapsize.py`) |
| Декарт (3 вызова) + тесть р.3 | ~10–15 мин |
| Весь шаг (после плана) | ~60–100 мин (без Декарта ~50–85); окна Влада и простой — вне |

Уже прошло: $3,83 (папа-кабан a3d001cb1235d4a4d $3,16 + ad2b976820d454473 $0,67, metrics.py; id из agents.md; сессия ещё идёт) — нижняя граница сметы ≥ $3,83; тесть р.1 (abdb395990685fabf, $0,19) и мой запуск (a1deef351b0e71b1d) не включены.

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| orchestrator | opus | 13–20M | 4,5–8,0 |
| papa-kaban (прошло $3,83 и 3,8M; +1–2 запуска) | fable (по Opus; последний запуск был opus) | 4,5–6M | 4,5–6,0 |
| kaban | sonnet | 2,5–4,5M | 1,3–2,3 |
| kaban-doeba | sonnet | 3–5M | 1,3–2,2 |
| mama-kaban | opus | 1,5–3M | 1,7–3,0 |
| kaban-svekrov | opus | 1,5–3M | 1,7–3,0 |
| kaban-test (р.1 sonnet, р.3 opus) | sonnet / opus | 0,4–0,7M | 0,4–0,8 |
| **итого без Декарта** | | 26–43M | **15,4–25,3** |
| kaban-dekart (3 вызова = 2 партии + 1 сводный) | fable (по Opus) | 3–4M × 3 (допущение) | 10,4 (3 × 3,47, последний факт Ш9, по plan-sh36.md:324) |
| **итого с Декартом** | | 35–55M | **25,8–35,7** |

Модели (`grep -H '^model:' ~/.claude/agents/<роль>.md`): kaban.md:model: sonnet; kaban-doeba.md:model: sonnet; kaban-dekart.md:model: fable; mama-kaban.md:model: opus; kaban-svekrov.md:model: opus; kaban-test.md:model: opus; papa-kaban.md:model: fable. Мой запуск — sonnet-5-5, kaban-test.md просит opus: р.3 считаю по opus.
