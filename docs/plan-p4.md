# П4. Веб-пульт: правка плана на ходу, «Еда» (кладовая), «Состояние», вес и синк в шапке (BACKLOG 49, часть 4 из 4)

## Суть

**Задача:** последний шаг пульта (разрез — docs/plan-roadmap-r2.md «Разрез пульта»; П1 — docs/plan-p1.md, П2 —
docs/plan-p2.md, вид — docs/plan-p2v.md, П3 — docs/plan-p3.md). Под баром дня — шкала: блок тянуть — сдвиг, правый
край — длительность, клик в пустоту — новый пункт; запись идёт в `coach_events` и в Календарь коуча тем же путём,
что `coach event move` (Н23). Вкладка «Еда» — кладовая («− остаток +», ввод +N/−N, списание просроченного,
добавление) и КБЖУ дня. Вкладка «Состояние» — сигналы и тренды. В шапке — вес с записью, синхронизация Garmin и
четыре показателя (П2в Р5 = 2). Прототип (артефакт BACKLOG 49) папе недоступен: ориентиры — текст пункта 49, решения
П1–П3 и ссылки П2в на хвост прототипа (`:487-588` — логика П4; `:513` — таймер, не сбивающий ввод, уже сделан).

**Правило (первым пунктом аппрува):**
1. Было `shifted(conn, row, start_at, today)` — «длительность сохраняется» (`agenda/service.py:217`) → станет
   `shifted(conn, row, start_at, today, end_at=None)`: при `end_at` длительность меняется; `move_event` и `move_draft`
   получают тот же необязательный `end_at`. Календарь — тем же `CalendarWriter.move(uid, start_at, end_at)`
   (`calendar_write.py:89`, уже ставит оба конца). CLI `coach event move` не меняется.
2. Было `_refusal`: `if urlsplit(path).path != "/api/mark": return 404` (`web/server.py:58`) → станет таблица
   POST-маршрутов `/api/mark`, `/api/event`, `/api/weight`, `/api/pantry`, `/api/sync`; проверка Origin = Host, тела и
   размера — общая для всех (П2 Р1 = 2).
3. Было `day-plan.md:22` «Правки плана в пульте пока нет» → станет описание шкалы (место — Р9).

**Поведение:** у команд не меняется. Новое: пульт пишет события (перенос, длительность, новый пункт), вес, кладовую
и запускает `coach sync` из браузера; `coach event list`, `get_agenda`, Календарь показывают правки из пульта;
`coach pantry list`, `get_pantry`, `coach log weight`, `get_weights` — записи из пульта. `load/*` не трогается
(только чтение `sleep_report`, `illness_report`, `overload_report`, `who5_report`, `find_deviations`); новые записи —
теми же функциями, что CLI (`record`, `add_weight`, `move_event`, `create_draft`), старые не переписываются — окно
данных v2.9 цело.

**Вне ai-coach:** Влад — при Р9 = 1 строка allow `Bash(cat .claude/agents/coach-help/pult.md)` в
`.claude/settings.json` (правило AGENTS.md; прецедент — `pult.md` скила в П3); до неё красный тест
`tests/test_skills_help.py:65`. Доступ процесса `coach web` к Календарю (EventKit) — тот же интерпретатор, что у
`coach sync`/`coach event move`; macOS может спросить разрешение ещё раз — нажимает Влад. Строк allow для `coach web`
не нужно (решение П1).

## Решения

Окна 2026-11-09, кто решил: Влад; варианты — раздел «Развилки»; все совпали с рекомендацией папы:
Р1 = 1 (полоса под баром), Р2 = 1 (показатели, вес и синк в шапке), Р3 = 1 (вес текущим моментом), Р4 = 2 (новый пункт
сразу в календарь), Р5 = 1 (четыре вида), Р6 = 1 (шаг по единице), Р7 = 1 (остаток и записи), Р8 = 1 (списание не в П4),
Р9 = 1 (тема `coach-help/pult.md`; вне репо: Влад добавляет `Bash(cat .claude/agents/coach-help/pult.md)`), Р10 = 1
(слова из справки), Р11 = 1 (пять графиков), Р12 = 1 (план первым).

Окно 2026-11-10, кто решил: Влад, совпало с рекомендацией папы: Р13 = 1 (пустой день — шкала 08:00–22:00, клик открывает
форму нового пункта; `frameOf` пустого дня → 480–1320).

Уточнения по партии 1 («API и модель»: `resize` без `end_at` → 400, тип `id` включая bool, `date` при move/resize не
читается, `CREATE_FIELDS` без повтора и связей, `mark_reply` → `post_reply`, `test_cli_agenda.py` без правок) — защита
ввода и внутреннее, решил папа 2026-11-09 по ревью и аудиту партии 1; виды `PULT_KINDS` — не решение папы, а исполнение
Р5 = 1 Влада на сервере.

Уточнения по партии 2 (решил папа 2026-11-10 по вопросам доебы, техническое): `newSpan(min, frame)` — всегда 30 мин
(Р5 = 1), `start = min(snap(min, 5), 1440 − 30)`, `end = start + 30`: конец не позже 24:00 (домен шкалы — сутки, как
`_clip` встреч в `day.py:82`), `frame.end` не ограничивает — рамка выводится из пунктов и после `load()` вырастет;
пример: клик 23:50 при рамке 18:00–24:00 → 23:30–24:00, клик 13:50 при рамке 08:00–14:00 → 13:50–14:20. Рамка пустого
дня — не техническое, развилка Р13. Сигнатуры `scale-model.js` доебы (`frameOf`, `minuteAt`, `snap`, `blockBox`,
`dragOutcome`, `newSpan`, `locked`) совместимы с «API и модель» и становятся контрактом кабана; `source` у строк
(`"item"`/`"meeting"`) для `locked` ставит `scale-pane.js` при слиянии `items` и `meetings` — в `ITEM_FIELDS`
(`day.py:22`) его нет.

Отступления кабана в партии 2 (разбор папы 2026-11-10, решил папа, техническое):
- `svgNode` в `dom.js` рядом с `el` — принято, так и в «Файлах»; `chart.js` партии 5 импортирует его оттуда.
- `newSpan(min, frame)` не читает `frame` (`void frame`) — принято: следствие уточнения выше («`frame.end` не
  ограничивает»), сигнатура — контракт доебы, не менять.
- `typing()` → `scaleBusy()` (тянут блок или открыта форма) останавливает таймер целиком, не только шкалу — принято:
  то же поведение, что у любого поля ввода в `.pane` сегодня (`pult.js:118`); после «Создать»/«Отмена» — `reload()`.
- Левый край не тянется — не отступление, «Умолчания».
- Форма нового пункта без категории — **не принято**, поправить: сервер для `task` без `category` отвечает 400
  «У задачи нужна категория: work, hobby или personal.» (`agenda/service.py:69` через `apply_event`,
  `web/plan.py:93`) — «задача» из формы не создаётся вовсе. Исполнение Р5 = 1 (Влад 2026-11-09): вид — кнопки
  «задача · фокус · отдых · еда» (не `<select>`; контейнер `.chips` и задуман под кнопки); у «задачи» — второй ряд
  кнопок `work · personal · hobby`, по умолчанию `work`, у других видов ряда нет и `category` не шлётся
  (`_category`: у `rest` сам ставит `rest`, у `focus`/`meal` чужая категория — ошибка); название — подстановка по
  виду в placeholder («Задача», «Фокус», «Прогулка / отдых», «Перекус» — `day_plan.py:168-184`), пустое поле →
  уходит это слово (иначе 400 «Название события пустое.», `service.py:110`). Два поля времени с правкой — принято
  (Р5 = 1: «время от клика, 30 мин» — стартовое значение, не запрет правки).

Окна 2026-11-10 по аудиту партии 2, кто решил: Влад, совпало с рекомендацией папы: форма нового пункта — два поля
времени, предзаполнены от клика на 30 мин, правятся до «Создать»; клик у конца суток (23:50) → 23:30–24:00, пункт всегда
30 мин, начало сдвигается назад; партия 2 коммитится после проверки Владом в браузере по чек-листу «Открыто», красное —
правка в этой же партии.

Окна 2026-11-10 по чек-листу браузера Влада, кто решил: Влад, варианты папы. Прошли (а), (в) — создание, (д), (е).
Красное: название блока не влезает, форма в одну строку, правка в приложении Календарь не доходит до шкалы.
- Название блока — подсказка «09:35–10:20 Название» над полосой при наведении и нажатии, клик по блоку раскрывает пункт
  в списке (рекомендация папы).
- Форма — пять строк: вид / категория (у задачи) / название / «с HH:MM до HH:MM» / «Создать · Отмена» (рекомендация папы).
- Правка в Календаре — по кнопке «обновить» партии 3 (полный синк); папа рекомендовал авточтение раз в 5 мин, Влад
  выбрал кнопку. До партии 3 — `uv run coach sync --calendar`.
- Объём: партия 2 коммитится сейчас (решение «красное в этой же партии» снято), подсказка, клик и форма — партия 2б
  (~50 строк, своё ревью и проверка Влада) (рекомендация папы).

Действуют решения П1 (docs/plan-p1.md «Решения», 2026-11-07), П2
(docs/plan-p2.md, 2026-11-08: Р1 = 2 Origin = Host, Р10–Р11 ошибки), П2в (docs/plan-p2v.md, 2026-11-08: Р5 = 2 —
готовность, сон, HRV, пульс покоя в шапке рядом с весом; Р12 = 1 — дата заголовком, время под ней; Р17 = 1 черновики
окна), П3 (docs/plan-p3.md, 2026-11-08/09) и Н23 (docs/plan-n23.md «Решения», 2026-11-07: Р3 = 1 `move` — только
начало, длительность та же — для CLI остаётся; Р5 = 1 повторяющееся не двигается).

## Что уже есть (разведка)

Проверено по коду и живой базе 2026-11-09 (база — read-only запросы, цифры агрегатные).

- **Перенос событий (Н23).** `shifted` (`agenda/service.py:217`) проверяет новое время через `validate_draft`
  (`:95`: −30…+14 дней, ≤ 24 ч, повтор — запрет), `move_draft` (`:233`) — черновик, `move_event` (`:245`) — записанное:
  сначала `writer.move(uid, start, end)`, потом база, commit внутри. CLI `event_move` (`cli/agenda.py:116`) выбирает
  путь по `status` — пульт повторяет этот выбор в `web/plan.py`; писатель — `CalendarWriter(load_config().coach_calendar)`
  (`cli/agenda.py:38 coach_calendar`, ошибки `WorkloadConfigError`, `CalendarError`). Фейк писателя — `tests/mcp_fakes.py`.
  Создание — `create_draft` (`:153`), запись — `write_event` (`:178`). MCP `move_draft_event` (`mcp_server/agenda.py:104`)
  записанное не трогает — пульт не MCP, ему можно (как CLI).
- **Сервер.** `server.py` 164 строки: POST только `/api/mark` (`_refusal` `:54`, `mark_reply` `:69`), GET `/api/day`,
  `/api/week` через общий `api(query, build)` (`:129`). `mark_reply` зовёт только `do_POST` (`git grep mark_reply HEAD -- src
  tests`: тестов на неё нет, `/api/mark` тесты `tests/test_web_server.py` идут по HTTP) — переименовывается в диспетчер
  `post_reply`, обёртка не остаётся (уточнение папы по ревью партии 1, 2026-11-09).
- **День.** `day_view` (`web/day.py:101`) — `items` с `start_at/end_at/status/repeat`, `meetings`, рамка бара
  (`elapsed_min/left_min`). Шкале хватает этих данных; блоки встреч — серые, не двигаются (П1 Р4 = 2).
- **Кладовая.** `pantry/service.py`: `record(conn, PantryEntry)` (`:63`, ошибки `ValueError`, предупреждение «списано
  больше остатка»), `stock` (`:117`: item, qty, unit, updated_at, expires_on, opened), `expiring(conn, today, days=2)`
  (`:160`, флаг `expired`), `spoil(conn, item, None, None, now, today)` (`:170` — весь просроченный остаток). CLI
  `pantry_write` (`cli/pantry.py:28`) — `now()` в формате `YYYY-MM-DD HH:MM:SS` с пробелом — пульт пишет так же.
  В базе 75 продуктов, 538 записей журнала.
- **Вес.** `add_weight(conn, {measured_at, weight_kg})` (`store/journal.py:12`), `list_weights(conn, start, end)` (`:17`,
  без удалённых), пределы `MIN_WEIGHT_KG = 20`, `MAX_WEIGHT_KG = 300` (`cli/journal.py:39-40`). Живых записей 8.
- **Синхронизация.** `coach sync` (`cli/main.py:137`) = `load_client()` (`garmin/client.py:67`, без токенов —
  `GarminAuthError`) → `run_sync(conn, client, days, pause=0.5)` (`sync/garmin_sync.py:232`) → `run_workload(conn, days)`
  (`sync/workload_sync.py:217`, EventKit внутри). Итог — в `sync_log` (`last_sync_log`, `store/journal.py:240`).
  Длительность по `sync_log` за 21 день (60 запусков): Garmin — среднее 39,4 с, максимум 142 с; нагрузка — среднее
  4,0 с, максимум 48 с. Запрос браузера на 2+ минуты держать нельзя — синк идёт фоном в процессе сервера (Умолчания),
  страница не блокируется: `ThreadingHTTPServer` отдаёт `/api/day` параллельно.
- **Сигналы и показатели.** `sleep_report` (`load/sleep.py:108`), `illness_report` (`load/illness.py:129`),
  `overload_report(conn, day, tss)` (`load/overload.py:168`, `tss` — из `tools.load`), `who5_report` (`load/who5.py:54`),
  `day_deviations` (`mcp_server/tools.py:234`) — все отдают `signals: [{kind, value, limit}]`; так их читает сводка
  (`mcp_server/snapshot.py:212-219`). Слова для `kind` — в справке: `sleep.md` («короткая ночь», «долг сна», «возможно,
  заболеваешь»), `workload.md:31-35` (пять сигналов перегруза), `who5.md:22-24`. Показатели дня — `list_daily_metrics`
  (`store/garmin_data.py:18`: `readiness_score`, `sleep_seconds`, `hrv_last_night`), пульс покоя — `list_recovery_days`
  (`:66`, `rhr`). В базе 569 дней метрик по 2026-11-09.
- **Графики.** `chartPoints(values, box)` (`week-model.js:54`, экспорт), `chartAxes`, `svgNode` (`week-pane.js:38, :17`,
  не экспорт) — вынести в общий `chart.js` для «Состояния».
- **Статика.** `pult.js` 172 (вкладки — цикл по `#tabs button`, `typing()` — таймер не сбивает ввод), `pult-model.js` 122,
  `marks.js` 284, `pult.css` 885 (`header`, `.sub`, `.days` — `:96-121`; телефон — `@media (max-width: 520px)` `:786`),
  `index.html` 52 (панели `food`, `state` — «скоро», `:46-47`). `el(tag, className, text)` — шесть копий (BACKLOG 66).
  `tests/web/*.mjs` — только чистые функции `*-model.js`; DOM — руками (правило П2в).
- **Справка.** `day-plan.md` 7509 из 8192 Б (683 свободно — П4 не влезает), `pantry.md` 4999, `food.md` 7222, `start.md`
  4647, `sleep.md` 4764, `calendar.md` 6628, индекс `coach-help.md` 4569 из 6144 (`wc -c` 2026-11-09). Иглы
  `test_day_plan_topic_describes_pult_marks` (`tests/test_skills_help.py:123`), `..._points_pult_windows_to_food_and_training`
  (`:129`), `test_coach_help_index_mentions_pult_food_and_training` (`:135`). `coach.md` 16371 из 16384 Б — не трогать
  (новых MCP-инструментов в П4 нет).
- **BACKLOG 49 после П1–П3** (по телу пункта): главная ✓ П1; окна по типу, красное, дозаполнение ✓ П2; еда, тренировка
  с фактом и зонами, вкладка «Тренировки» ✓ П3; «нового в данных»: привязка отметок к пункту ✓ (0029, 0030), «сделал»
  у практики ✓ (`done_log`, П2), пульсовые зоны ✓ (П3 — из `raw_json`, без новых данных). Осталось ровно П4: план на
  ходу, «Еда», «Состояние», шапка. **П4 закрывает 49 целиком** — карточка `docs/done/049-veb-pult-trenera.md` при закрытии.
- **Соседние пункты беклога:** 55 (ручные события коуча, черновики до `event write`) — П4 не закрывает: симптом 3 —
  модель `own_events`, не пульт; симптом 4 при Р4 = 2 снимается только для пунктов, созданных в пульте; 62 (списание
  кладовой при «Съел вариант») — Р8; 64 (тема `pult.md`) — Р9; 66 (общий `el`) — Умолчания, закрывается партией 2;
  57, 60, 61, 63, 65, 67 — пульт П4 не задевает.

## Файлы

Объём — ожидание, не проверено; номинал партии ≤ 200 (факт П3: ×1,5–2,4 от номинала). База `wc -l` — «Разведка».

| Файл | Что | Объём |
|---|---|---|
| `src/ai_coach/agenda/service.py` | `shifted` += `end_at=None` (проверка через `validate_draft`, как сейчас); `move_draft`, `move_event` += `end_at=None`, пробрасывают | ~10 |
| `src/ai_coach/agenda/calendar_write.py` | докстринг `move` («переносит и меняет длительность») | 1 |
| `src/ai_coach/web/plan.py` | новый: `apply_event(conn, payload, now, writer_factory)` — `action: move \| resize \| create`; move/resize: по `status` — `move_event` с писателем или `move_draft`; create: `create_draft` (+ при Р4 = 2 `write_event`); `writer_factory()` по умолчанию `CalendarWriter(load_config().coach_calendar)`; `PULT_KINDS` — четыре вида Р5 = 1, чужой → 400; ошибки `AgendaError`, `CalendarError`, `WorkloadConfigError` → `MarkError` текстом | ~75 |
| `src/ai_coach/web/marks.py` | `_event`: `MAX_ID = 2**63 - 1`, id сверх предела → прежний `NoEvent` «Пункта нет.» (регресс в области партии 1: без защиты `get_event` падает `OverflowError` sqlite → 500; проверено `uv run python`, 2026-11-09). Константа дублируется с `plan.py` намеренно — общий модуль под одно число не заводим | ~3 |
| `tests/test_web_marks.py` | `test_huge_event_id_is_not_found`: `payload(2**63, …)` → `NoEvent` (рядом с `test_event_id_must_be_int`); mutmut по `git diff` захватит `ai_coach.web.marks:_event`, TESTS — этот файл | ~5 |
| `src/ai_coach/web/header.py` | новый: `header_view(conn, day, now)` — `weight` (последняя за 30 дней до `day`), `sync` (`last_sync_log` + `syncer.status()`), `metrics` (`readiness`, `sleep_h`, `hrv`, `rhr` дня `day`); `save_weight(conn, payload, now)` — пределы 20–300, `add_weight` | ~45 |
| `src/ai_coach/web/syncer.py` | новый: `start(db) -> bool` (поток-демон: `load_client` → `run_sync` → `run_workload`, как `cli/main.py:137`; второй запуск при идущем — False), `status() -> {running, started_at, error}`; состояние модульное, под `threading.Lock` | ~50 |
| `src/ai_coach/web/pantry.py` | новый: `pantry_view(conn, day, now)` (`now` не читается — как `week_view`, `server.py:119`; «Правки по ревью», партия 4) — `stock` + флаги `expired/soon` из `expiring(conn, day, 2)`, при Р7 = 1 `remaining` (как `day.py:64-67`) и `food` дня (ключи `marks_for_day`, `marks.py:183`); `save_pantry(conn, payload, now)` — `op: add \| use \| set \| spoil` (`PULT_OPS`), `record`/`spoil` с `today = now.date()`, `ValueError` → `MarkError`, предупреждение в ответ | ~60 |
| `src/ai_coach/web/state.py` | новый: `state_view(conn, day, now)` — `signals` (пять отчётов, `kind/value/limit` + источник), `trends` (14 дней: `sleep_h`, `hrv`, `rhr`, `readiness`; вес 30 дней), `load_error` при `ToolError` (overload без `tss`) | ~70 |
| `src/ai_coach/web/day.py` | `day_view` += `"header": header_view(...)` | ~3 |
| `src/ai_coach/web/server.py` | `POST_ROUTES = {"/api/mark": save_mark-путь, "/api/event": apply_event, "/api/weight": save_weight, "/api/pantry": save_pantry}`; `/api/sync` — отдельная ветка `post_reply` (`SYNC_PATH`, `sync_reply(db)`: 202/409; «Правки по ревью», партия 3); `_refusal(path, headers)` — путь из `POST_PATHS`; `post_reply(db, path, headers, rfile)` — общий разбор JSON и ошибок, `mark_reply` переименована в него (обёртки нет); GET `/api/pantry`, `/api/state`, `/api/sync` через `api(query, build)`; `do_POST` → `post_reply`, JSON при `status < 300` | ~45 |
| `src/ai_coach/web/static/dom.js` | новый: `el`, `svgNode` — одна копия; шесть старых копий `el` удаляются (BACKLOG 66) | ~12, −30 |
| `src/ai_coach/web/static/chart.js` | новый: `chartPoints` (из `week-model.js:54`), `chartAxes` (из `week-pane.js:24`; в `line`/`text` — `box` аргумента, не модульный `BOX`, см. «Правки», партия 5), `lineChart(svg, rows, keys)` из `week-pane.js:41-66`; чистые `chartSegments(values, box)` (разрыв на `null`, при Р25 = 1) и `valueRange(values)` (при Р24 = 1); `week-pane.js` импортирует | ~70, −35 |
| `src/ai_coach/web/static/scale-model.js` | новый (чистые, тесты `node --test`): `frameOf(view)` (Р1), `minuteAt(x, width, frame)`, `snap(min, 5)`, `blockBox(row, frame)` (left/width в %), `dragOutcome(mode, row, deltaMin)` → `{start_at, end_at}` с границами (конец > начала, ≥ 5 мин), `newSpan(min, frame)` (30 мин), `locked(row)` (повтор, встреча) | ~70 |
| `src/ai_coach/web/static/scale-pane.js` | новый (DOM): `renderScale(view)` под `#bar-label`; Pointer Events (`pointerdown` → `setPointerCapture`, порог 4 px, `pointermove` → подсказка времени, `pointerup` → `POST /api/event`); правый край 12 px (у блоков уже 36 px — правая треть) — `resize`; клик в пустоту — форма нового пункта (Р5); при ошибке — текст под шкалой (П2 Р11), блок на место; `dragging` — таймер `pult.js` не перерисовывает | ~130 |
| `src/ai_coach/web/static/header-pane.js` | новый: показатели, вес («записать» → поле + «OK»), «Обновить» → `POST /api/sync`, опрос `/api/sync` раз в 5 с пока `running`, затем `load()`; `headerBusy()` для `typing()` | ~55 |
| `src/ai_coach/web/static/header-model.js`, `tests/web/header.test.mjs` | новые (партия 3, решил папа 2026-11-10): чистые `metricsLine(metrics)`, `weightLine(weight)`, `syncLine(sync, status)` — тексты строк шапки по Р2 = 1; тесты `node --test` | ~25 + ~40 |
| `src/ai_coach/store/journal.py`, `src/ai_coach/cli/journal.py` | `MIN_WEIGHT_KG`, `MAX_WEIGHT_KG` переезжают из `cli/journal.py:39-40` в `store/journal.py`, CLI импортирует их (имена в `cli.journal` остаются; `grep -rn MIN_WEIGHT_KG tests/` — пусто) | ~4 |
| `src/ai_coach/web/static/pantry-model.js`, `pantry-pane.js` | новые: `stepFor(unit)` (Р6), `parseDelta("+200" \| "-50" \| "120")` → `{op, qty}`, `pantryRows(view, today)` → `[{item, qty, unit, step, until, state, spoil}]` («Правки по ревью», партия 4); DOM — таблица «Продукт · Остаток · Годен до», кнопки «−»/«+», поле, «Списать просроченное», форма добавления, блок КБЖУ (Р7); `loadPantry(day, today)` и `pantryBusy()` — как `loadWeek`/`headerBusy` | ~45 + ~110 |
| `src/ai_coach/web/static/toast.js`, `post.js` | новые (партия 4, отступления кабана — «Правки по ревью»): `toast(text)` — узел и таймер из `marks.js:48` без смены поведения (третий потребитель, предложение из партии 3); `postJson(url, payload)` — из `header-pane.js`, ответ += `body` (текст 200 — `warning` кладовой); потребители — `marks.js`, `header-pane.js`, `pantry-pane.js` | 18 + 19 (`wc -l`) |
| `src/ai_coach/web/static/state-model.js`, `state-pane.js` | новые: `SIGNAL_WORDS` (18 кодов → слова Р10 = 1), `signalRows(state)` → `[{kind, source, word, detail}]` (порядок сервера; `word` — `SIGNAL_WORDS[kind] ?? kind`, `detail` — Р23), `trendSeries(state)` → `[{key, label, dates, values}]` (пять рядов по порядку `sleep_h, hrv, rhr, readiness, weight`; у веса `dates`/`values` — из `trends.weight`); DOM — `loadState(day, today)` как `loadPantry`, список сигналов («сигналов нет»), «нет данных: …» при `load_error`, пять графиков через `chart.js` («Правки», партия 5) | ~50 + ~70 |
| `src/ai_coach/web/static/pult.js`, `pult-model.js` | `render` зовёт `renderScale`, `renderHeader`; вкладки `food`/`state` грузят `/api/pantry`, `/api/state` (как `train` → `loadWeek`, `:140, :161`); `typing()` += `dragging` | ~25 |
| `src/ai_coach/web/static/index.html`, `pult.css` | `#scale` под баром; шапка — строка показателей и кнопок под `#now` (Р2); панели `food`, `state` вместо «скоро»; стили `.scale`, `.blk-ev`, `.handle`, `.tip`, `.chips`, `.pantry`, `.sig`, `.trend`; `touch-action: none`, `user-select: none` у шкалы; телефон — кнопки 44 px (П2в Р3 = 2) | ~15 + ~150 |
| `tests/test_agenda_service.py` | `shifted`/`move_*` с `end_at`: длительность меняется; `end <= start` → ошибка; без `end_at` — как раньше (регресс). `tests/test_cli_agenda.py` не меняется: CLI без `end_at`, регресс — прогон файла | ~40 |
| `tests/test_web_plan.py`, `test_web_header.py`, `test_web_syncer.py`, `test_web_pantry.py`, `test_web_state.py` | новые — «Тесты» | ~330 |
| `tests/test_web_server.py`, `tests/test_web_day.py` | маршруты POST (404 для чужого пути, 403 Origin — общие), GET `/api/pantry`, `/api/state`, `/api/sync`; `header` в `day_view` | ~70 |
| `tests/web/scale.test.mjs`, `pantry.test.mjs`, `state.test.mjs`, `pult.test.mjs` | чистые функции выше; `chartPoints` переезжает в `chart.js` — импорт в тесте | ~120 |
| Справка — Р9 | `coach-help/pult.md` (новая) или правки `day-plan.md`, `calendar.md`, `pantry.md`, `food.md`, `start.md`, `sleep.md`; индекс `coach-help.md:23`; иглы `tests/test_skills_help.py:123-137` | ~30 |

**Итого:** ~1000 кода + ~560 тестов (ожидание, не проверено) — пять партий.

## Партии

Порядок — Р12. Каждая партия — рабочий экран; коммит по партии; `make check` (smells — BACKLOG 58 красный и до шага).

1. **Правка плана, сервер.** `agenda/service.py` (`end_at`), `web/plan.py`, `server.py` (таблица POST, `post_reply`,
   `/api/event`, `PULT_KINDS`), тесты `test_web_plan.py`, правки `test_agenda_service.py`; регресс
   `uv run pytest tests/test_agenda_service.py tests/test_cli_agenda.py tests/test_mcp_agenda.py tests/test_mcp_no_push.py
   tests/test_workload_sync_agenda.py tests/test_web_*.py`. На выходе: `POST /api/event {action: move, id, start_at}`
   двигает черновик, `resize` меняет конец, ошибка — 400 текстом — через поднятый сервер на временной базе
   (`tests/test_web_server.py`: `test_post_event_move_draft_moves_it_and_answers_times`, `test_post_event_resize_changes_end`,
   `test_post_event_error_is_400_with_text`; `coach web` без `--db`, живую базу кабан не трогает); с фейком писателя —
   записанное и `create` (при Р4 = 2 — и в календарь); чужой `kind` → 400. `coach event list` и Календарь на живой базе —
   рецепт в «Открыто: стенд», за Владом. ~170 + тесты.
2. **Шкала дня.** `dom.js` (+ снятие шести копий `el`), `scale-model.js`, `scale-pane.js`, `index.html`, `pult.css`,
   `pult.js` (`dragging`), `tests/web/scale.test.mjs`. На выходе: шкала под баром, блок тянется с подсказкой времени,
   правый край — длительность, клик в пустоту — форма нового пункта (Р5), ошибка — текстом под шкалой; окна и вкладки
   П2–П3 работают как раньше (общий `el`). ~200.
2б. **Шкала: название и форма** (окна Влада 2026-11-10). `scale-pane.js` (`startDrag`, `blockNode`, `openForm`),
   `pult.js` (колбэк раскрытия пункта), `pult.css`. На выходе: подсказка «09:35–10:20 Название» при наведении и нажатии,
   клик по блоку раскрывает пункт в списке, форма в пять строк. Чистых функций нет — тестов доебы нет, проверка — чек-лист
   Влада (б), (в), (г). ~50. Отступления кабана (разбор папы 2026-11-10, техническое): повтор раскрывается кликом,
   встреча — нет (тот же фильтр `hasWindow`, что у строк списка), у кликабельного повтора курсор-указатель; подсказка
   на всех блоках, `title` снят.
3. **Шапка: вес, синк, показатели.** `web/header.py`, `web/syncer.py`, `day.py` (`header`), `server.py` (`/api/weight`,
   `/api/sync`), `header-pane.js`, `index.html`, `pult.css`, тесты. На выходе: под датой — показатели дня, «вес N кг ·
   записать», «синк HH:MM · обновить»; «обновить» → «идёт…» → через ~45 с (измерено: среднее 43 с) данные дня
   обновились без перезагрузки; без токенов Garmin — текст ошибки; `coach log weight` видит запись. ~165 + тесты.
4. **Вкладка «Еда».** `web/pantry.py`, `server.py` (`/api/pantry`), `pantry-model.js`, `pantry-pane.js`, `pult.js`,
   `pult.css`, тесты. На выходе: таблица остатков с «−»/«+» (Р6), поле +N/−N, «Списать просроченное» у просроченных,
   форма добавления, блок КБЖУ дня (Р7); `coach pantry list` совпадает. ~210 — на краю, при росте резать на 4а (сервер)
   и 4б (окно).
5. **Вкладка «Состояние».** `web/state.py`, `server.py` (`/api/state`), `chart.js` (вынос из `week-*`), `state-model.js`,
   `state-pane.js`, `pult.css`, тесты; Справка целиком (Р9) и индекс. На выходе: сигналы дня словами (Р10), пять графиков
   (Р11), «сигналов нет», «нет данных: …» при ошибке нагрузки; вкладка «Тренировки» рисует график как раньше. ~230 —
   на краю, при росте Справка отделяется в партию 6.

## Справка (правило AGENTS.md)

Новые функции тренера: шкала (перенос, длительность, новый пункт из пульта), кладовая и КБЖУ в пульте, вес и синк
из пульта, «Состояние». Куда писать — Р9:
- При Р9 = 1: новая тема `coach-help/pult.md` — раздел «Пульт: план дня в браузере» из `day-plan.md:14-22` переезжает
  целиком (день-план остаётся 5–13 + строка-ссылка), плюс разделы «Шкала и правка плана», «Еда: кладовая и КБЖУ»,
  «Шапка: вес, синхронизация, показатели», «Состояние»; индекс `coach-help.md:23` делится на «План дня» и «Пульт» (≤ 1575 Б
  запаса); иглы `tests/test_skills_help.py:123-137` читают `pult.md`; `test_skills_help.py:65` ждёт строку allow
  Влада («Вне репо»). Закрывает BACKLOG 64.
- При Р9 = 2: `calendar.md` («Команды» — перенос из пульта), `pantry.md` («Кладовая» — пульт), `food.md` («Вес» — запись из
  пульта, 970 Б запаса — впритык), `start.md` («Синхронизация» — кнопка в пульте), `sleep.md`/`workload.md` («Состояние»),
  `day-plan.md:22` → одна строка о шкале со ссылками (≤ 683 Б).
- В обоих: `coach-help.md:23` — «…еда и тренировки, правка плана, кладовая, состояние» (игла `:135` остаётся).
- Текст MCP-инструментов не меняется (`test_every_mcp_tool_is_in_help` цел); `coach.md`, `coach-agenda.md` не трогаются.

## API и модель (внутреннее)

- `POST /api/event`: `{action: "move", id, date, start_at}` → `{start_at, end_at, date}`; `{action: "resize", id, date,
  end_at}` → то же (`move_*` с `start_at = row.start_at`, `end_at`); `{action: "create", kind, title, start_at, end_at[,
  category]}` → `{id, status}`; `date` — день просмотра (повтор — `locked`, сервер отвечает текстом `shifted`). Ошибки
  400 текстом (`AgendaError`, `CalendarError`, `WorkloadConfigError` — «Календарь коуча не задан…»), 404 — нет события.
  Уточнения по партии 1 (папа, 2026-11-09, приняты): `resize` без `end_at` → 400 «end_at: нужно время конца.» (иначе
  `shifted(end_at=None)` вернул бы прежние времена молча); `id` не целое или bool → 400 «id: нужен номер события.»
  (как `marks._event`, строже на bool — `True` иначе двигал бы событие 1); `date` сервером при move/resize не читается
  (id уникален) — клиент партии 2 может его не слать. `create` принимает только `PULT_KINDS = ("task", "focus", "rest",
  "meal")` (`web/plan.py`, новая константа; `day_plan.PLAN_KINDS` — другое назначение), проверка до `create_draft`; чужой
  `kind` → 400 «kind: задача, фокус, отдых или еда.» — исполнение Р5 = 1 на сервере (уточнено по аудиту партии 1,
  2026-11-09; прежнее «любой `kind` из `agenda.KINDS`, сужение в партии 2» снято). `CREATE_FIELDS` без `repeat`,
  `workout_id`, `practice_id` — повтор и связи из пульта не поставить.
- `POST /api/weight {kg}` → `{id}`; `measured_at = now` (Р3). `POST /api/sync {}` → 202 `{started: true}` или 409
  «Синхронизация уже идёт.»; `GET /api/sync` → `{running, started_at, error, last: {started_at, finished_at, status,
  message}}`. `POST /api/pantry {op, item, qty, unit[, until]}` → `{warning}`; `op: spoil` без `qty` — весь просроченный.
- `GET /api/day` += `header: {weight: {kg, measured_at} | null, sync: {finished_at, status, running, error}, metrics: {readiness,
  sleep_h, hrv, rhr} | null}` (`error` — «Правки по ревью», партия 3, отступления); `GET /api/pantry?date=` → `{rows: [{item, qty, unit, expires_on, opened, expired, soon}],
  remaining, food}` (Р7); `GET /api/state?date=` → `{signals: [{source, kind, value, limit}], trends: {dates, sleep_h, hrv,
  rhr, readiness, weight: [{date, kg}]}, load_error}`.
- Шкала: рамка — Р1; блоки `items` (повтор — замок, встречи — серые, без захвата); px ↔ минуты по ширине `#scale`;
  снап 5 мин; порог начала перетаскивания 4 px (иначе клик). Правый край 12 px (у блоков уже 36 px — правая треть) — `resize`. Клик в пустоту — `newSpan`
  30 мин от снапа. Пока `dragging` — `load()` таймера пропускается, после ответа — `load()`.
- `syncer`: поток-демон на своё `open_db(db)`; успех и ошибка — в `sync_log` самим `run_sync`/`run_workload`; `error`
  модуля — только текст исключения до `sync_log` (`GarminAuthError`, `GarminError`, `CalendarError`).

## Тесты

- `shifted(..., end_at)`: конец позже — длительность выросла; `end_at <= start_at` → `AgendaError`; без `end_at` — прежние
  тесты `test_agenda_service.py` зелёные (регресс). `move_event(..., end_at)` — фейк-писатель получил новый конец.
- `apply_event`: move черновика → `update_event`, писатель не вызван; move записанного → писатель, затем база; ошибка
  писателя → база не тронута, `MarkError` с текстом; resize; create → `draft` (при Р4 = 2 — `written` с uid; сбой календаря →
  остаётся черновик + текст); повтор → ошибка; `writer_factory` падает (`WorkloadConfigError`) → 400 текстом; `kind` вне
  `PULT_KINDS` → `MarkError`, в базе ничего.
- `save_weight`: 81.7 → строка `weight_log`; 19 и 301 → `MarkError`; «81,7» запятой → принимается (как CLI `parse_kg`).
- `syncer`: `start` при идущем → False; поток с подменёнными `run_sync`/`run_workload` (фейки `tests/garmin_fakes.py`,
  `workload_fakes.py` — как `tests/test_cli_sync_workload.py`) → `status().running` False после join, `last_sync_log` есть;
  исключение `GarminAuthError` → `status().error` текст.
- `pantry_view`: просроченная партия → `expired`, срок через 1 день → `soon`; `save_pantry`: `+200` → `add`, `-50` → `use`,
  больше остатка → `warning`; `spoil` без qty у непросроченного → ошибка «нет просроченного остатка»; чужая единица → 400.
- `state_view`: база без пульса покоя → `load_error`, сигналы сна/болезни считаются; `signals` пуст → `[]`; `trends` — 14 дат
  подряд, пропуск дня → `null`.
- Сервер: `POST /api/event` без Origin → 403 (общая проверка); `POST /api/weight` 200 и запись; `POST /api/sync` дважды →
  202, 409; `GET /api/pantry`, `/api/state` 200, мусорная дата 400; `/api/day` содержит `header`.
- JS (`node --test "tests/web/*.test.mjs"` — `make player-test`, `Makefile:37`; каталог без маски падает, П2в факт 9): `frameOf`,
  `minuteAt`, `snap`, `blockBox`, `dragOutcome` (сдвиг, резайз ≥ 5 мин, конец >
  начала), `newSpan`, `locked`; `stepFor`, `parseDelta` («+200», «-50», «120», «abc» → null); `signalRows` (слова по
  `SIGNAL_WORDS`, 18 кодов, неизвестный → код), `trendSeries` (`key`, `label`, `dates`, `values`); `chartPoints`,
  `chartSegments`, `valueRange` из `chart.js` («Правки», партия 5).
- Регресс области: `uv run pytest tests/test_web_*.py tests/test_cli_web.py tests/test_agenda_service.py tests/test_cli_agenda.py
  tests/test_mcp_agenda.py tests/test_pantry_service.py tests/test_cli_pantry.py tests/test_store_journal.py tests/test_skills_help.py`
  — зелёные (ожидание); `make check`.
- mutmut (правило проекта — `Makefile:39`, модули по `git diff`): `ai_coach.agenda.service:shifted`, `:move_draft`,
  `:move_event` (TESTS `tests/test_agenda_service.py`, `tests/test_cli_agenda.py`, `tests/test_mcp_agenda.py`, `tests/test_web_plan.py`
  — `grep -l 'move_event\|move_draft\|shifted' tests/`); `ai_coach.web.plan:*`, `ai_coach.web.header:*`, `ai_coach.web.syncer:*`,
  `ai_coach.web.pantry:*`, `ai_coach.web.state:*` (новые; TESTS — одноимённые `tests/test_web_*.py`, `tests/test_web_server.py`);
  `ai_coach.web.server:_refusal`, `ai_coach.web.server:post_reply` (новая), `ai_coach.web.day:day_view` (TESTS `tests/test_web_server.py`,
  `tests/test_web_day.py`, `tests/test_cli_web.py`). Время — по факту П3: 13–50 мин на модуль по load; пять новых модулей —
  ожидание 1,5–3 ч фоновых, не проверено.
- Руками (DOM и Pointer Events тестами не покрыты; `jsdom`/Playwright в проекте нет, новая зависимость — только с согласия
  Влада, не предлагаю): Mac — мышью перетащить блок, край, клок в пустоту; Chrome DevTools «device mode» эмулирует
  `pointerType: touch` — проверка касаний без телефона; телефон (Safari iOS) — перетаскивание не прокручивает страницу
  и не выделяет текст (`touch-action: none`, `user-select: none`, `-webkit-touch-callout: none`), блок двигается с
  подсказкой, записанное событие сдвинулось в приложении Календарь; «обновить» на телефоне — «идёт…» и обновление;
  кладовая — «−»/«+»/поле/списание/добавление, `coach pantry list` совпадает; «Состояние» — сигналы и графики, две темы.

## Развилки

Видимое Владу — решает он. Прототип папе недоступен — варианты собраны по тексту BACKLOG 49 и решениям П1–П3.

- **Р1. Рамка и вид шкалы.** (1) Горизонтальная полоса 56 px под баром дня на рамке бара ± 1 ч (П1 Р3 = 1), блоки
  тренера в одном ряду, встречи — тонкий серый ряд снизу; снап 5 мин; при перетаскивании над блоком подсказка
  «09:35–10:20». Точность: 860 px / 13 ч ≈ 1,1 px/мин на Mac, 360 px → ≈ 0,46 px/мин на телефоне (5 мин ≈ 2,3 px) —
  измерено по ширине `.wrap` и типовой рамке. (2) Вертикальная лента часов 48 px/ч под баром (0,8 px/мин на любом
  экране, прокрутка ~600–900 px), блоки как в календаре. (3) Полоса на 06:00–24:00 фиксированно (клик куда угодно, но
  0,33 px/мин на телефоне). Рекомендую 1 — слово «шкала» из принятого прототипа и компактность; телефонная точность
  спасается снапом и подсказкой; если на телефоне окажется неудобно — 2 отдельным шагом. Решает Влад.
- **Р2. Шапка.** (1) Под `#now` вторая строка моноширинным (`.sub`): «готовность 72 · сон 7,2 ч · HRV 48 · пульс 52»,
  третья — «вес 81,2 кг · записать» и «синк 17:13 · обновить» (вторичные кнопки-ссылки, на телефоне в две строки). (2)
  Показатели — наверху вкладки «Состояние», в шапке только вес и синк. Рекомендую 1 — П2в Р5 = 2 (Влад 2026-11-08:
  показатели в шапке рядом с весом). Решает Влад.
- **Р3. Запись веса из пульта.** (1) `measured_at` = сейчас, независимо от листаемого дня (как `coach weight` без `--at`);
  поле появляется по «записать», «OK» пишет, «Записано» всплывает (П2в Р9 = 1). (2) `measured_at` = день просмотра 12:00
  (как `--at YYYY-MM-DD`), у будущего дня запрет. Рекомендую 1 — вес меряют сейчас; прошлое — `coach weight --at`.
- **Р4. Новый пункт из пульта — черновик или сразу в календарь.** (1) Только `create_draft` — пункт «(черновик)» в
  пульте, в Календарь — `coach event write` или тренер; (2) `create_draft` + `write_event` в одном запросе, когда календарь
  коуча задан; сбой календаря — остаётся черновик, текст «записан черновиком: …». Рекомендую 2 — П4 по ROADMAP «пишет в
  календарь через механизм Н23», пульт — рука Влада, как CLI; напоминание в Календаре появится сразу. При 1 — BACKLOG 55
  симптом 4 остаётся целиком. Решает Влад.
- **Р5. Форма нового пункта.** (1) Вид — кнопки «задача · фокус · отдых · еда» (у задачи категория work · personal · hobby,
  по умолчанию work), название с подстановкой по виду («Задача», «Фокус», «Прогулка / отдых» — `day_plan.py:170`,
  «Перекус»), время от клика, 30 мин, «Создать»; тренировки, практики, чек-ины — не из пульта (нужны `workout_id`,
  `practice_id`, повтор). (2) Только «задача» и «отдых». Рекомендую 1. Решает Влад.
- **Р6. Кнопки «−»/«+» в кладовой.** Шаг: (1) по единице — g 50, ml 100, pcs 1; поле «+N/−N»: «+200» — добавить, «−50» —
  списать, число без знака — «сверка» (`set`); (2) шаг 10 % остатка; (3) без кнопок, только поле. Рекомендую 1 — слово
  прототипа «− остаток +», шаг понятен. Решает Влад.
- **Р7. «КБЖУ» на вкладке «Еда».** (1) Строка остатка дня (как в окне еды: ккал · белок · жир · углеводы, «Перебор», «без
  КБЖУ: N») и список записей еды за день (время · текст · ккал); (2) только строка остатка; (3) без КБЖУ — кладовая и всё.
  Рекомендую 1 — в BACKLOG 49 «КБЖУ» стоит у вкладки «Еда», записи дня видны только в окнах пунктов. Решает Влад.
- **Р8. Списание кладовой при «Съел вариант» (BACKLOG 62).** (1) Не в П4: у строк варианта `qty` — текст, связи с
  названиями кладовой нет (BACKLOG 67); (2) в П4 — сопоставление по `normalize(what)` и разбору `qty` «150 г», ~80
  строк и ложные списания. Рекомендую 1. Решает Влад.
- **Р9. Куда справку.** (1) Новая тема `coach-help/pult.md`, раздел «Пульт» из `day-plan.md` переезжает (BACKLOG 64),
  Влад добавляет строку allow; (2) по темам (`calendar.md`, `pantry.md`, `food.md`, `start.md`, `sleep.md`), в `day-plan.md`
  одна строка. Рекомендую 1 — `day-plan.md` на пределе (683 Б), пульт описан в пяти местах труднее читать тренеру; цена —
  одна строка allow (как в П3). Решает Влад.
- **Р10. Слова сигналов на вкладке «Состояние».** (1) Из справки: «короткая ночь», «долг сна», «возможно, заболеваешь»,
  «нагрузка три дня подряд», «работа по вечерам три дня», «работа в выходные», «восстановление хуже», «туду растёт»,
  «WHO-5 низкий / снижен / упал», отклонения дня («самочувствие», «настроение», «стресс», «готовность», «HRV», «сон»,
  «ATL выше CTL») — с числом `value` и порогом `limit`; (2) коды `kind` как в MCP. Рекомендую 1. Решает Влад.
- **Р11. Тренды.** (1) Пять графиков за 14 дней (сон ч, HRV, пульс покоя, готовность) и вес за 30 дней, SVG как CTL · ATL
  (П3 Р4 = 1), точка на правом конце; (2) только сигналы, без графиков; (3) один график — готовность. Рекомендую 1 —
  «тренды» в тексте пункта 49, код общий с `week-pane.js` (`chart.js`). Решает Влад.
- **Р12. Порядок партий.** (1) правка плана (сервер → шкала) → шапка → еда → состояние — порядок строки П4 в ROADMAP;
  (2) шапка первой (самое дешёвое и ежедневное — синк и вес), потом план. Рекомендую 1. Решает Влад.
- **Р13. Шкала пустого дня** (ни пунктов, ни встреч не на весь день — `day.py:116` бар тогда 0/0, «На этот день ничего
  нет.»). (1) Шкала есть, рамка 08:00–22:00 (константа `scale-model.js`), блоков нет, клик в пустоту — форма нового
  пункта; плотность на телефоне 360 px / 840 мин ≈ 0,43 px/мин — как у Р1 (3). (2) Шкалы нет, остаётся только надпись;
  первый пункт дня — `coach plan day`, `coach event add` или тренер (новый пункт из пульта в пустой день невозможен).
  (3) Рамка от текущего часа: сегодня — now − 1 ч … now + 3 ч, другой день — как (1). Рекомендую 1 — пульт «рука Влада»
  (Р4), пустой день и есть случай, когда нужен первый пункт; (3) — две рамки на один экран, прыгает по часам. При Р13 = 1
  тест доебы: `frameOf(view([]))` → `[480, 1320]`, день только с `all_day` — то же. Решает Влад.
- **Р14. Строка синка в шапке при ошибке и во время синка** (партия 3; текст ошибки без токенов Garmin —
  «Токенов Garmin нет. Выполни: coach login», `garmin/client.py`). (1) «синк 17:13 · обновить» всегда по `finished_at`
  последней записи `sync_log` любого статуса; при `status != ok` — «синк 17:13 ошибка · обновить», а текст ошибки —
  строкой под шапкой (как под шкалой, П2 Р11), пока следующий синк не пройдёт; во время синка — «синк идёт…», кнопка
  неактивна, по окончании `load()`. (2) То же, но без слова «ошибка» в строке — только текст под шапкой. (3) Время
  последнего *успешного* синка (отдельный запрос по `status = ok`), ошибка — только текстом под шапкой. Рекомендую 1 —
  одна запись `last_sync_log` (`store/journal.py:240`), видно и когда, и что не так. Решено: 1 (кто решил: Влад,
  окно 2026-11-10, по рекомендации папы).
- **Р15. Десятичный разделитель в шапке.** Р2 = 1 записан как «сон 7,2 ч» (запятая); в пульте числа сегодня с точкой —
  «12.3 км» (`training-model.js:79`, `toFixed(1)`). (1) Точка, как везде в пульте («сон 7.5 ч»); (2) запятая по тексту Р2,
  только в шапке; (3) запятая везде — правка `training-model.js`, `week-pane.js:30` и тестов П3 (вне партии 3).
  Рекомендую 1 — один стиль, ввод веса «81,7» запятой сервер принимает в любом случае (как `parse_kg`). Решено: 1
  — точка (кто решил: Влад, окно 2026-11-10, по рекомендации папы).
- **Р16. Строки шапки без данных** (партия 3, отступление кабана — план текст не задавал; `header-model.js:12-33`).
  Вес не записан за 30 дней, синков в `sync_log` нет, у дня нет строки `daily_metrics` (будущий день, день до первого
  синка). (1) Как у кабана: «веса нет · записать», «синка не было · обновить», строка показателей пустая — ряд исчезает,
  шапка на день без данных ниже на одну строку. (2) Те же слова у веса и синка, у показателей — «показателей нет»: три
  ряда всегда, шапка не прыгает при листании дней. (3) Тире: «вес — · записать», «синк — · обновить», «показатели —».
  Решено: 2 (кто решил: Влад, окно 2026-11-10, по рекомендации папы).
  Рекомендую 2 — слова в манере «На этот день ничего нет.» / «сигналов нет» (Р10), ряд на месте; тесты доебы
  `header.test.mjs` (`metricsLine(null)` без `null`/`NaN`) зелёные при любом варианте. Решает Влад.
- **Р17. Когда коммитить партию с DOM-кодом (партии 4, 5; партия 3 — чек-лист пройден Владом 2026-11-10 14:03, «всё работает
  чётко», вопрос по ней снят).** Правило для партии 2 Влад дал окном 2026-11-10 («коммит после браузера», `:78-81`) и там же
  смягчил («коммитится сейчас, красное — партия 2б», `:90`); для партии 3 отдельного правила не было — папа вывел его из
  партии 2 по ошибке (свекровь, круг 4). (1) Коммит после чек-листа Влада в браузере: красное правится до коммита, в `main`
  только проверенное; минус — Влад на критическом пути каждой партии, большой дифф партий 4–5 (~210/~230 строк) висит в
  дереве до его окна. (2) Коммит после ревью мамы и аудита свекрови, до браузера; чек-лист блокирует только закрытие шага
  (как партия 1, `:581-582`); красное в браузере — партия «Nб» со своим ревью (как 2б); минус — в `main` может лечь
  непроверенный DOM, правка — отдельным коммитом. (3) Коммит после чек-листа на Mac, телефон — до закрытия шага.
  Рекомендую 2 — так партия 2 и прошла по факту (`:90`): красное всё равно стало партией 2б, конвейер не ждёт Влада,
  история по партиям чище; `main` — рабочий репо Влада без релизов, цена непроверенного коммита — один коммит-правка.
  Решает Влад. **Решено: 2** — кто решил: Влад, окно 2026-11-10, по рекомендации папы.
- **Р18. Строка таблицы кладовой** (партия 4; Р6 = 1 задал кнопки и поле, текст ячеек — нет). (1) Как `coach pantry list`
  (`cli/pantry.py:149`): остаток числом как есть («350 g», «2.5 pcs»), единицы `g`/`ml`/`pcs` из базы, «Годен до» — дата
  `YYYY-MM-DD`, нет срока — пусто; просроченная строка — красная, дата с пометкой «просрочен», истекающая (≤ 2 дней) —
  жёлтая с «скоро»; (2) единицы по-русски («г», «мл», «шт») и дата «6 ноя» — таблица перевода в `pantry-model.js`,
  расхождение с CLI и справкой `pantry.md`. Рекомендую 1 — то же, что видит тренер в `get_pantry` и Влад в CLI; перевод —
  отдельным шагом, если понадобится. Решает Влад. **Решено: 1** — кто решил: Влад, окно 2026-11-10, по рекомендации папы.
- **Р19. Форма добавления** (партия 4). (1) Четыре поля в одну форму под таблицей: название · количество · единица
  (кнопки `g · ml · pcs`, как кнопки вида у формы нового пункта Р5, по умолчанию `g`) · «годен до» (`<input type="date">`,
  необязательно) · «Добавить»; (2) только название и количество, единица `g`, срок — через CLI; (3) форма открывается по
  кнопке «+ продукт», как поле веса по «записать» (Р3), иначе таблица без формы. Рекомендую 3 — на телефоне таблица
  короче, форма нужна реже, чем «−»/«+»; поля — как в (1). Решает Влад. **Решено: 3** — кто решил: Влад, окно 2026-11-10,
  по рекомендации папы.
- **Р20. Предупреждение «списано больше остатка» и «Записано»** (партия 4; `record` возвращает `warning`,
  `pantry/service.py:87`). (1) Успех без предупреждения — всплывает «Записано» (`toast`, как у веса — П2в Р9 = 1);
  с предупреждением — его текст строкой под таблицей (как ошибки сервера, П2 Р11 = 1), держится до следующей записи,
  «Записано» не всплывает; (2) предупреждение — в тосте вместо «Записано», под таблицей только ошибки 400. Рекомендую 1 —
  тост исчезает, а «остаток 0» — повод для сверки. Решает Влад. **Решено: 1** — кто решил: Влад, окно 2026-11-10, по
  рекомендации папы.
- **Р21. Порядок блоков на вкладке «Еда»** (партия 4). (1) Кладовая сверху (таблица, форма), ниже блок КБЖУ (строка
  остатка дня + записи еды за день, Р7 = 1); (2) КБЖУ сверху, кладовая ниже. Рекомендую 1 — порядок текста BACKLOG 49
  («кладовая … и КБЖУ дня»), кнопки «−»/«+» — главное действие вкладки. Решает Влад. **Решено: 1** — кто решил: Влад,
  окно 2026-11-10, по рекомендации папы.
- **Р22. Как применяется поле «+N/−N» и как закрыть форму добавления** (партия 4, отступление кабана — план способ не
  задавал; `pantry-pane.js:rowNode`, `:addProduct`). У кабана: поле в каждой строке между «− остаток +», применяется
  только клавишей Enter, кнопки нет; форма «+ продукт» закрывается только после удачного «Добавить» (ни «Отмена», ни
  Escape). У веса (партия 3) — кнопка «OK» + Enter, Escape закрывает поле. (1) Поле — Enter без кнопки (как у кабана), форма
  закрывается Escape (горячая клавиша, как у веса — техническое, кабан ставит сейчас) и после «Добавить». (2) То же плюс
  кнопка «OK» у каждого поля и «Отмена» в форме — как у веса и формы нового пункта. (3) Одно поле «+N/−N» на таблицу
  (выбор продукта — клик по строке) с кнопкой «OK». Рекомендую 1 — в строке на телефоне уже две кнопки по 44 px и число,
  третья не влезает; клавиша «ввод» есть и на телефонной клавиатуре; при Р17 = 2 коммит партии не ждёт — если на
  чек-листе Enter окажется неочевидным, «OK» — партия 4б (~6 строк). Решает Влад. **Решено: 1** — кто решил: Влад, окно
  2026-11-10, по рекомендации папы.
- **Р23. Строка сигнала на вкладке «Состояние»** (партия 5; Р10 = 1 задал слова «с числом `value` и порогом `limit`», форму
  строки — нет; у двух из 18 сигналов `value`/`limit` не числа: `hrv` — статус строкой и список статусов
  (`load/deviations.py:46`), `recovery_drop` — словари по показателям (`load/overload.py:140`)). (1) «<слово> · <value>
  (порог <limit>)»: числа и строки как есть — «короткая ночь · 2 (порог 1)», «HRV · LOW (порог LOW, UNBALANCED, BELOW)»;
  список — через запятую, словарь — «ключ значение» через запятую: «восстановление хуже · readiness 12, mood 1.5 (порог
  readiness 10, mood 1, stress 1)»; источник (`sleep`, `overload`…) не показывается. (2) Только «<слово> · <value>», порог —
  во всплывающей подсказке строки. (3) Только слово, цифры — в подсказке. Рекомендую 1 — буква Р10 = 1 («с числом и
  порогом»), подсказок на телефоне нет (П2в Р3 = 2); грубая форма у двух редких сигналов приемлема, их словарь — тот же,
  что видит тренер в `get_overload`/`get_deviations`. Решает Влад.
  Решено: 1 — кто решил: Влад, окно 2026-11-10, по рекомендации папы.
- **Р24. Шкала Y графиков состояния** (партия 5; Р11 = 1 задал пять графиков «как CTL · ATL», у того шкала от 0 —
  `week-pane.js:60`). (1) От минимума до максимума ряда (`null` не считаются); ряд ровный — ±1; ряд пустой — графика нет,
  подпись «нет данных»; (2) от 0 до максимума, как CTL · ATL. Рекомендую 1 — HRV 55–65 и пульс 48–54 на шкале от 0 —
  прямая у верха, тренд не виден; CTL · ATL от 0 — потому что это накопление. Решает Влад.
  Решено: 1 — кто решил: Влад, окно 2026-11-10, по рекомендации папы.
- **Р25. Пропуски в рядах и даты веса** (партия 5; сервер отдаёт `null` за день без метрик — «Тесты», вес — только дни
  записей за 30 дней). (1) `null` — разрыв линии (одиночное значение между пропусками — кружок); вес — точки по записям
  равным шагом (как `chartPoints`), под осью — числа дней записей, как у недели (`chartAxes`: даты через одну). (2) `null` —
  соединять соседей линией через пропуск; вес — так же. (3) Вес — по календарю 30 дней с `null` между записями (при (1)
  каждая запись — одиночная точка, линии нет; осмысленно только с соединением (2)). Рекомендую 1 — разрыв честнее:
  «данных нет» не рисуется как значение; вес 8 записей за 30 дней — равный шаг читается как ряд замеров. Решает Влад.
  Решено: 1 — кто решил: Влад, окно 2026-11-10, по рекомендации папы.

Риски:
- EventKit из потока HTTP-обработчика (`CalendarWriter._open` → `_request_access`, `calendar_eventkit.py:48`,
  `threading.Event`) и из потока синка — на живом Календаре не проверено; partия 1 и 3 проверяют руками первыми; запас —
  подпроцесс `coach event move` / `coach sync` (ожидание ~20 строк замены в `plan.py`/`syncer.py`).
- `rebuild_plan_actual` при синке днём пишет `skipped` сегодняшней тренировке (BACKLOG 65) — кнопка «обновить» сделает
  это заметнее; правка в `load/*` не здесь.
- Перетаскивание на телефоне: точность 0,46 px/мин (Р1 = 1), конфликт с прокруткой; смягчение — `touch-action: none`
  только у шкалы, порог 4 px, снап.
- Ctrl-C серверу во время синка — поток гибнет, строки «ok» в `sync_log` нет; следующий `coach sync` всё перепишет.
- `coach-help/pult.md` (Р9 = 1): переезжающий раздел `day-plan.md:14-22` — 4562 Б (`wc -c` 2026-11-10), предел темы
  `HELP_TOPIC_LIMIT = 8192` (`tests/test_skills_help.py:48`) — на четыре новых раздела 3630 Б (~900 Б на раздел,
  измерено); не влезает — сокращать переезжающий текст (не разносить по темам — Р9 = 1), кабан меряет `wc -c` до коммита.
- `pult.css` 885 → ~1035 строк, `server.py` 164 → ~210: `qlty smells` может дать новые пункты при `SMELLS_MAX = 0`
  (BACKLOG 58 уже красный) — выносы в `*-model.js`/`web/*.py` по образцу П3.
- Пульт без пароля (П1 Р6 = 1): теперь любой в сети может двигать план, писать вес и кладовую, запускать синк —
  решение Влада П1/П2 действует; в справке — одной строкой.

## Умолчания (внутреннее)

- Имена: `web/plan.py`, `header.py`, `syncer.py`, `pantry.py`, `state.py` (рядом с `food.py`, `training.py`); JS —
  `scale-*`, `header-pane`, `pantry-*`, `state-*`, `dom.js`, `chart.js`. Миграций нет: все записи — в существующие таблицы.
- Синк из пульта — поток-демон в процессе сервера (не подпроцесс: `ai_coach.cli.main` без `__main__`, путь `coach` в
  `sys.argv[0]` ненадёжен), `days = 7`, `pause = 0.5` — как `coach sync` по умолчанию; статус модульный, один на процесс.
- `header.metrics` — за день просмотра; `weight` — последняя запись за 30 дней до дня включительно; `sync` — всегда
  последняя (`last_sync_log`), не по дню.
- Шкала: редактируются только `items` тренера (`source: item`); повтор (`repeat != null`) — замок без захвата (Н23 Р5 = 1);
  прошедшие пункты двигать можно (сервер и так разрешает −30 дней — «правка на ходу» и дозаполнение); левый край не
  тянется (при Р1 = 1 правый край = длительность); пересечения блоков не запрещаются (как у `validate_draft`).
- `dragOutcome` не даёт длительность < 5 мин и конец ≤ начала — проверка и на сервере (`validate_draft`).
- Перенос и длительность зажаты в сутки строки (при Р1 = 1, предложил папа, решил Влад окном 2026-11-10); перенос на
  соседний день — CLI или тренер. Событие, уже идущее через полночь, зажим не обрезает: вперёд не двигается, конец не
  растёт, назад и укоротить можно (мама, круг 2).
- Виды нового пункта (Р5 = 1): форма партии 2 показывает `task · focus · rest · meal`; сервер в партии 1 принимает те же
  четыре (`PULT_KINDS`, «API и модель») — форма и сервер сходятся; тренировки, практики, чек-ины — не из пульта ни с какой
  стороны. Текст 400 виден только не-форме (форма чужой `kind` не шлёт) — умолчание.
- Тесты партии 1 к ветвям выше (под mutmut `ai_coach.web.plan:*`): `resize` без `end_at` → `MarkError`, ничего не сдвинуто;
  `id: "7"` и `id: true` → `MarkError` (не `NoEvent`), событие 1 на месте; `kind: "training"`, `"checkin"` → `MarkError`,
  в `coach_events` ничего.
- Ошибки — два слоя по П2 Р10 = 2: тексты сервера под шкалой/в блоке, протокольные — «Не сохранилось, ошибка пульта (код N)».
- `pantry_view.rows` — порядок `stock()` (по алфавиту), `expired` и `soon` (≤ 2 дней, `expiring(days=2)`) — флаги строк
  относительно дня просмотра `day` (тест доебы `test_view_flags_depend_on_viewed_day`); при Р7 = 1 `remaining` —
  `meal_view(conn, day, profile_nutrition(conn, day, current_profile(conn, day)))["remaining"]` (как `day.py:64-67`),
  `food` — `list_food(conn, day, day)` с ключами `id, text, kcal, logged_at` (как `marks_for_day`, `marks.py:183`).
- `save_pantry`: `PULT_OPS = ("add", "use", "set", "spoil")` — `open` из пульта не делается (нужен срок, кнопки нет); чужой
  `op` → `MarkError` «op: add, use, set или spoil.»; `qty` — число, не bool (`None`/нет ключа — только у `spoil`), иначе
  «qty: нужно число.»; `item` не строка → «item: нужно название.»; остальное (пустое имя, единица, срок `until`, «нет дома»,
  `qty ≤ 0`) — тексты `ValueError` из `record`/`spoil` без правки. `spoil` без `qty` → `spoil(conn, item, None, None, now,
  today)` (весь просроченный, `unit` не читается), с `qty` — `spoil(conn, item, qty, unit, now, today)` (FIFO, как CLI);
  `today = now.date().isoformat()`, `now` — `isoformat(sep=" ", timespec="seconds")` (формат `cli/pantry.py:25`).
- `pantryRows(view, today)` → `[{item, qty, unit, step: stepFor(unit), until: expires_on ?? "", state: "expired" | "soon" |
  "", spoil: expires_on !== null && expires_on < today}]`: `state` — класс строки по флагам сервера (день просмотра),
  `spoil` — кнопка «Списать просроченное» по настоящему `today` (`document.body.dataset.today`, `pult.js:145`), чтобы
  сервер не ответил «нет просроченного остатка» при просмотре будущего дня; на сегодняшнем дне `spoil === (state ===
  "expired")`. Тексты ячеек — Р18.
- Вкладка «Еда»: `loadPantry(day, today)` в `pantry-pane.js` по образцу `loadWeek` (`week-pane.js:70`): вызов при открытии
  вкладки и из `load()` таймера, когда панель видна (`pult.js:146, :168`), после каждого POST — повтор; ошибка запроса —
  строкой под таблицей. Поля ввода кладовой лежат вне `.pane` — `typing()` их не видит (`pult.js:128`): `pantryBusy()`
  (фокус в поле или идёт POST), `typing()` += `|| pantryBusy()`, как `headerBusy()`. `toast` — третий потребитель: вынос в
  `static/toast.js` в этой партии (предложение из «Правок», партия 3; `marks.js`, `header-pane.js` импортируют оттуда).
- `state_view.signals` — пять источников по дню просмотра, порядок строк и значения `source`: `sleep` (`sleep_report(day,
  now)`), `illness` (`illness_report(day, tss, sleep)`), `overload` (`overload_report(day, tss)`), `who5` (`who5_report(day)`),
  `deviations` (`day_deviations(conn, day, load_row)`, `mcp_server/tools.py:234`); один вызов `tools.load(day-13, day)` даёт
  и `tss` (`{date: tss}` по `rows`, как `snapshot.py:167`), и `load_row` (последняя строка); `ToolError` → `tss = {}`,
  `load_row = None`, `load_error = str(error)` («В базе нет свежего … пульса покоя из сна. Сделай coach sync.»,
  `tools.py:342`), сон, болезнь, WHO-5 и отклонения без нагрузки всё равно считаются (как `deviations()`, `tools.py:252`).
  Отчёты импортируются в `web/state.py` по имени как атрибуты модуля (`from ai_coach.load.illness import illness_report`) —
  тесты доебы подменяют `ai_coach.web.state.illness_report`/`overload_report` (прецедент — `syncer.load_client`, партия 3).
  `source` пользователю не показывается (при Р23 = 1). `trends` — `list_daily_metrics`/`list_recovery_days` за 14 дней,
  `list_weights` за 30 (граница как у шапки: `day − 30` входит, `day − 31` — нет).
- `state-model.js` (партия 5): `SIGNAL_WORDS` — 18 кодов, слова Р10 = 1 (`short_night` «короткая ночь», `sleep_debt`
  «долг сна», `illness_risk` «возможно, заболеваешь», `total_streak` «нагрузка три дня подряд», `evening_streak` «работа
  по вечерам три дня», `weekend_work` «работа в выходные», `recovery_drop` «восстановление хуже», `todo_growth` «туду
  растёт», `who5_low` «WHO-5 низкий», `who5_reduced` «WHO-5 снижен», `who5_drop` «WHO-5 упал», `wellbeing` «самочувствие»,
  `mood` «настроение», `stress` «стресс», `readiness` «готовность», `hrv` «HRV», `sleep` «сон», `atl_over_ctl` «ATL выше
  CTL»); неизвестный код → сам код (сервер добавил сигнал — строка не пропадает). `trendSeries` — `label` по словам Р11 = 1:
  «сон, ч», «HRV», «пульс покоя», «готовность», «вес, кг»; `dates` у четырёх рядов — `trends.dates`, у веса — даты записей.
- `state-pane.js`: `loadState(day, today)` по образцу `loadPantry` (вызов при открытии вкладки и из `load()` таймера у
  видимой панели, `pult.js:148-149, :173`); полей ввода нет — `stateBusy()` не нужен; ошибка запроса — строкой под
  сигналами (П2 Р11 = 1). Пять графиков — `lineChart` из `chart.js`, размер и оси как у CTL · ATL (320×140, `PAD`,
  `chartAxes`), одна линия и кружок на последнем непустом значении; `.sig`, `.trend` — в обеих темах.
- `dom.js` снимает шесть копий `el` (BACKLOG 66 закрывается партией 2); `chart.js` — вынос из `week-*` без смены поведения
  (тест `chartPoints` меняет импорт).
- Таймер `pult.js` при `dragging` и при открытом поле веса не перерисовывает: `typing()` ловит `INPUT` только внутри
  `.pane` (`pult.js:124`), для шапки — `headerBusy()` («Правки по ревью», партия 3).
- Тесты JS — чистые функции в `*-model.js`, DOM — руками (правило П2в).

## Открытые вопросы

Р1–Р12 — «Развилки». Первые блокируют партии: 1 — Р4, Р5 (сервер `create`); 2 — Р1, Р13; 3 — Р2, Р3; 4 — Р6, Р7, Р8; 5 — Р9,
Р10, Р11; порядок — Р12.

1. Р4 — новый пункт черновиком или сразу в календарь (`agenda/service.py:153 create_draft`, `:178 write_event`); рекомендую 2;
   разблокирует партию 1; решает Влад.
2. Р1 — вид шкалы (`scale-model.js` новая); рекомендую 1; разблокирует партию 2; решает Влад.
3. Р9 — куда справку (`coach-help/day-plan.md:14-22`); рекомендую 1 (+ строка allow Влада); разблокирует партию 5 и
   «Вне репо»; решает Влад.
4. Р2, Р3, Р5–Р8, Р10–Р12 — рекомендую 1 во всех, кроме Р4 = 2; решает Влад окнами по одному (okna.md).
5. Р13 — шкала пустого дня (`scale-model.js:frameOf`, новая); рекомендую 1; разблокирует тест `frameOf` пустого дня и
   партию 2 (2026-11-10); решает Влад.
6. Р14, Р15 — строка синка при ошибке и десятичный разделитель (`header-model.js:syncLine`, `:metricsLine`, новые);
   рекомендую 1 в обоих; разблокируют `header-model.js` и тесты `tests/web/header.test.mjs` партии 3 (сервер и тесты
   доебы по Python от них не зависят — кабан начинает с них); решает Влад.
7. Р16 — строки шапки без данных (`header-model.js:metricsLine`, `:weightLine`, `:syncLine`); рекомендую 2; разблокирует
   коммит партии 3 (код кабана = вариант 1, правка ~2 строки); решает Влад.
8. Р18–Р21 — строка таблицы кладовой, форма добавления, предупреждение и «Записано», порядок блоков (`pantry-pane.js`,
   `pantry-model.js:pantryRows` — новые); рекомендую 1, 3, 1, 1; разблокируют DOM партии 4 (сервер `web/pantry.py` и
   тесты доебы по Python и `stepFor`/`parseDelta` от них не зависят — кабан начинает с них); решает Влад окнами.
9. Р22 — поле «+N/−N» только Enter, форма добавления без «Отмена» (`pantry-pane.js:rowNode`, `:addProduct`); рекомендую 1;
   коммит партии 4 не блокирует (Р17 = 2), окно — вместе с чек-листом браузера; решает Влад.
10. Р23–Р25 — строка сигнала, шкала Y графиков, пропуски и даты веса (`state-model.js:signalRows`, `chart.js:valueRange`,
    `:chartSegments` — новые); рекомендую 1 во всех; разблокируют `state-model.js`, `chart.js` и тесты доебы к ним
    (`state.test.mjs` дописка); сервер `web/state.py`, `test_web_state.py`, Справка от них не зависят — кабан начинает с них;
    решает Влад окнами. Строка allow `Bash(cat .claude/agents/coach-help/pult.md)` — Влад, до коммита партии 5 («Вне ai-coach»).

## Правки по ревью

Партия 1, ревью мамы и аудит свекрови (2026-11-09):

- Сервер принимает только четыре вида пульта, чужой `kind` → 400 — исполнение Р5 = 1 Влада, срок и способ решил папа.
- Нестрочный `title` и `id` сверх диапазона sqlite → 400 вместо падения — мама, тексты папы.
- Большой `id` в `marks._event` → прежний `NoEvent` «Пункта нет.»; `MAX_ID` в двух модулях — кабан, принял папа;
  `marks.py` и `test_web_marks.py` добавлены в «Файлы».
- Удалена неиспользуемая `mark_reply`, сборка `values` в `_create` упрощена — мама, удаление решил папа.
- Добавлены тесты: `WorkloadConfigError` при create, `default_writer`, чужой `kind`, нестрочный `title`, большой `id`;
  усилены проверки ключа `error` и тела 404 — мама.
- `tests/test_cli_agenda.py` не меняется, в «Файлах» был по ошибке — папа.
- Ручная проверка EventKit: коммит партии 1 не блокирует, Влад проверяет до старта партии 2 — окно Влада 2026-11-09.
- Личные пути в «Смете» заменены на `~/…` — папа по замечанию мамы.

Партия 2, ревью мамы и аудит свекрови (2026-11-10):

- Перенос и длительность зажаты в сутки строки, три теста `dragOutcome` — вопрос мамы, решил папа.
- Край resize — `min(12 px, треть ширины)`: короткий блок теперь можно двигать — мама, решил папа.
- Подсказка времени над полосой, как в Р1 — свекровь, решил папа.
- Убран лишний реэкспорт `scale-model.js` из `pult.js` — мама и свекровь, решил папа.
- Два поля времени, клик 23:50 → 23:30–24:00, коммит после браузера — окна Влада 2026-11-10.
- `scale-pane.js` — мама: `pointercancel` откатывает без POST; «Создать» заблокировано на время POST; пустое время —
  ошибка текстом; блок возвращается после ошибки и при открытой форме; состояния нажатия, жеста и сохранения разделены,
  нажатие до порога защищено от перерисовки; только основная кнопка; текст из ответа 200 при сбое Календаря показывается;
  без сдвига POST нет; «Отмена» очищает ошибку.
- Клик после перетаскивания — `drag.quiet` со сбросом по `setTimeout 0` на любом `pointerup` блока; вариант мамы
  (`drag.active`) не подходит, флаг снимается до `click` — кабан, принял папа.
- Зажим в сутки — окно Влада 2026-11-10 («стоп у края суток»), по строке аудита свекрови, круг 2.
- Круг 2 мамы: событие через полночь зажимом не обрезается, два теста; при смене дня во время нажатия флаги жеста
  сбрасываются, подсказка скрывается.

Партия 2б:

- Форма — пять строк на любой ширине: строки «с … до …» и «Создать · Отмена» каждая во всю ширину (на
  широком окне вставали в один ряд, выходило четыре) — аудит свекрови, окно Влада 2026-11-10 «пять строк
  всегда» (рекомендация папы).

Партия 3, тесты доебы (`tests/test_web_header.py`, `tests/test_web_syncer.py`, правки `tests/test_web_server.py`,
`tests/test_web_day.py`; разбор папы 2026-11-10 по коду, техническое — решил папа; Р14, Р15 — Владу):

- **Syncer: подмена `syncer.load_client`, настоящие `run_sync`/`run_workload`** — принято, лучше плана: так идёт
  `tests/test_cli_sync_workload.py:64` (`main.load_client` → `FakeGarmin()`), `run_sync` с `FakeGarmin` пишет `sync_log`
  сам, `time.sleep` подменён. Безопасно: autouse `tests/conftest.py:11 no_real_workload` даёт конфиг без календарей и
  tmp-пути → `sync_workload` (`workload_sync.py:237 config.has_calendar` False) к `CalendarReader`/EventKit не ходит;
  подмена `workload_sync.CalendarReader` в `db`-фикстуре лишней не мешает. Контракт `syncer.py`: `from
  ai_coach.garmin.client import load_client`, `from ai_coach.sync import sync as run_sync, sync_workload as
  run_workload` — атрибутами модуля (иначе подмена не сработает). Поток: `conn = open_db(db)`; `GarminError` (в т. ч.
  `GarminAuthError`) → `error = str(e)`, **нагрузка всё равно идёт** (как `cli/main.py:150-156`); любое другое `Exception`
  → `error = str(e)` + traceback в stderr (поток-демон молча падать не должен); `running = False` в `finally`;
  `started_at` — `datetime.now().isoformat(timespec="seconds")` (формат `sync_log.started_at`); новый `start` сбрасывает
  `error` (тест `test_successful_run_clears_previous_error`). Тест `wait_idle` при подменённом `time.sleep` крутится
  вхолостую до 5 с — принято, не блокирует.
- **`save_weight(conn, payload, now) → {"id"}`** — принято, как в «API и модель». `measured_at = now.isoformat(sep=" ",
  timespec="seconds")` — формат CLI `now()` (`cli/journal.py:60`). Разбор `kg`: число или строка, запятая → точка,
  `float`; `bool`, `None`, «abc», отсутствие ключа → `MarkError` «Вес должен быть числом…»; вне 20–300 (19.9, 301) →
  `MarkError` «Вес должен быть от 20 до 300 кг.» — тексты `parse_kg` (`cli/journal.py:98`), саму `parse_kg` не звать
  (`fail` → `typer.Exit`). `web` из `cli` не импортирует (прецедента нет): `MIN_WEIGHT_KG`, `MAX_WEIGHT_KG` переезжают в
  `store/journal.py`, `cli/journal.py` импортирует их оттуда — «Файлы».
- **`header_view`** — принято: `metrics` из `get_daily_metrics(conn, d)` (`readiness ← readiness_score`, `sleep_h ←
  round(sleep_seconds / 3600, 1)`, `hrv ← hrv_last_night`) и `rhr` из `list_recovery_days(conn, d, d)` (`garmin_data.py:66`,
  `_REST_HR_SQL` — `$.sleep.restingHeartRate` или метрика HR импорта; тест доебы с `raw_json.sleep.restingHeartRate` ему
  соответствует); нет строки дня → `metrics: None`, есть строка без поля → поле `null`. Вес — `list_weights(conn,
  (day − 30 дн).isoformat(), day.isoformat())[-1]` (`store/journal.py:17`, по дате `measured_at`): 30 дней назад — ещё
  показывается, 31 — уже нет; тесты доебы 29 и 37 дней верны, границу 30/31 добить (ниже). `sync` — всегда
  `last_sync_log` (`:240`, по id, любой `kind` и статус) + `syncer.status()["running"]`; **без записей `sync_log`** —
  `{"finished_at": None, "status": None, "running": False}` (форма постоянна, `running` осмыслен всегда), не `None`.
- **`POST /api/sync`: 202 JSON `{"started": true}`, 409 текст «Синхронизация уже идёт.»** — принято, как в «API и
  модель». Исполнение в `server.py`: маршруты `POST_ROUTES` остаются `(conn, payload, now) → dict` и 200 (`/api/weight`
  → `save_weight` входит туда); синк — отдельная ветка `post_reply`: после `_refusal` и разбора JSON (тело `{}` — объект,
  проходит) `if name == SYNC_PATH: return sync_reply(db)` — ему нужен путь `db`, а не `conn` (поток открывает свою
  базу), и статусы не 200/400. `_refusal` проверяет `name in POST_PATHS` (`frozenset(POST_ROUTES) | {SYNC_PATH}`).
  `do_POST`: Content-Type JSON при `status < 300` (сейчас `== 200`, `server.py:172` — 202 ушёл бы `text/plain`).
  Строка плана «`"/api/sync": syncer.start` в `POST_ROUTES`» снята.
- **`GET /api/sync`** — через `api(query, build)` с `sync_view(conn, day, now)` в `header.py` (`day`, `now` не
  читаются): `syncer.status() | {"last": {started_at, finished_at, status, message} | None}`. Тест доебы нужен (ниже).
- **`header-pane.js` без чистых функций** — не принято: тексты строк шапки по Р2 = 1 — чистые функции, выносятся в
  `header-model.js` (`metricsLine`, `weightLine`, `syncLine`), тесты `tests/web/header.test.mjs` (правило П2в: чистое —
  `node --test`, DOM — руками). Виды строк при ошибке и разделитель — Р14, Р15 (Владу). Поправка к «Умолчаниям»:
  `typing()` (`pult.js:124`) ловит ввод только внутри `.pane`; поле веса в `<header>` оно не увидит — `header-pane.js`
  экспортирует `headerBusy()` (поле веса открыто или идёт опрос синка), `typing()` += `|| headerBusy()`, как `scaleBusy()`.
  Опрос `/api/sync` раз в 5 с запускается и когда страница открылась при `header.sync.running` (синк запущен из другой
  вкладки или `curl`).
- **Тесты доебы — дополнить** (до кода, тем же стилем): `test_web_header.py` — вес ровно 30 дней назад (2026-10-08)
  показывается, 31 (2026-10-07) → `None` (константа под mutmut); `sync` без записей → `{"finished_at": None, "status":
  None, "running": False}`; строка дня без `readiness_score` → `metrics["readiness"] is None`, остальное на месте;
  `save_weight(conn, {"kg": True}, NOW)` → `MarkError` (bool — как `id` в партии 1); `sync_view` без логов → `last is None`,
  с логом — четыре ключа. `test_web_syncer.py` — `GarminAuthError` не отменяет нагрузку: после `wait_idle`
  `last_sync_log(conn)["kind"] == "workload"` (`workload_sync.py:36 KIND`) и `status()["error"]` — текст Garmin. `test_web_server.py` — `GET /api/sync` → 200, ключи `{running, started_at,
  error, last}`, `last is None` на пустой базе; `POST /api/sync` → заголовок `Content-Type: application/json` при 202;
  `POST /api/weight` с телом `[]` → 400 «Нужен JSON-объект.» (общая проверка, регресс области). Остальные тесты доебы
  — как написаны.

Партия 3, отступления кабана (разбор папы 2026-11-10 по `git diff HEAD`; техническое — решил папа, видимое — Р16 Владу):

- **Строки без данных** («веса нет», «синка не было», `metricsLine(null)` → `""`; `header-model.js:12-33`) — видимое
  Владу, развилка Р16 («Развилки»), код кабана = вариант 1; до окна не менять.
- **Текст ошибки под шапкой** (`#header-error`, `header-pane.js:errorText`, `:poll`, `:renderHeader`) — место и смысл
  приняты: исполнение Р14 = 1 (Влад 2026-11-10: «текст ошибки — строкой под шапкой, пока следующий синк не пройдёт»).
  Источник текста — **не принято, поправить**: найден регресс области. Без токенов Garmin `load_client` падает до
  `run_sync` (`syncer.py:39`), записи `sync` в `sync_log` нет, `run_workload` пишет `workload`/`ok`
  (`workload_sync.py:265`) → `last_sync_log` = `ok` → `header.sync.status == "ok"`; `poll()` показывает `status.error`
  и зовёт `reload()`, а `renderHeader` по `status == "ok"` тут же делает `showError("")` (`header-pane.js:105`) — текст
  Garmin стирается через один запрос; при открытии страницы его нет вовсе, строка — «синк 17:13» без слова «ошибка».
  Выход партии 3 «без токенов Garmin — текст ошибки» не выполняется. Правка (техническое, папа): один источник —
  `header_view` отдаёт `sync.error` = `syncer.status()["error"]`, иначе `last["message"]` при `last["status"] != "ok"`,
  иначе `None` (`web/header.py:header_view`, ~4 строки); `syncLine` пишет «ошибка», если `sync.status !== "ok" ||
  sync.error` (`header-model.js:syncLine` — исполнение Р14 = 1: сбой Garmin — тоже ошибка синка, видно «и когда, и что
  не так»); `renderHeader` показывает `header.sync.error` всегда (`showError(header.sync.error || "")`), `errorText`,
  `fetchStatus` при загрузке и ветка `status !== "ok"` в `renderHeader` снимаются, `poll()` после `running: false` —
  только `clearInterval` + `reload()` (ошибку принесёт `/api/day`). `GET /api/sync` остаётся только для опроса
  `running`. Тесты (доеба, до кода): `tests/test_web_header.py` — `test_header_sync_without_logs_has_constant_shape`
  и `test_header_sync_is_last_log_not_by_day` += `"error": None`; новые: `syncer._state["error"]` (monkeypatch) при
  последней записи `ok` → `sync["error"]` — текст Garmin; последняя запись `status: "error"`, `message: "…"` без ошибки
  потока → `sync["error"] == message`; обе — приоритет у потока. `tests/web/header.test.mjs` — `syncLine({finished_at,
  status: "ok", error: "Токенов Garmin нет…"}, idle)` → `/ошибка/`; `error: null` — без. `tests/test_web_server.py:746`
  (`set(header)`) не меняется. mutmut: `ai_coach.web.header:header_view` уже в списке («Тесты»).
- **`size="5"`, `inputmode="decimal"` у поля веса** (`index.html:20`) — принято: `inputmode` даёт цифровую клавиатуру на
  телефоне (П2в Р3 = 2), `size` — ширина под «81.7» без правила в `pult.css`; прецедентов `size`/`inputmode` в пульте нет
  (grep), первый — здесь.
- Прочее по диффу без замечаний: `headerBusy()` = поле веса открыто или идёт опрос (как в «Правках», партия 3);
  `button.link` 44 px на телефоне (П2в Р3 = 2); `Escape` закрывает поле веса, `Enter` пишет — умолчание кабана, принято
  (клавиши в пульте: `Enter` раскрывает строку, `pult.js:59`; `Escape` — первый случай, сверх кнопки «OK» и клика мимо,
  поведение по умолчанию у текстового поля браузера — не видимое решение, а горячая клавиша).

Партия 3, ревью мамы и аудит свекрови (2026-11-10; что исправлено — чьё решение):

- Открытое поле веса больше не останавливает таймер навсегда: `headerBusy()` — идёт опрос синка или фокус внутри
  `#weight-form` (`form.contains(document.activeElement)`, `header-pane.js:93`); клик мимо снимает занятость — мама (п. 1),
  её второй вариант, принял папа.
- Отказ `POST /api/sync` кроме 409 (403, 5xx, обрыв) — текст под шапкой, кнопка снова активна, опроса нет; 409 — опрос как
  при 202 (`startSync`, `header-pane.js:79`) — мама (п. 2), принял папа.
- Строка `daily_metrics` есть, все четыре поля `null` → «показателей нет» (`metricsLine`, `header-model.js:20`) — мама
  (п. 3) и свекровь, исполнение Р16 = 2 (Влад 2026-11-10); тест к этому — кабана, принят (отступления ниже).
- «Записано» после записи веса — `toast("Записано")` в `saveWeight` (`header-pane.js:74`) — свекровь, исполнение Р3 = 1
  («“Записано” всплывает», Влад 2026-11-09; П2в Р9 = 1); экспорт `toast` — отступления ниже.
- Счёт тестов доебы (замечание мамы, уточнение оркестратора 2026-11-10; папа проверил `grep -c '^def test_'` по новым файлам и
  `git diff 017262c | grep -c '^+def test_'`, снятых `^-def test_` нет): новых тестовых функций Python 39 — `test_web_header.py` 21,
  `test_web_syncer.py` 7, `test_web_server.py` 10, `test_web_day.py` 1; JS 16 в `header.test.mjs` (в файле 17 — семнадцатый
  кабана). Число 38 в записи оркестратора было неверным. Красная проверка (по записи оркестратора, папа не перепроверял):
  ранние порции красные только сборкой файла (`ImportError`, `ERR_MODULE_NOT_FOUND` — модулей ещё не было), поштучно
  подтверждены последние 5 из 5 и 7 из 7.
- `node --test tests/web/` в «Тестах» → `node --test "tests/web/*.test.mjs"` (`make player-test`, `Makefile:37`; каталог без
  маски на node 26 падает — П2в факт 9, docs/plan-p2v.md:190) — свекровь, поправил папа.
- Ручная проверка шапки и синка из пульта (EventKit из потока, телефон) — чек-лист партии 3 в «Открыто» (а)–(д): пройден
  Владом 2026-11-10 14:03 («всё работает чётко»), коммит партии 3 не блокирует. Правило «коммит после браузера» папа вывел
  из окна по партии 2 ошибочно — Влад его для партии 3 не давал, а по партии 2 смягчил (`:90`); свекровь, круги 2 и 4.
  Правило для партий 4–5 — развилка Р17 («Развилки»), окно Владу.

Партия 3, отступления кабана после ревью (разбор папы 2026-11-10 по `git diff 017262c`; техническое — решил папа):

- **`toast` экспортирован из `marks.js:48`, `header-pane.js:4` импортирует** — принято. Одна копия всплывашки: узел `ui.toast`,
  таймер и стиль `.toast` (`pult.css:791`) общие, вторая копия была бы BACKLOG 66 заново. Прецедент импорта панели из
  панели — `offers-pane.js:4` (`table` из `training-pane.js`); цикла нет (`marks.js` шапку не импортирует), `marks.js` уже
  загружен `pult.js:4`. В `dom.js` не переносить: там функции без состояния (`el`, `svgNode`), у `toast` — узел и таймер.
  Предложение, не требование: третий потребитель («Записано» кладовой, партия 4) — вынести `toast` в `static/toast.js`
  в той же партии; до него — как есть.
- **Тест `metricsLine` «строка дня, все поля пустые» (`header.test.mjs:94`) написал кабан** — принять, доебе не отдавать.
  Прецедент — партии 1 и 2: тесты по замечаниям мамы (чужой `kind`, большой `id`; зажим `dragOutcome`, круг 2 мамы) писал
  кабан, принял папа; по family.md:84 правки по замечаниям мамы идут кабану тому же id, доеба на круге ревью не зовётся.
  Тест в форме доебы (`assert.equal` на слово Р16 = 2), проверяет поведение, не код; отдельный вызов доебы ради одного
  assert — расход без пользы. Граница: кабан дописывает тест только по замечанию ревью к уже написанному доебой файлу;
  новые сценарии «Тестов» — доеба, до кода.

Партия 3, полный pytest (оркестратор 2026-11-10, режим «долго», `taskpolicy -b`):

- Упали 4 теста синка («синк не закончился»: потолок ожидания 5 с меньше длительности синка под фоновым приоритетом,
  27–54 с) и `test_cli_agenda` (BACKLOG 70, не от шага). Без `taskpolicy` — зелёные. Правка доебы: `WAIT` 5 → 60 с в
  `tests/test_web_syncer.py`, `WAIT_SYNC = 60` в `tests/test_web_server.py`; это потолки ожидания по готовности, проверки
  не ослаблены; прод-код не менялся. Под `taskpolicy -b` оба файла зелёные. Вопрос доебы, почему синк на `FakeGarmin`
  под фоновым приоритетом идёт 30–50 с, — открыт, на ревью мамы.
- Ревью мамы, круг 3: медленный синк — от тестов, не от кода: фикстуры `db` и `slow_sync` подменяют `time.sleep` пустой
  функцией, циклы ожидания крутятся без паузы и отнимают GIL у потока синка. Правка доебы по ревью мамы: `REAL_SLEEP =
  time.sleep` до подмены, ожидание через `REAL_SLEEP(0.01)` в `wait_idle` и teardown `slow_sync`; потолки `WAIT` и
  `WAIT_SYNC` вернулись к 5 с. Под `taskpolicy -b` оба файла зелёные, самый долгий тест 0,6 с.

Партия 4, тесты доебы (`tests/test_web_pantry.py` — 29 функций, `tests/test_web_server.py` +8, `tests/web/pantry.test.mjs` — 7;
разбор папы 2026-11-10 по коду; техническое — решил папа, видимое — Р18–Р21 Владу). Красные (прогон папы 2026-11-10):
`test_web_pantry.py` и `pantry.test.mjs` — сборкой файла (`ModuleNotFoundError: ai_coach.web.pantry`, `ERR_MODULE_NOT_FOUND`),
поштучно не подтверждены; серверные — 8 из 8 `FAILED` поштучно (`uv run pytest tests/test_web_server.py -k pantry -rA`:
маршрута нет → 404 вместо 200/400/403), `make lint` на `test_web_server.py` чист.

- **(1) `pantry_view(conn, day, now)` — три аргумента**, не обёртка и не `now=None`: все `build` в `api(query, build)`
  (`server.py:166`) — `day_view`, `week_view`, `sync_view` — трёхаргументные, `now` у `week_view`/`sync_view` не читается
  и помечен в докстринге (`server.py:120`, `header.py:59`); второй способ в репо не заводим. Доеба правит тесты: `pantry_view(conn, DAY, NOW)`
  (`rows_by_item` и прямые вызовы, ~12 строк), «Файлы» исправлены.
- **(2) `save_pantry(conn, payload, now)` → `{"warning": str | None}`** — принято: контракт `POST_ROUTES` (`server.py:76`,
  «Правки», партия 3), `today = now.date().isoformat()` — тот же момент, что `date.today()` рядом с `now()` в CLI
  (`cli/pantry.py:88`). Четвёртый аргумент в «Файлах» был ошибкой — исправлено.
- **(3) Тело `{op, item, qty, unit[, until]}`, ответ `{warning}`, ключи `food` — `text, kcal, logged_at`, `remaining` как у
  `meal_view`** — принято, совпадает с «API и модель» (`:259, :261`). `food` — ровно `id, text, kcal, logged_at` (как
  `marks_for_day`, `marks.py:183`; тест доебы проверяет три — четвёртый не мешает); `remaining` — `meal_view` с целью
  `profile_nutrition` (`day.py:64-67`), без профиля `None`. Детали разбора `payload` — «Умолчания» (`PULT_OPS`, bool,
  `open` не из пульта).
- **(4) `pantryRows(view, today)`** — форма результата в плане не была описана, папа задал в «Файлах» и «Умолчаниях»:
  `[{item, qty, unit, step, until, state, spoil}]`; `today` — кнопка списания по настоящему дню, `state` — по флагам
  сервера. Тесты доебы — ниже.
- **(5) I001 в `test_web_pantry.py`** — верно: ruff относит импорт к first-party по наличию модуля в `src` (подсказка ruff
  переносит именно `ai_coach.web.pantry` к `pytest`, остальные `ai_coach.*` на месте — проверено `uv run ruff check`
  2026-11-10); после `src/ai_coach/web/pantry.py` пройдёт. Коммитить файл тестов до модуля не нужно (коммит — партия
  целиком, RULES «Гигиена»), отдельной правки нет.
- Тесты по плану — сверка: «Тесты» требуют `expired`, `soon`, `+200 → add`, `-50 → use`, `warning`, `spoil` у непросроченного
  → ошибка, чужая единица → 400, сервер `GET /api/pantry` 200 и мусорная дата 400 — всё есть. Сверх плана и принято:
  граница `soon` (сегодня, 2, 3 дня), флаги по дню просмотра, `set`, нормализация имени, `until`, таблица плохих тел,
  `[1]` → «Нужен JSON-объект.», 403 без записи, `logged_at` запроса. Расхождений с решениями Влада нет; `qty == 200`
  против `REAL` sqlite — `200.0 == 200` в Python истинно, не ловушка.
- **Доебе дописать** (до кода, тем же стилем): `test_web_pantry.py` — `{"op": "open", "item": "рис", "qty": 0, "unit": "g",
  "until": "2026-12-01"}` → `MarkError`, в журнале пусто (иначе `record` его примет — `PULT_OPS` под mutmut); `spoil` с `qty`
  у непросроченного (`put` без срока, `{"op": "spoil", "item": "рис", "qty": 100, "unit": "g"}`) → `{"warning": None}`,
  остаток 400 (ветка `spoil(qty, unit)`); `spoil` с `qty` больше остатка → `warning` «остаток 0»; `set` с `qty: 0` →
  продукт исчезает из `rows` (сверка «0» в поле — Р6 = 1, `set` допускает 0); `pantry_view` после `save_pantry` «молоко»
  со сроком `2026-11-06` при `DAY` → `expired`, после `spoil` без qty — строки нет. `tests/web/pantry.test.mjs` —
  `pantryRows`: строка без срока → `{until: "", state: "", spoil: false}`; `expired: true`, `expires_on: "2026-11-06"`,
  `today: "2026-11-07"` → `state: "expired", spoil: true`; `soon: true` → `state: "soon", spoil: false`; `expired: true`
  при `today` раньше срока (день просмотра в будущем: `expires_on: "2026-11-08"`, `today: "2026-11-07"`) → `state:
  "expired", spoil: false`; `step` по единице; порядок строк как в `view.rows`. `parseDelta("0")` → `{op: "set", qty: 0}`
  (сверка «ничего не осталось»), `parseDelta("-0")`/`"+0"` → `null` (списать/добавить ноль нечего). Серверные — как
  написаны. Поштучный прогон красных — как в партии 3.

Партия 4, отступления кабана (разбор папы 2026-11-10 по `git diff HEAD` и новым `pantry.py`, `pantry-model.js`, `pantry-pane.js`,
`toast.js`, `post.js`; техническое — решил папа, видимое сверх Р18–Р21 — Р22 Владу; тесты зелёные по слову кабана, папа прогнал
только пробу `save_pantry` ниже):

- **`static/post.js`: `postJson` вынесен из `header-pane.js`, ответ += `body`** — принято. Два потребителя (`header-pane.js:4`,
  `pantry-pane.js:6`), вторая копия была бы BACKLOG 66 заново; `body` нужен кладовой ради `warning` из ответа 200 (Р20 = 1),
  шапка его не читает — поведение веса и синка не меняется (`text: ""` при `ok` как раньше). Имя `post.js` — рядом с `dom.js`
  (функции без состояния), в `dom.js` не кладём: там DOM, тут сеть. В «Файлы» добавлен. Не в этой партии: `marks.js:75` и
  `scale-pane.js:41` шлют POST своим кодом (третья и четвёртая копия разбора ответа) — вне области партии 4, объединение —
  пункт BACKLOG (оптимизация), не сейчас (правило 9: регресс в области — в партию, оптимизации — в бэклог).
- **`static/toast.js` уже в этой партии** — принято, ровно предложение папы из партии 3 («третий потребитель — вынести в той же
  партии», `:663`): `marks.js`, `header-pane.js`, `pantry-pane.js` импортируют оттуда, узел и таймер одни, `.toast` в `pult.css`
  не тронут, `ui.toast` из `marks.js` снят. В «Файлы» добавлен.
- **«просрочен» / «скоро» рядом с датой, строка красная / жёлтая** (`pantry-pane.js:71`, `pult.css .pantry tr.expired/.soon`) —
  не отступление: дословно Р18 = 1 (Влад 2026-11-10: «дата с пометкой «просрочен»… жёлтая с «скоро»»). Остаток «350 g»,
  дата `YYYY-MM-DD`, пусто без срока — тоже Р18 = 1. Принято.
- **Поле «+N/−N» в каждой строке** — принято как исполнение Р6 = 1 («− остаток +» и поле; Р18 прямо говорит, что кнопки и поле
  задал Р6). Способ применения (только Enter) и закрытие формы без «Отмена» — видимое, план не задавал → **Р22** («Развилки»),
  код кабана = вариант 1 без Escape; Escape у формы — кабан ставит сейчас (горячая клавиша, прецедент поля веса
  `header-pane.js:100`, принято папой в партии 3 `:628`), остальное — до окна не менять.
- **Тексты** — приняты, развилки не дают: «Дома ничего нет.» — то же слово, что `coach pantry list` на пустой кладовой
  (`cli/pantry.py:144`) — исполнение Р18 = 1 «как CLI»; «Записей еды за день нет.» — пустой список записей Р7 = 1 в манере
  «На этот день ничего нет.» / «сигналов нет» (Р16 = 2); «Нужно число: +200, -50 или 120.» — отказ клиента на `parseDelta →
  null`, три формы — слова Р6 = 1, показывается там же, где ошибки сервера (П2 Р11 = 1). Строка остатка КБЖУ — `remainingText`
  из `marks-model.js:129` (без цели — «Цель на день не задана.»), тот же текст, что в окне еды — Р7 = 1 «как в окне еды».
- **`save_pantry`: `until` не строкой** — **не принято, поправить** (регресс области, правило 9): `{"until": 5}`, `true`, `["x"]`
  → `_check_expiry` (`pantry/service.py:48`) падает `TypeError: fromisoformat: argument must be str`, `except ValueError`
  (`web/pantry.py:63`) его не ловит, `post_reply` — тоже (`server.py:113` ловит только `MarkError`) → обработчик падает,
  ответа нет (проверено `uv run python` 2026-11-10). Правка (техническое, папа): в `save_pantry` после `unit` — `until =
  payload.get("until")`; `if until is not None and not isinstance(until, str): raise MarkError("until: нужна дата
  YYYY-MM-DD.")` (текст — как у `date` в `api`, `test_web_server.py:test_get_pantry_garbage_date_is_400_with_text`); ~2 строки.
  Тест — кабан дописывает в таблицу `test_save_bad_payload_is_mark_error_and_writes_nothing` (`tests/test_web_pantry.py:276`)
  две строки: `{"op": "add", "item": "рис", "qty": 1, "unit": "g", "until": 5}` и `"until": True` (по замечанию ревью к файлу
  доебы — граница из партии 3 `:668`; `ai_coach.web.pantry:save_pantry` под mutmut уже в «Тестах»). `unit` не строкой —
  проверено: `record` отвечает `ValueError` «Единица должна быть из …» на любой тип → 400, правки не нужно.
- Прочее по диффу без замечаний: `pantry_view` — три аргумента, флаги по дню просмотра, `FOOD_KEYS` — четыре ключа («Правки»,
  тесты доебы); `POST_ROUTES["/api/pantry"]` и GET через `api(query, build)` — как в «Файлах»; `pantryBusy()` — идёт POST или
  фокус в `INPUT` видимой панели (`panel.contains(active)` — `null` безопасен); `write()` чистит заметку перед записью —
  «держится до следующей записи» Р20 = 1; форма — поля Р19 (1), кнопки `g · ml · pcs` с `aria-pressed`, по умолчанию `g`,
  открывается по «+ продукт» (Р19 = 3), после удачи `reset()` и скрыта; порядок карточек — кладовая, затем КБЖУ (Р21 = 1);
  `inputmode="decimal"` у количества — как у веса (`:624`), у поля `+N/−N` его нет намеренно (на iOS у decimal нет «+»/«−»);
  44 px на телефоне (П2в Р3 = 2); таймер зовёт `loadPantry` только у видимой панели (как `loadWeek`).
- Не от кабана: в дереве неотслеживаемый `str_me` (одна строка — команда `claude --resume` этой сессии, артефакт среды) — в
  коммит не брать; удалить — по «да» Влада (RULES «Гигиена»).

Партия 4, ревью мамы и аудит свекрови (круг 1, 2026-11-10): свекровь — чисто; мама — одно замечание:
медиаблок `@media (max-width: 520px)` с 44 px для `.pantry button, .pf button` в `pult.css` дублировал общий блок «Телефон
(Р3)» — кабан удалил (техническое, по ревью мамы), node 195/195, `make lint` чист. BACKLOG не заводился.

Партия 5, тесты доебы (`tests/test_web_state.py` — 19 функций, `tests/web/state.test.mjs` — 8, `tests/test_web_server.py` +3,
`tests/test_skills_help.py` +6, `tests/web/pult.test.mjs` — четыре теста `chartPoints` импортируют `chart.js`; разбор папы
2026-11-10 по коду; техническое — решил папа, видимое сверх плана — Р23–Р25 Владу). Красные (прогон папы 2026-11-10):
`test_web_state.py` — сборкой файла (`ModuleNotFoundError: ai_coach.web.state`), поштучно не подтверждены; серверные — 3 из 3
`FAILED` поштучно (`-k state`: маршрута нет); справка — 6 из 6 `FAILED` поштучно (`pult.md` нет, индекс без строки);
`state.test.mjs` 0/8, `pult.test.mjs` 4 красных из 77 (`chart.js` нет), `node --test "tests/web/*.test.mjs"` — 191/203; ruff —
I001 на `test_web_state.py` (та же причина, что у партии 4 (5): модуля в `src` ещё нет, пройдёт сам), `ruff format` чист.

- **(1) `signalRows(state)` — массив строк в порядке сервера, строка со словом, `value` и `limit`** — принято, контракт
  задан в «Файлах»: `[{kind, source, word, detail}]`, `word = SIGNAL_WORDS[kind] ?? kind`, `detail` — по Р23 (тест доебы
  проверяет через `JSON.stringify` — любой вариант Р23 с числами в строке его проходит). Порядок — порядок `signals` сервера
  («Умолчания»: `sleep`, `illness`, `overload`, `who5`, `deviations`), без группировки по источнику.
- **(2) `trendSeries(state)` → `[{key, values}]`, ключи `sleep_h, hrv, rhr, readiness, weight`, у веса — числа kg** —
  принято; сверх того у ряда `label` (слова Р11 = 1) и `dates` (у веса — даты записей): графику нужны подписи оси, а
  `chartAxes` читает `row.date` (`week-pane.js:33`). Тесты доебы на `key`/`values` совместимы.
- **(3) `SIGNAL_WORDS.short_night == "короткая ночь"`, `.sleep_debt == "долг сна"`** — принято, это Р10 = 1 (Влад
  2026-11-09); полный словарь 18 кодов — «Умолчания» (сверено по `load/*.py`: `sleep` 2, `illness` 1, `overload` 5,
  `who5` 3, `deviations` 7 — `grep -n '"kind"'`).
- **(4) `source` только на непустоту** — принято как минимум; значения `source` — имена отчётов («Умолчания»), доебе
  добить `== "sleep"` у `short_night` (одна строка).
- **Не покрыто (DOM `state-pane.js`, темы, графики)** — по правилу П2в (DOM — руками): чек-лист партии 5 в «Открыто»,
  коммит не блокирует (Р17 = 2). Графики — чистая часть выносится в `chart.js` и тестируется: `chartSegments(values, box)` и
  `valueRange(values)` («Файлы»; при Р24/Р25 = 1), DOM `lineChart` — руками.
- **Сигналы `illness`/`overload`/`who5`/`deviations` не тестируются** — не принято как есть: `state_view` под mutmut
  (`ai_coach.web.state:*`, «Тесты») — пропущенный вызов отчёта выжил бы. Доебе дописать (ниже).
- **Иглы `tests/test_skills_help.py:123-133`** — не принято, поправить: `test_day_plan_topic_describes_pult_marks` и
  `test_day_plan_topic_points_pult_windows_to_food_and_training` читают `day-plan.md` («дозаполн», «истори», «в сети», точная
  строка «Еда и тренировка - окна в …»), а новый `test_day_plan_topic_points_pult_to_pult_md` требует, чтобы раздела в
  `day-plan.md` не было — вместе не пройдут. По плану («Справка», Р9 = 1: «иглы `:123-137` читают `pult.md`») обе иглы
  переводятся на `topic("pult.md")` (имена — `test_pult_topic_…`), `:135` (индекс) остаётся.
- **`test_allow_has_every_topic_file` (`:65`)** — красный с появлением `pult.md` до строки allow Влада («Вне ai-coach»,
  прецедент П3); строка нужна до коммита партии 5 — иначе `make check` красный в `main`. Напоминание — «Открытые вопросы» 10.
- **Дубль `chartPoints` в `state.test.mjs:67`** — то же поведение, что `pult.test.mjs:514` (первая точка на `x0`, последняя
  на `x1`) — снять, одно поведение — один тест; четыре теста в `pult.test.mjs` с импортом из `chart.js` — как написаны.
- **`chartAxes` при переезде** — регресс в области (правило 9): `week-pane.js:29-30` рисует линии и подписи по модульному
  `BOX`, а не по аргументу `box`; в `chart.js` графики состояния другого размера сломались бы — кабан переводит на `box`
  (при том же `BOX` у «Тренировок» поведение не меняется). DOM — тестом не покрыть, проверка — чек-лист (е).
- **Доебе дописать** (до кода, тем же стилем): `test_web_state.py` — отклонение дня из данных: `put(conn, DAY, 4)` → в
  `kinds` есть `sleep` (4 ч < `SLEEP_MIN_HOURS = 6`, `load/deviations.py:11`), `source == "deviations"`; `put(conn, DAY, 7,
  readiness=30)` → `readiness` (`READINESS_MIN = 33`); WHO-5 — `add_who5` (`store/journal.py:207`) с баллом ≤ 28 на `DAY` →
  `who5_low`, `source == "who5"`; подмена `monkeypatch.setattr("ai_coach.web.state.illness_report", …)` и `…overload_report`
  функциями, отдающими `{"signals": [{"kind": "illness_risk", "value": 2, "limit": 2}]}` / `{"signals": [{"kind":
  "total_streak", …}]}` → оба в `kinds` с `source` `illness`/`overload`; порядок источников при сигналах сна и отклонений
  одновременно (`nights(conn, 4, rhr=50)` даёт и `short_night`, и `sleep`): сначала `sleep`, потом `deviations`; `load_error`
  содержит «coach sync» (текст `tools.py:342`); вес ровно 30 дней назад (`2026-10-08`) в `trends.weight` есть, 31
  (`2026-10-07`) — нет (граница как у шапки, константа под mutmut). `state.test.mjs` — `Object.keys(SIGNAL_WORDS)` —
  18 кодов из «Умолчаний» (deepEqual списка); `signalRows` с неизвестным `kind: "x"` → `word === "x"`; `trendSeries` —
  `label` пяти рядов и `dates` веса `["2026-10-20", "2026-11-07"]`; при Р23 = 1 — `detail` для `DEBT` → `"3.5 (порог 3)"`,
  для `hrv` со строкой и списком, для `recovery_drop` со словарями; при Р24 = 1 — `valueRange([60, 64, null])` → `{min: 60,
  max: 64}`, `valueRange([5, 5])` → `{min: 4, max: 6}`, `valueRange([null])` → `null`; при Р25 = 1 — `chartSegments([1, null,
  3], box)` → два отрезка по одной точке, `[1, 2, null, 3, 4]` → два по две, `[null, null]` → `[]`, x — по индексу во всём
  ряду (как `chartPoints`). Тесты к Р23–Р25 — после окон Влада, остальные — сразу. Поштучный прогон красных — как в партии 3.

Партия 5, отступления кабана (разбор папы 2026-11-10 по `git diff HEAD` от 010ae0c и новым файлам; техническое решил папа,
видимого сверх Р23–Р25 нет):

- **`loadState(day)` без `today`** (`state-pane.js:44`) — принято: флагов по дню просмотра у вкладки нет, `today` не читался
  бы; «Файлы» (`loadState(day, today)`) — описка плана, контракт — по коду.
- **Общий класс `value`, `.chart .value` / `circle.value`** (`pult.css:831`, `:835`) — принято: каждый из пяти графиков — свой
  SVG с одним рядом, различать цвета внутри графика нечего; цвет у ряда один на все графики — видимое только в теме,
  проверка — чек-лист (д).
- **`GET_VIEWS` вместо elif-веток GET** (`server.py:127`, `:157`) — принято: тот же стиль, что `POST_ROUTES`, поведение
  маршрутов не меняется (серверные тесты `/api/day`, `week`, `pantry`, `state`, `sync` — гарантия), снимает smell
  `make_server`.
- **`week-pane.js` через `lineChart` из `chart.js`** — принято, это план («Файлы»); DOM — чек-лист (е), коммит не блокирует
  (Р17 = 2), красное — партия 5б.
- **Одиночная точка — малый кружок, последнее значение — кружок r 3.5** — принято: одиночная точка — следствие Р25 = 1
  (отрезок из одной точки линией не виден), кружок на последнем — план (чек-лист (в)); радиусы — внутреннее.
- **smells 5 → 5** (замер оркестратора: ушёл `server.py:make_server`, пришёл `static/pult.js`, total 50, +3 строки) — принято
  без резки: число не выросло, порог превышен на HEAD (BACKLOG 58, «Партии»: «smells — красный и до шага»); резка `pult.js`
  — рефакторинг вне задачи, место ему — BACKLOG 58.
- **pyright — 2 ошибки `web/pantry.py:25`, `:63`** (партия 4, в коммите 010ae0c) — регресс в области шага, `make check`
  (`types`) красный → в эту партию (правило 9), не BACKLOG. `:25` — `rows: list[dict[str, Any]] = []` (тип у списка);
  `:63` — `unit` в `PantryEntry` строкой: `unit if isinstance(unit, str) else ""` — `record` отвечает тем же `ValueError`
  «Единица должна быть из …» → 400 (проверено разбором партии 4, `:821`), поведение не меняется. Проверка —
  `uv run pyright` 0 ошибок, `tests/test_web_pantry*` зелёные.

Партия 5, ревью мамы и аудит свекрови (круг 1):

- **Справка `pult.md`, «Шкала и правка плана»: «черновик, потом `coach event write`»** (свекровь, «решить») — решил папа:
  правка справки под Р4 = 2 (`web/plan.py:70-76` пишет сразу в календарь), не вопрос Владу. Новая формулировка: пункт
  сразу пишется в календарь; при недоступном календаре остаётся черновиком «записан черновиком: …», записать —
  `coach event write`.
- **Справка `pult.md`, «Состояние»: нет `get_who5` в источниках сигналов** (мама) — кабан добавляет.
- **Счёт тестов доебы** (мама) — пересчёт доебы по дереву: +66 (итог доебы «82» — ошибка сложения, поправила мама) — `test_web_state.py` 29, `state.test.mjs` 28,
  `test_web_server.py` +3, `test_skills_help.py` +6 и 2 переименования; `pult.test.mjs` — 0 новых (импорт `chartPoints`).

## Открыто: стенд / аналитик

- Прототип (артефакт claude.ai) папе недоступен — развилки Р1, Р2, Р5–Р7, Р11 составлены без него; Влад сверяет с
  прототипом в окнах.
- EventKit из потока сервера (перенос записанного события, синк) — руками на живом Календаре в партиях 1 и 3. Коммит
  партии 1 не блокирует (прецедент — Н23, docs/plan-n23.md:251, та же строка в «Открыто»); закрытие шага — блокирует.
  Проверяет Влад (его Календарь, возможный запрос macOS — «Вне ai-coach»). Рецепт партии 1: `uv run coach web --no-open`;
  `uv run coach event list` → id записанного события; `curl -X POST -H 'Origin: http://127.0.0.1:8765'
  -H 'Content-Type: application/json' -d '{"action":"move","id":N,"start_at":"YYYY-MM-DDTHH:MM"}'
  http://127.0.0.1:8765/api/event` → событие в приложении Календарь на новом месте, `coach event list` — новое время.
  Красное → партия 1б: подпроцесс `coach event move` в `default_writer`/`_move` (~20 строк, «Риски»), контракт POST для
  партии 2 не меняется. Срок прогона (Влад, окно 2026-11-09): до старта партии 2. Партия 1: рецепт прогнан Владом до старта партии 2 — работает
(слова Влада), партия 1б не нужна; синк из потока сервера — партия 3.
- Перетаскивание на телефоне (Safari iOS) и в Chrome device mode — руками в партии 2; DOM тестами не покрыт.
- Партия 2, браузером не проверено; `scale-pane.js` — только руками. Коммит партии — после чек-листа Влада (окно
  2026-11-10), Mac, затем Chrome device mode или телефон:
  (а) окна пункта, отметки, варианты еды, вкладка «Тренировки» открываются как раньше (общий `el`);
  (б) блок тянется с подсказкой над полосой, край меняет длительность, у края суток блок останавливается;
  (в) клик в пустоту → форма, кнопки вида, ряд категорий только у «задачи»; «Создать» → пункт на шкале, в
  `coach event list` и в Календаре (Р4 = 2); «Отмена» без следа;
  (г) ошибка текстом под шкалой: клик в пустоту, в форме конец раньше начала (10:00 и 09:30), «Создать» → «Начало
  события должно быть раньше конца.», ничего не создано (рецепт папы 2026-11-10; жестом диапазон дней не нарушить);
  (д) перенос записанного события из шкалы виден в приложении Календарь;
  (е) касание не прокручивает страницу и не выделяет текст.
- Партия 3, `header-pane.js` — только руками; чек-лист (аудит свекрови 2026-11-10) пройден Владом 2026-11-10 14:03 —
  «всё работает чётко», коммит не блокирует; правило коммита для партий 4–5 — Р17:
  (а) шапка: строки показателей, веса и синка; при пустых данных — «показателей нет», «веса нет», «синка не было»;
  (б) запись веса из шапки → «Записано», вес в строке, `coach` видит запись;
  (в) «Синк» из пульта → «синк идёт…», затем время; данные Garmin и Календаря (EventKit из потока сервера) обновились;
  (г) без токенов Garmin — «синк HH:MM ошибка» и текст ошибки под шапкой, кнопка снова активна;
  (д) открытое поле веса не останавливает обновление дня; на телефоне шапка не ломает вёрстку.
- Партия 4, `pantry-pane.js` — только руками; коммит не блокирует (Р17 = 2), красное — партия 4б; Р22 — тем же окном:
  (а) вкладка «Еда»: таблица, «Дома ничего нет.» на пустой кладовой, просроченная строка красная с «просрочен», ≤ 2 дней —
  жёлтая с «скоро», `coach pantry list` совпадает;
  (б) «−»/«+» по шагу единицы (g 50, ml 100, pcs 1) → «Записано»; списание больше остатка → предупреждение под таблицей,
  «Записано» не всплывает;
  (в) поле «+200» / «-50» / «120» + Enter → add / use / set; «abc» → «Нужно число: +200, -50 или 120.»;
  (г) «Списать просроченное» у просроченной строки → строка исчезает; «+ продукт» → форма, `g · ml · pcs`, дата, «Добавить»;
  (д) блок КБЖУ: строка остатка как в окне еды, записи дня «время · текст · ккал», «Записей еды за день нет.»;
  (е) ввод в поле не сбивается таймером; телефон — кнопки 44 px, таблица не ломает вёрстку.
- Партия 5, `state-pane.js` и `lineChart` — только руками; коммит не блокирует (Р17 = 2), красное — партия 5б; Влад
  добавляет строку allow `pult.md` до коммита:
  (а) вкладка «Состояние»: сигналы дня словами Р10 = 1 в форме Р23; день без сигналов — «сигналов нет»;
  (б) база без свежего пульса покоя (или день до первого синка) — «нет данных: …» под сигналами, сигналы сна видны;
  (в) пять графиков с подписями «сон, ч» … «вес, кг», шкала по Р24, пропуски по Р25, кружок на последнем значении;
  (г) листание дней стрелками обновляет сигналы и графики; таймер не трогает вкладку, пока она скрыта;
  (д) обе темы (светлая/тёмная) — линии, оси и подписи читаются; телефон — графики не вылезают за карточку;
  (е) вкладка «Тренировки»: график CTL · ATL как до партии (`chartAxes` через `box`), окна и отметки — как раньше;
  (ж) справка: `cat .claude/agents/coach-help/pult.md` из тренера проходит (allow), `day-plan.md` ссылается на `pult.md`.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план П4 («Суть», «Файлы», «Партии», «Справка», «Тесты»); «Развилки» не читал — их влияние заложено только
в ширину диапазона. База — факт П3 (`docs/plan-p3.md`, «Итог»: 85,27 $, 153,05M, net 1349 строк кода, та же серия и стек).
Цены — pricing от 2026-11-09 (https://platform.claude.com/docs/en/about-claude/pricing): Opus 5.5 — 4 / 5 / 0,20 / 20,
Sonnet 5.5 — 2 / 2,50 / 0,10 / 10 $ за 1M (вход / запись кэша / чтение кэша / выход), совпадает с тарифом metrics.py от
2026-10-25; fable — цена Opus (правило сметы).

Масштаб — строки кода из «Файлов» против факта П3: номинал по таблице файлов 1166 строк (Python 354, JS/CSS/HTML 782, Справка
30), рост × 1,2–1,8 (П3 по шагу × 1,4 к номиналу 963) → **1400–2100 строк** против 1349, то есть × 1,04–1,56. Партий 5 против 6.

Платного вне LLM нет: хостинга, внешних API и новых подписок план не вводит; БД — локальный SQLite, пульт — локальный
`coach web`, Календарь — EventKit, синк Garmin — тот же `coach sync` без LLM, графики — SVG без библиотек. Новых зависимостей нет
(`jsdom`/Playwright план не предлагает). Расход в эксплуатации — 0 $/мес; всё ниже — разовая стоимость шага.

| Статья | Сейчас ($/шаг; в эксплуатации 0 $/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Декарт (fable) | 13,1 | партий + 1 сводный = 6 вызовов × 2,19 $ (последний факт, Ш28: 10,95 $ за 5, `plan-sh28.md:303`) | только сводный вызов; или не звать, как в П2, П2в, П3 | 10,9 $ (сводный); 13,1 $ (без него) | разбор по партиям, огрехи ранних всплывут в конце; без вызова — разбора нет |
| Оркестратор (opus) | 14,4–22,6 | 35–55M × 0,41 $/M (факт П3: 57,03M за 6 партий, 9,5M на партию, 347 вызовов) | `/compact` сразу после коммита партии; отчёты субагентов — файлами, в сессию только хэнд-бэк | 2–4 $, допущение | ничего при ведении `agents.md` |
| Папа (fable) | 10,6–18,6, в т. ч. 3,62 уже прошло | остаток 7–15 $ при факте П3 16,92 $ за 6 партий (2,82 на партию, 19 запусков, 27 развилок после старта); низ — вдвое меньше развилок | развилки закрыть одним раундом окон до старта; отступления партии — одним вызовом на партию | 3–6 $, допущение | ничего; часть мелких отступлений решит оркестратор без папы |
| Кабан и доеба (sonnet) | 13,9–26,2 | кабан 20–27k токенов на строку (П3 27k, низ — при меньшем числе развилок) × 0,29 $/M; доеба 18–30M × 0,324 $/M (П3 23,22M; пять новых модулей под мутанты) | модель не менять: haiku на коде и тестах — риск новых кругов; чек-лист «Тесты» отдать кабану одним списком до правок вида (П3: 69,3 % затрат субагентов — после первого ревью) | 3–6 $, допущение | ничего |
| Прогоны mutmut (фон, доеба) | внутри строки доебы | план 1,5–3 ч (не проверено), П3 122 мин; прогоны #3 и #4 в П3 — из-за таймаутов при load 270–570 | запускать по модулю, при низкой нагрузке, без параллельных прогонов кабана | 1–2 $, допущение | время: фоновые окна длиннее |
| Ревью и аудит (opus) | 16,4–26,9 | мама 5,5–9,0M × 1,634 $/M, свекровь 5,5–9,0M × 1,353 $/M; факт П3 — 7,68M и 7,82M на 6 партий | не трогаем | — | — |

| Партия | Время |
|---|---|
| 0. План папы + окна | папа — факт, 13,8 мин; окна — ожидание Влада, вне сметы |
| 1. Правка плана, сервер (~170 + тесты) | 41–61 мин |
| 2. Шкала дня (~275 по «Файлам») | 66–99 мин |
| 3. Шапка: вес, синк, показатели (~220) | 53–79 мин |
| 4. Вкладка «Еда» (~268) | 64–96 мин |
| 5. Вкладка «Состояние» и Справка (~310) | 74–112 мин |
| Ручная проверка Влада (Календарь, телефон, две темы) | вне сметы, ожидание Влада |
| cov + mutmut | 95–190 мин фоновых: cov 5–10, mutmut 90–180 (оценка плана, не проверено) |
| Декарт, тесть р.3, закрытие | 45–65 мин |
| **Цепочка** | **357–526 мин работы** + 95–190 фоновых = **452–716**, без ожидания Влада; сопоставимо с П3 435 мин (313 сегментов + 122 фоновых) |

Время партии: строки партии × 1,2–1,8 × 0,20 мин на строку (П3: 271 мин на net 1349; кабан, доеба, ревью и папа, сумма
сегментов). Партия 1 — по строке плана ~170: в «Файлах» её ~96, но серверные партии П3 с тестами шли 41–43 мин.

| Роль | Модель | Токены | $ (pricing 2026-11-09) |
|---|---|---|---|
| orchestrator | opus | 35–55M | 14,4–22,6 |
| papa-kaban | fable | 9,3–17,5M | 10,6–18,6 |
| kaban | sonnet | 28–57M | 8,1–16,5 |
| kaban-doeba | sonnet | 18–30M | 5,8–9,7 |
| mama-kaban | opus | 5,5–9,0M | 9,0–14,7 |
| kaban-svekrov | opus | 5,5–9,0M | 7,4–12,2 |
| kaban-test | opus | 0,3–0,5M | 0,7–1,1 |
| kaban-dekart (6 вызовов) | fable | ≈ 12,4M | 13,1 |
| **итого** | | **114–190M** | **69,1–108,5** |

Без Декарта (в П2, П2в и П3 его не звали): **56,0–95,4 $**, 102–178M.

Как считал: $/M — средняя цена роли по факту П3 ($ / токены): оркестратор 0,41, папа 0,97, кабан 0,29, доеба 0,324, мама 1,634,
свекровь 1,353, тесть 2,19 (только р.3 и редакция сметы, свой запуск не включён). Токены Декарта — оценка по 1,06 $/M. База
Декарта: 2,19 $/вызов (факт Ш28) — без смены; в шагах семьи после Ш28 фактов Декарта нет.

Уже прошло: 3,62 $ (papa-kaban a5ed1c476c5a6ab71, 2,06M, `metrics.py` сессии 4acf1d23); нижняя граница 69,1 $ ≥ 3,62 $, папа в
таблице включает эту сумму. Свинопаса и шурина в `agents.md` нет.

Оговорки:
- Партий с объёмом > 400 строк кода в плане нет (номинал 165–230). По «Файлам» партии 2–5 выходят 220–310: у партии 5 при
  росте × 2,4 из плана — ~740, у партии 2 — ~660; порог будет пройден по факту. План уже называет края у партий 4 и 5.
- Итог плана «~1000 кода» не включает HTML/CSS (~165): по таблице файлов — ~1166. Смета считает 1166.
- Сумма партий по «Партиям» 975 расходится с «Файлами» (1169), в основном по CSS, разложенному на партии 2–5.
- Вынос `el` и `chart.js` трогает готовые окна П2–П3: возможны круги правок сверх номинала, в верх диапазона заложено.
- mutmut 1,5–3 ч — оценка плана по пяти новым модулям; при таймаутах как в П3 (load 270–570) фон вырастет.
- Fable считается по Opus по правилу. По pricing Fable 5.1 стоит 10 / 12,50 / 0,25 / 50 $: при оплате по прейскуранту папа и
  Декарт вырастут примерно × 2,3 (как папа в П3, 19,19 → 43,6 $): итог ~+30–40 $ с Декартом.
- Смета выше факта П3 при меньшем числе партий: П4 шире по коду (JS и CSS вида) и включает Декарта (13,1 $), которого в П3 не было.

Цитата `grep -H '^model:'`:

```
~/.claude/agents/kaban.md:model: sonnet
~/.claude/agents/kaban-test.md:model: opus
~/.claude/agents/kaban-dekart.md:model: fable
~/.claude/agents/papa-kaban.md:model: fable
~/.claude/agents/kaban-doeba.md:model: sonnet
~/.claude/agents/mama-kaban.md:model: opus
~/.claude/agents/kaban-svekrov.md:model: opus
```

Вердикт: ок по бабкам, партий > 400 строк кода в плане нет. Главные развилки цены — Декарт (13,1 $) и круги правок после
ревью (в П3 — 69,3 % затрат субагентов); выбор за Владом.
