# План реализации v2: веллбиинг-коуч

ТЗ — [v2-wellbeing-plan.md](v2-wellbeing-plan.md) (ред. 4). План — папа-кабан по отчётам свинопаса и кабана-шурина, оценка — кабан-тесть («по бабкам ок»: разработка под Max, эксплуатация ~$14–18/мес эквивалента). Влад (2026-10-10): «окей, кабаним»; рекомендации папы-кабана приняты все; Swift-хелпер — запасной путь к календарю; **v2.2 и v2.3 объединены в один цикл**; Haiku для вечера и урезание вечернего snapshot — не берём. Цикл каждого шага — как «Общее для шагов 2–8» в [plan.md](plan.md); пуш — после аудита каждого этапа.

## Общее для v2 (каркас)

**Принципы v1 остаются:** CLI пишет, MCP читает базу и пишет только черновики; LLM в Python нет; личные данные — только в базе вне репо и в `spikes/out/`; фикстуры синтетические (репо публичное). hb-watch и `todo.json` — только чтение (тест на неизменность).

**Календарь читает только `coach sync`** (CLI из терминала). MCP к EventKit не ходит — отдаёт события из базы. Разрешение macOS (TCC) нужно терминалу, из которого запускается `тренер`.

**Схема (миграция 0015):**
- `calendar_events(id, source DEFAULT 'apple_calendar', uid, date, start_at, end_at, all_day, calendar, category CHECK IN (work, personal, hobby, rest, unknown), title, status, my_status, synced_at, raw_json)`, `UNIQUE (source, uid, start_at)`, индекс `(date)`. Время местное, `date` — день начала. В `raw_json` нет участников и адресов.
- `day_counters(date, kind, value REAL, source, synced_at, raw_json, PK (date, kind))` — расширяемый журнал признаков: новый признак = новый `kind` без миграции (белый список kind — в Python). Стартовые: `todo_open`, `todo_closed`, `grooming_done`, `grooming_pending`; v2.2 — ручные `work_hours`, `hobby_hours`, `rest_hours` (source `manual`).
- Метрики календаря (часы встреч, вечера, выходные) не материализуются — считаются на чтении из `calendar_events`.
- Календарь — замена окна `[today−days, today+AHEAD_DAYS=14]` (upsert и удаление исчезнувших, неизменённые строки не перезаписываются — повторный sync не меняет базу; Влад 2026-10-10 по аудиту v2.1); история вне окна остаётся.
- `todo_closed`, `grooming_done` — upsert за каждый день окна; `todo_open`, `grooming_pending` — снимок за `today` (последний sync дня побеждает).

**Конфиг вне репо:** `~/.config/ai-coach/workload.toml` (`tomllib`; переопределяется `$AI_COACH_WORKLOAD_CONFIG`): `[calendar] work/personal/hobby/rest/ignore = [названия календарей]`, `[paths] todo, hb_watch`. Неразмеченный календарь → `unknown` (хранится, в нагрузку не входит, замечание в итоге sync). Нет конфига → календарь пропускается, туду/груминг по умолчаниям.

**Правила подсчёта (константы `workload/service.py`):** в часы встреч — work, не all-day, не cancelled, не declined; tentative считается; повторы — каждый экземпляр; пересечения — объединение; через полночь — режется по дням; all-day — флаг `all_day_work`; вечер — после `EVENING_FROM = 19:00`; выходные — сб/вс. Личное/хобби — те же правила.

**Модули:** `workload/{config,calendar_eventkit,todo,grooming,service}.py`, `store/workload.py`, `sync/workload_sync.py` (читать всё, затем одна транзакция; упавший источник — замечание, остальные пишутся; `sync_log kind='workload'`, не `sync` — иначе ломается `first_run_today`). EventKit импортируется лениво, `CalendarError` с подсказкой про настройки конфиденциальности.

**Встраивание:** `coach sync` после Garmin всегда делает workload (ошибка Garmin не прерывает нагрузку, код выхода 1 сохраняется). MCP `get_workload(date_from, date_to, events=false)` ≤ 92 дней; `events=true` только на один день (названия по запросу). Snapshot: `workload` (7 дней назад, в `DATE_SERIES`), `workload_ahead` (7 дней вперёд, без названий). Агент: строка нагрузки в сводке, логика — в `.claude/agents/coach-wellbeing.md` по требованию (coach.md ≤ 15360 Б). Тесты без macOS: читатель календаря подменяется, `ai_coach` импортируется без EventKit.

## Шаг v2.0. Спайк источников нагрузки (только чтение)

**Цель:** «работает / не работает» по каждому пункту на маке Влада; одноразовые скрипты. Отчёт без личных данных.

**Правила:** скрипты в `spikes/workload/`, сырьё в `spikes/out/`; только чтение (в EventKit нет `save`/`remove`, в hb-doc не заходим); скрипты с промптом TCC Влад запускает сам в обычном терминале; в отчёт — структуры, счётчики, категории, без названий.

**Задачи:**
1. `common.py`: `OUT`, `save_json`, обезличенная печать.
2. `calendar_eventkit.py` (`uv run --with pyobjc-framework-EventKit`): `requestFullAccessToEventsWithCompletion:` (macOS 14+), список календарей, события −30…+14 дней, поля `eventIdentifier`, `calendarItemIdentifier`, start/end, `isAllDay`, `status`, `availability`, повторы/`occurrenceDate`, статус участия Влада, `organizer`, `timeZone`. Сводка обезличенно.
3. Вариант Б (если А не даёт промпта/доступа): `swift/CalendarDump.swift` с вшитым Info.plist (`NSCalendarsFullAccessUsageDescription`). osascript — зафиксировать как не рекомендуемый.
4. TCC-матрица: терминал Влада (промпт → разрешить), повтор без промпта, из сессии `тренер` через Bash, из другого терминала/Claude Desktop (для протокола). Какой процесс получил право, поведение API при отказе.
5. `todo_scan.py`: форма, состояния, гипотеза «закрыто за день = done/dropped по `updated`» (меняется ли `updated` при правке текста, чистит ли whats-up done).
6. `grooming_scan.py`: `done/`, `pending/` — число, mtime по дням, доля с `pr:`, сверка с `log.txt` (только счётчики).
7. Отчёт `docs/spike-workload-<дата>.md` по образцу `spike-garmin-2026-10-06.md`: таблица, ограничения, что меняется в каркасе, выбранный доступ (А/Б), TCC-матрица; разметка календарей Влада → конфиг `~/.config/ai-coach/workload.toml` (в отчёт — только количество по категориям).

**Готово, когда:** отчёт написан; по пп. 2, 4, 5, 6 есть результат; доступ из цепочки `тренер` → `coach sync` подтверждён (или зафиксирован путь Б); конфиг создан вне репо; `spikes/out/` не в гите; в отчёте нет названий событий, календарей, файлов, адресов.

**Риски:** промпт TCC для python из venv может не прийти (→ Б); терминал Влада (cmux/iTerm) — право выдаётся ему; pyobjc должен знать API macOS 26; `updated` в todo может меняться не только при закрытии.

## Шаг v2.1. Загруженность: импорт, счётчики, `get_workload`

**Цель:** события календаря и счётчики туду/груминга в базе по `coach sync`, метрики дня через MCP и в сводке тренера.

**Задачи:** миграция 0015 и `store/workload.py` (`replace_calendar_window`, `list_calendar_events`, `upsert_counter`, `list_counters`); `workload/config.py`; `workload/calendar_eventkit.py` по итогам спайка (`CalendarReader` для подмены); `workload/todo.py`, `workload/grooming.py`; `workload/service.py` (`workload_day`, `workload_series`); `sync/workload_sync.py`; `cli/main.py:sync`; MCP `get_workload` + snapshot `workload`/`workload_ahead` + `INSTRUCTIONS`; `coach.md` (tool, строка сводки, allow `Bash(cat .claude/agents/coach-wellbeing.md)`), короткий `coach-wellbeing.md`; `pyproject.toml` — `pyobjc-framework-EventKit; sys_platform == 'darwin'`; architecture «v2: нагрузка», README «Нагрузка вне тренировок», pipeline.

**Готово, когда:** повторный sync не меняет базу; события вне окна не тронуты; `todo.json` и `hb-watch` после sync байт-в-байт те же; ошибка календаря не блокирует туду/груминг и Garmin; `make check` зелёный; Влад прогнал `coach sync` и `тренер` — в сводке есть строка нагрузки.

**Тестовые сценарии (TDD):** миграция 0015 (колонки, UNIQUE, CHECK, PK); replace окна (идемпотентность, вне окна остаётся, исчезнувшее исчезает); upsert_counter; config (нет файла, ignore, unknown, битый toml, env); правила подсчёта (all-day, cancelled/declined/tentative, пересечения, 18:30–19:30 → вечер 0.5, до 19:00 → 0, через полночь, сб/вс, hobby/personal, unknown); todo (open, closed по updated, пустой/нет/битый); grooming (mtime через `os.utime`, pending, имён файлов в базе нет); sync (CalendarError → error в sync_log, счётчики записаны; `kind='workload'` не влияет на `first_run_today`; GarminAuthError → workload выполнен, код 1; read-only по хэшу и mtime); MCP (> 92 дней → ошибка, events на диапазоне → ошибка, на дне — title, без events — title нет, snapshot без названий, raw_json не отдаётся); импорт без EventKit; тексты coach.md ≤ 15360.

**Риски:** лимит coach.md (вынос 4а в `coach-nutrition.md` при нехватке); pyobjc удлиняет `uv sync`; TCC «протухает» после обновления терминала — в README.

## Шаг v2.2+v2.3. Вечерний чек-ин, общая нагрузка и сигнал выгорания (один цикл)

**Цель:** вечером — настроение, стресс, работа/хобби/отдых; одно число «общая нагрузка», сигнал перегруза, реакция тренера и прогноз по календарю.

**Задачи (вечер):** миграция 0016 — `wellbeing_log.mood`, `stress` (1–5, NULL допустим); `coach feel <1-5> ["текст"] [--mood] [--stress] [--work ч] [--hobby ч] [--rest ч]` (часы → `day_counters` manual); `find_deviations` + `mood <= 2`, `stress >= 4`, recalc.md; snapshot `evening_done_today`, wellbeing с mood/stress; скилл `coach-evening/SKILL.md` ≤ 3 КБ; `тренер вечер` (аргумент в `bin/trener`).

**Задачи (нагрузка):** `load/overload.py` — `total_load` (линейная сумма, веса-константы; ручные часы главнее календарных), `find_overload` (`total_streak`, `evening_streak`, `weekend_work`, `recovery_drop`, `todo_growth`); MCP `get_overload(date)`, snapshot `overload`, `workload_ahead[].overloaded`; реакция в `coach-wellbeing.md` (снижение объёма черновиками через recalc.md, «пустой вечер», перегруженные дни), строка-триггер в `coach.md`; формула — в architecture.

**Готово, когда:** вечерняя запись в `get_wellbeing` и snapshot, повторный вечер не спрашивает заново; `total` на фикстуре = ручной расчёт; стрики и падение восстановления ловятся на границах; snapshot в лимите; Влад прогнал `тренер вечер` и видит сигнал в сводке.

**Тесты:** миграция 0016 (старые строки живы); feel с/без опций, `--mood 7` → ошибка; часы → manual; `evening_done_today`; deviations на границах; SKILL ≤ 3072; расчёт total; ручные часы перекрывают календарные; стрики N−1/N/N+1; `recovery_drop` без данных не срабатывает; `get_overload` без нагрузки → `load_error`; тексты.

**Риск:** веса — догадка; калибровать по 2–3 неделям, менять только константы (бэклог «пересмотр весов»).

## Шаг v2.3а. Вечер после полуночи

**Цель (Влад, 2026-10-11):** чек-ин после полуночи относится к прошедшему вечеру.

**Задачи:** константа `EVENING_CUTOFF` = 04:00; «день самочувствия» = вчера, если сейчас раньше 04:00. По нему: дата записи `coach feel` (оценка, mood/stress, текст), дата ручных часов `--work/--hobby/--rest` в `day_counters`, `evening_done_today` в snapshot (и что видит `тренер вечер`). Остальное (sync, еда, сводка, план) — по календарной дате. Одноразово перенести запись самочувствия 2026-10-11 01:51 на 2026-10-10 (данные, не код).

**Тесты:** feel в 03:59 → вчера, в 04:00 → сегодня; часы так же; `evening_done_today` в 01:00 видит вчерашний чек-ин; граница на смене месяца; остальные даты не сдвигаются.

## Шаг v2.4. Практики и привычки

Миграция 0017 — `practice` (как `recipe`: name, kind breathing/pause/walk/sleep, minutes, trigger, steps, soft delete) и `habit`/`habit_log` (состав — груминг v2.4); `coach practice add/list/show` (allow), edit/delete — нет; `coach habit …` по грумингу; MCP `get_practices`, snapshot `habits_today`; подбор практики — в промпте. Готово: CRUD + лимиты + тексты; Влад завёл 2–3 практики.

## Шаг v2.5. Недельный обзор и роль коуча

MCP `get_weekly_review(weeks=4)` (по неделям: TSS, часы работы/вечера/выходные, туду, mood/stress/сон/readiness и дельты; выводы — агент); `review_log` + `coach review done`, флаг `week_review_due`; `coach.md` — ядро + файлы (`coach-wellbeing.md`, `coach-nutrition.md`, `coach-week.md`), тесты ≤ 15360 и «каждый файл в allow»; README/architecture финал. Готово: Влад прогнал обзор недели.

**Общие риски:** отдельный `kind='workload'` в sync_log; приватность (названия только в базе и `events=true`); TCC привязан к терминалу; рост snapshot — проверять `MAX_CHARS`; лимиты Max 5 при 5 циклах подряд; mutmut — фоном вне агента.
