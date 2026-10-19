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

**Груминг v2.4 (Влад, 2026-10-11):** привычка — да/нет за день + необязательное число (`habit`: name, unit?, soft delete; `habit_log`: date+habit, done 0/1, amount?); отметка — вечерний чек-ин (`coach-evening` спрашивает по активным привычкам) + CLI; команды `coach habit add/list/done/undo/edit/delete` (delete — soft, история остаётся); дата отметки — правило «до 04:00 — вчера», как у `coach feel`. В allow — `habit add/list/done/undo`; `edit/delete` — только с подтверждением Влада. MCP сверх плана — `get_habits`, `get_habit_log` — Влад оставил. «Не сделал» пишется (`habit done --no` → done=0, вечером тоже); число без `unit` — отказ.

## Шаг v2.5. Недельный обзор и роль коуча

MCP `get_weekly_review(weeks=4)` (по неделям: TSS, часы работы/вечера/выходные, туду, mood/stress/сон/readiness и дельты; выводы — агент); `review_log` + `coach review done`, флаг `week_review_due`; `coach.md` — ядро + файлы (`coach-wellbeing.md`, `coach-nutrition.md`, `coach-week.md`), тесты ≤ 15360 и «каждый файл в allow»; README/architecture финал. Готово: Влад прогнал обзор недели.

**Решения v2.5 (Влад, 2026-10-11):** неделя — ISO Пн–Вс, текущая неделя неполная (`partial`); `week_review_due` — в Вс и Пн, пока нет записи `review_log` за эту неделю (Вс — текущая, Пн — прошедшая); вынос из `coach.md` — как в плане: ядро + `coach-wellbeing.md`, `coach-nutrition.md` (есть, дополнить) и новый `coach-week.md`, блоки переносятся без смены смысла. По ревью и аудиту (подтверждено Владом): поля `total` и `days_with_data` сверх плана — оставить; повтор `review done` без заметки старую не затирает; `--week` не понедельник → ошибка; `review done` запускает тренер сам в конце обзора (в allow); `weeks` 1–12; «Красные флаги» — только в ядре `coach.md` (дубль из `coach-nutrition.md` убран); нет пульса покоя → `tss` недели `None`.

## Шаг v2.6. Запись тренера в Apple Calendar

Из бэклога (Влад, 2026-10-11). План — папа-кабан, оценка — кабан-тесть («по бабкам ок»: разработка $0 сверх Max, эксплуатация +$1–1.5/мес). Схема как у тренировок: MCP пишет только черновик, в календарь пишет CLI после «да» Влада.

**Решения Влада (2026-10-11, все по рекомендации):** (1) отдельный календарь коуча в iCloud, название — `workload.toml [coach] calendar`, чужие календари недостижимы; (2) двойное подтверждение — «да» в чате + `coach event write/remove` не в allow (`event list/cancel` — в allow); (3) правка = `remove` + новый черновик, `move` — в закрома при частых переносах; (4) нагрузка по категории события из `coach_events.category` по uid: тренировки/практики/чек-ин — не считаются, отдых/сон — `rest`, «буду …» — work/hobby/personal; события, добавленные в календарь коуча руками, пропускаются; (5) доступ — запись из CLI в том же терминале, Swift-хелпер — только если спайк не пройдёт; (6) «буду …» — тренер всегда предлагает черновик `task` (уточняет время и категорию); постфактум — черновик с прошлой датой до 30 дней + напомнить часы в `coach feel`; вопрос на вечернем чек-ине — не добавлять; (7) одно ежедневное напоминание о чек-ине (`checkin`, `repeat=daily`), черновиком по «да»; (8) слот тренировки — после approve/push, связь `workout_id`, отмена тренировки → предложить снять слот. Окно `agenda` в snapshot — −1..+7 (удешевление кабана-тестя не берём).

**Задачи:**
0. Мини-спайк записи (Влад в своём терминале) `spikes/workload/calendar_write.py`: найти календарь, создать событие с будильником, прочитать по `eventIdentifier`, удалить; повторяющееся — создать/удалить с будущими. Зафиксировать: новый промпт TCC, стабильность `eventIdentifier` после iCloud-синка, задержку на iPhone. Отчёт — дополнение в `spike-workload-2026-10-10.md` без названий. Без спайка код не пишется.
1. Миграция 0019 `coach_events`: `kind` (training/practice/rest/sleep/checkin/task), title, date, start_at/end_at, all_day, note, `category` (work/personal/hobby/rest или NULL), alarm_min, `repeat` (daily, только checkin), `workout_id`, `practice_id`, `status` draft/written/cancelled/removed, `calendar_uid`, created/written/removed_at, `removed_by` cli/calendar.
2. `store/agenda.py` — CRUD, `list_events`, `category_by_uid`, `find_by_uid`.
3. `agenda/service.py` — `validate_draft` (kind, start < end, ≤ 24 ч, −30..+14 дней, repeat только у checkin и один активный, workout/practice живы, категория по умолчанию), переходы write/remove/cancel; порядок EventKit → база, при сбое базы uid в сообщении.
4. `agenda/calendar_write.py` — `CalendarWriter` (write → uid, remove с проверкой «событие в календаре коуча»), ленивый EventKit, общие `_request_access`/`_ns_date`; MCP его не импортирует.
5. `workload/config.py` — `[coach] calendar`, конфликт с другими секциями → ошибка, категория `coach`.
6. `sync/workload_sync.py` — свои события по uid с категорией из `coach_events`, чужие в календаре коуча — пропуск со счётчиком в итоге, пропавшие свои `written` → `removed_by='calendar'`; одна транзакция.
7. MCP `mcp_server/agenda.py`: `create_draft_event`, `cancel_draft_event`, `get_agenda` (≤ 92 дня); snapshot `agenda` (−1..+7, draft/written); `INSTRUCTIONS`.
8. CLI `coach event list/write/remove/cancel` (`write` по нескольким id, коммит после каждого).
9. Роль: `.claude/agents/coach-agenda.md` ≤ 6144 Б (в allow), триггер в `coach.md`, ссылки из `coach-wellbeing.md` и `coach-week.md`; `coach-evening` не трогать.
10. `test_mcp_no_push.py` — новые инструменты, запрет импорта писателя, EventKit не грузится с сервером.
11. Документы: architecture (раздел v2.6), README (календарь коуча, `[coach]`, команды), pipeline, handoff, строку из backlog снять.

**Тесты (TDD):** миграция 0019 (CHECK, индексы); store; `validate_draft` на границах; переходы (write только из draft, повторный write не создаёт второе событие); `FakeCalendarWriter` (ошибка календаря → база не меняется; ошибка базы → uid в сообщении); CLI (`write 1 2 3` с плохим 2, remove чужого uid, нет `[coach]` → ошибка до EventKit); MCP (статусы, > 92 дней, snapshot ≤ `MAX_CHARS` при 20 событиях, состав инструментов); sync (work-событие → `work_hours`/`weekend_work`, NULL-категория не хранится, чужой uid пропущен, удалённое руками → removed, идемпотентность, ошибка календаря не помечает removed); config; тексты и лимиты; todo/hb-watch не меняются.

**Риски:** форма возврата pyobjc при сохранении/удалении и стабильность `eventIdentifier` в iCloud — только спайк; повторяющийся чек-ин (один uid на все вхождения); лимиты текстов (`coach-wellbeing.md` запас 104 Б, `coach-evening` 6 Б); TCC привязан к терминалу; приватность — названия только в базе; рост snapshot.

**Ручная проверка:** календарь коуча в Calendar.app + `[coach]`; спайк; слот тренировки после утверждения виден в Calendar.app и на iPhone; «в сб буду работать 10–12» → write → sync → `weekend_work` в сводке; постфактум; `event remove`; удалить своё руками → после sync `removed`; напоминание о чек-ине пришло; повторный sync ничего не меняет; чужие календари целы.

**Общие риски:** отдельный `kind='workload'` в sync_log; приватность (названия только в базе и `events=true`); TCC привязан к терминалу; рост snapshot — проверять `MAX_CHARS`; лимиты Max 5 при 5 циклах подряд; mutmut — фоном вне агента.

## Шаг v2.7. Спайк экранного времени (Mac, ActivityWatch)

Из закромов (Влад, 2026-10-12). План — папа-кабан. Только чтение; код фичи, пороги и веса `overload.py` не трогаем. iPhone (Biome) — отдельный спайк позже.

**Решения Влада (2026-10-12, все по рекомендации):** (1) установка — `brew install --cask activitywatch`; (3) правила категорий — в Python по `app` (черновик `spikes/out/screen_rules.toml`, при фиче — `[screen]` в workload.toml); (5) фаза Б — до первых выходных включительно (≥ 3 будня + сб/вс); (6) AW постоянно, Login Items. (2) заголовки окон — изменено Владом при установке (2026-10-12): «Универсальный доступ» выдан и оставлен, заголовки копятся только в базе AW на маке, в coach.db и репо не идут. После фазы Б по цифрам: (4) браузер — в спайке только доля. (7) 2026-10-19, по рекомендации: в `aw_compare` день — 04:00→04:00, как у ручных часов (v2.3а); (8) колонка «+брауз» (work + весь браузер, верхняя оценка) остаётся; (9) сегодняшний неполный день в сравнение не входит; (10) правила браузера — вне лимита ~15 правил (предложила мама-кабан, Влад подтвердил 2026-10-19); (11) календарные часы в `aw_compare` тоже по дню 04:00→04:00 (Влад, против рекомендации); (12) 2026-10-19, против рекомендации: терминал cmux (61 % дня по `--apps`) делить на work/hobby по заголовку окна внутри AW — пересмотр (3) «по app»; как именно — папа-кабан. По его плану (2026-10-19; (13)–(18) Влад выбрал сам в AskUserQuestion, «по рекомендации» = выбрал рекомендованный вариант): (13) заголовок cmux без совпадения → work; (14) Влад: «projects — это всегда hobby, msa — это всегда работа» (правила по пути в заголовке, старшинство при пересечении не задано); (15) title-правила входят в лимит ~15, по рекомендации; (16) regex Python `re` без учёта регистра, по рекомендации; (17) по рекомендации: `title` первого события группы в ответе aw-server принят (убрать на сервере нельзя; скрипт читает только `app`/`$category`, не печатает и не хранит); (18) по рекомендации: при пересечении title-regex побеждает hobby (последний класс в `categorize`).

**Фаза А (день 0):** установка и TCC-промпты (какой процесс, какие права); `spikes/screen/aw_probe.py` — `/api/0/info`, бакеты, события по дням, доля пустых `title`, чередование afk; проверка из сессии `тренер`; убитый aw-server → понятная ошибка.
**Фаза Б:** `spikes/screen/aw_day.py --date` (query API: окна ∩ not-afk, `merge_events_by_keys(["app"])`; день, вечер 19:00→04:00, почасово; work/hobby/other, доля неразмеченного; `--apps` — только в терминал Влада; события через полночь резать по границам периодов, а не относить к дню начала — ревью фазы А); `spikes/screen/aw_compare.py --days N` — дельты с `coach feel --work` и календарём (только чтение `coach.db`); замер CPU/батареи/размера базы AW, afk при блокировке.
**Отчёт:** `docs/spike-screen-<дата>.md` без названий окон, приложений, hostname.

**Правки по ревью фазы Б (2026-10-19):** решения Влада пп. 7–9 (день 04:00 в `aw_compare`, «+брауз» остаётся, без сегодня); по маме-кабану: сверка часов с днём/вечером в `aw_day` (±60 с, иначе exit), часы через `astimezone()` (DST), «нет coach.db» одной строкой, шапка таблицы, единое имя `unmarked`, комментарий о нескольких хостах; в `screen_rules.toml` браузер вне лимита ~15 правил, work+hobby = 15. Замеры CPU/батареи/базы AW и afk при блокировке — ручные пункты отчёта. Круг 2 (решение Влада 11): календарь в `aw_compare` из событий coach.db (`list_calendar_events`, `_counted/_clip/_hours` из `workload.service`), день 04:00→04:00. Круг 3 (cmux по заголовку, ревью мамы-кабана): порядок классов проверен на живом AW — при пересечении побеждает последний класс, `TITLE_CATS = ("work","hobby")` оставлен (решение 18), комментарий; склеенная regex компилируется до запроса; имя секции в ошибке; неизвестный ключ в `[title.*]` → exit; `_category_of` упрощён. Круг 4 (баг, нашёл оркестратор при подгонке правил Владом): query2 не снимает JSON-экранирование — regex с `\` молча не совпадал; `_query_literal` (json.dumps + `\\`→`\`), regex с `"` → exit. Проверено на живом AW (`\w`, `[\w]`, `\bc`).

**Ручные замеры (2026-10-19):** Влад — нагрузка AW в течение недели нормальная (незаметен), afk при блокировке работает. Оркестратор — база AW 10 МБ за 7 дней; процессы aw-* ~0 % CPU, ~135 МБ RSS суммарно (два процесса `aw-watcher-window` — проверить, не дубль ли).

**Решение Влада (19), 2026-10-19, против рекомендации «ещё неделя»:** отчёт сейчас, вердикт предварительный — [spike-screen-2026-10-19.md](spike-screen-2026-10-19.md); сравнение ±1 ч досчитать позже.

**Заголовки окон в терминале (решение 12, план папы-кабана 2026-10-19, аппрув Влада «окей, кабаним» 2026-10-19):**
Правило: было `merge_events_by_keys(events, ["app"])` + `classify(app)` по `[work|hobby].apps` → станет: app из секций `[title.<app>]` в `screen_rules.toml` отделяются в запросе (`filter_keyvals`), сервер размечает их `categorize(t, [[["work"],{"type":"regex","regex":"(?i)(?:…)","select_keys":["title"]}],[["hobby"],…]])` и сливает `merge_events_by_keys(t, ["app","$category"])`; остальные — `exclude_keyvals` + merge по app, как было; клиент берёт категорию из `$category`, иначе `classify(app)`. Заголовки не выходят из aw-server: в ответе только `app` и `$category` (страховка в `screen_seconds`: ключ `title` в ответе → exit). *При реализации: `merge_events_by_keys` оставляет `title` первого события группы — страховка снята, заменена решением (17).* Вариант «merge по `["app","title"]` и разметка на клиенте» отклонён — заголовки попали бы в HTTP-ответ и память процесса, который запускают и агенты. Движок — python aw-server v0.14.1, regex Python `re`; регистр — `(?i)` в regex, классы — `json.dumps` в строку запроса (как aw-webui).
Формат (вне git): `[title."cmux"]` — ключ ровно как в `--apps` (регистр важен); `work = ["…", "…"]`, `hobby = ["…"]` — список regex (`re.search`); подстрока — частный случай. Ошибка regex → exit до запроса. Без `[title.*]` вывод прежний.
Заголовки Владу: `aw_day --date D --titles cmux` — отдельный запрос (`filter_keyvals(app)` → `merge_events_by_keys(["title"])` → `sort_by_duration` → `limit_events(40)`), «минуты  заголовок[:100]» только в терминал; `sys.stdout.isatty()` ложно (pipe, Bash агента) → exit 1 одной строкой. Тот же guard — на `--apps` (регресс в области, в партию).
Лимит и критерий: каждая regex `[title.*]` — одно из ~15 правил work+hobby, cmux в `[work].apps` (fallback) — одно; критерий «неразмеченное ≤ 15 %» не меняется; новая строка `aw_day` «по заголовку: work/hobby/без правила» (без имён) — > 20 % терминала без правила после правки правил → заголовки неинформативны → откат к (3) «по app», в отчёт.
Партии: (1) `common.py` — `load_rules` (+`[title.*]`, `re.compile`), `screen_query(rules)` вместо `SCREEN_QUERY`, `screen_seconds` (ключ `(app, cat)`), `by_category`, новая `title_seconds`; проверка — без `[title.*]` вывод `aw_day` как до правки. (2) `aw_day.py` — tty-guard, `--titles APP`, строка «по заголовку» для дня и вечера; `aw_compare` без правок. (3) Влад: `--titles cmux` → секция в `screen_rules.toml` → прогоны. (4) этот документ: критерий, решения 13–14.
Проверки (spikes без pytest, руками): без `[title.*]` — вывод идентичен; `work=[".*"]` → весь cmux work, `hobby=[".*"]` → hobby, оба — кто побеждает в движке (без заголовков); regex `(` → exit 1 до запроса; cmux без совпадений → по вопросу 1; `--titles cmux | cat` и `--apps | cat` → exit 1; сверка часов ±60 с проходит; `aw_compare --days 3` запускается; ~~ответ с ключом `title` → exit~~ (снято решением 17).
Риски: заголовки cmux одинаковые/пустые (имя вкладки) — лечить именованием воркспейсов по проекту или заголовком shell = cwd, иначе откат к (3); частая смена заголовка → больше событий, запрос медленнее (замер времени — в отчёт); опечатка в имени app → секция молча не применяется (печатать «правил по заголовку: N app»); версия aw-core в бандле неизвестна — `select_keys` давняя опция, `priority` не используем, порядок при пересечении проверить сценарием; заголовки могут содержать пути и имена задач — только tty, в отчёт не идут.
Вопросы Владу (13)–(16) решены — см. «Решения Влада» (13)–(18).

**Годится:** сервер сам после перезагрузки; afk чередуется; агрегаты без выгрузки заголовков; work ≈ `coach feel --work` ±1 ч в будни (или объяснимо); неразмеченное ≤ 15 % при ≤ ~15 правилах; AW незаметен; неделя без падений на macOS 26.2.
**Не годится:** afk не лечится правами; расхождение > 2 ч регулярно; браузер не делится; сервер нестабилен.
