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

Уточнения по партии 1 («API и модель»: `resize` без `end_at` → 400, тип `id` включая bool, `date` при move/resize не
читается, `CREATE_FIELDS` без повтора и связей, `mark_reply` → `post_reply`, `test_cli_agenda.py` без правок) — защита
ввода и внутреннее, решил папа 2026-11-09 по ревью и аудиту партии 1; виды `PULT_KINDS` — не решение папы, а исполнение
Р5 = 1 Влада на сервере.

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
| `src/ai_coach/web/pantry.py` | новый: `pantry_view(conn, day)` — `stock` + флаги `expired/expiring` из `expiring`, при Р7 = 1 `remaining` и `food` дня (как `meal_view`); `save_pantry(conn, payload, now, today)` — `op: add \| use \| set \| spoil`, `record`/`spoil`, `ValueError` → `MarkError`, предупреждение в ответ | ~60 |
| `src/ai_coach/web/state.py` | новый: `state_view(conn, day, now)` — `signals` (пять отчётов, `kind/value/limit` + источник), `trends` (14 дней: `sleep_h`, `hrv`, `rhr`, `readiness`; вес 30 дней), `load_error` при `ToolError` (overload без `tss`) | ~70 |
| `src/ai_coach/web/day.py` | `day_view` += `"header": header_view(...)` | ~3 |
| `src/ai_coach/web/server.py` | `POST_ROUTES = {"/api/mark": save_mark-путь, "/api/event": apply_event, "/api/weight": save_weight, "/api/pantry": save_pantry, "/api/sync": syncer.start}`; `_refusal(path, headers)` — путь из таблицы; `post_reply(db, path, headers, rfile)` — общий разбор JSON и ошибок, `mark_reply` переименована в него (обёртки нет); GET `/api/pantry`, `/api/state`, `/api/sync` через `api(query, build)`; `do_POST` → `post_reply` | ~45 |
| `src/ai_coach/web/static/dom.js` | новый: `el`, `svgNode` — одна копия; шесть старых копий `el` удаляются (BACKLOG 66) | ~12, −30 |
| `src/ai_coach/web/static/chart.js` | новый: `chartPoints` (из `week-model.js`), `chartAxes`, `lineChart(svg, rows, keys)` из `week-pane.js:38-80`; `week-pane.js` импортирует | ~50, −35 |
| `src/ai_coach/web/static/scale-model.js` | новый (чистые, тесты `node --test`): `frameOf(view)` (Р1), `minuteAt(x, width, frame)`, `snap(min, 5)`, `blockBox(row, frame)` (left/width в %), `dragOutcome(mode, row, deltaMin)` → `{start_at, end_at}` с границами (конец > начала, ≥ 5 мин), `newSpan(min, frame)` (30 мин), `locked(row)` (повтор, встреча) | ~70 |
| `src/ai_coach/web/static/scale-pane.js` | новый (DOM): `renderScale(view)` под `#bar-label`; Pointer Events (`pointerdown` → `setPointerCapture`, порог 4 px, `pointermove` → подсказка времени, `pointerup` → `POST /api/event`); правый край 12 px — `resize`; клик в пустоту — форма нового пункта (Р5); при ошибке — текст под шкалой (П2 Р11), блок на место; `dragging` — таймер `pult.js` не перерисовывает | ~130 |
| `src/ai_coach/web/static/header-pane.js` | новый: показатели, вес («записать» → поле + «OK»), «Обновить» → `POST /api/sync`, опрос `/api/sync` раз в 5 с пока `running`, затем `load()` | ~70 |
| `src/ai_coach/web/static/pantry-model.js`, `pantry-pane.js` | новые: `stepFor(unit)` (Р6), `parseDelta("+200" \| "-50" \| "120")` → `{op, qty}`, `pantryRows(view, today)`; DOM — таблица «Продукт · Остаток · Годен до», кнопки «−»/«+», поле, «Списать просроченное», форма добавления, блок КБЖУ (Р7) | ~40 + ~110 |
| `src/ai_coach/web/static/state-model.js`, `state-pane.js` | новые: `SIGNAL_WORDS` (слова из справки — Р10), `signalRows(state)`, `trendSeries(state)`; DOM — список сигналов («сигналов нет»), пять графиков через `chart.js` | ~40 + ~70 |
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
- `GET /api/day` += `header: {weight: {kg, measured_at} | null, sync: {finished_at, status, running}, metrics: {readiness,
  sleep_h, hrv, rhr} | null}`; `GET /api/pantry?date=` → `{rows: [{item, qty, unit, expires_on, opened, expired, soon}],
  remaining, food}` (Р7); `GET /api/state?date=` → `{signals: [{source, kind, value, limit}], trends: {dates, sleep_h, hrv,
  rhr, readiness, weight: [{date, kg}]}, load_error}`.
- Шкала: рамка — Р1; блоки `items` (повтор — замок, встречи — серые, без захвата); px ↔ минуты по ширине `#scale`;
  снап 5 мин; порог начала перетаскивания 4 px (иначе клик). Правый край 12 px — `resize`. Клик в пустоту — `newSpan`
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
- JS (`node --test tests/web/`): `frameOf`, `minuteAt`, `snap`, `blockBox`, `dragOutcome` (сдвиг, резайз ≥ 5 мин, конец >
  начала), `newSpan`, `locked`; `stepFor`, `parseDelta` («+200», «-50», «120», «abc» → null); `signalRows` (слова по
  `SIGNAL_WORDS`), `trendSeries`; `chartPoints` из `chart.js`.
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

Риски:
- EventKit из потока HTTP-обработчика (`CalendarWriter._open` → `_request_access`, `calendar_eventkit.py:48`,
  `threading.Event`) и из потока синка — на живом Календаре не проверено; partия 1 и 3 проверяют руками первыми; запас —
  подпроцесс `coach event move` / `coach sync` (ожидание ~20 строк замены в `plan.py`/`syncer.py`).
- `rebuild_plan_actual` при синке днём пишет `skipped` сегодняшней тренировке (BACKLOG 65) — кнопка «обновить» сделает
  это заметнее; правка в `load/*` не здесь.
- Перетаскивание на телефоне: точность 0,46 px/мин (Р1 = 1), конфликт с прокруткой; смягчение — `touch-action: none`
  только у шкалы, порог 4 px, снап.
- Ctrl-C серверу во время синка — поток гибнет, строки «ok» в `sync_log` нет; следующий `coach sync` всё перепишет.
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
- Виды нового пункта (Р5 = 1): форма партии 2 показывает `task · focus · rest · meal`; сервер в партии 1 принимает те же
  четыре (`PULT_KINDS`, «API и модель») — форма и сервер сходятся; тренировки, практики, чек-ины — не из пульта ни с какой
  стороны. Текст 400 виден только не-форме (форма чужой `kind` не шлёт) — умолчание.
- Тесты партии 1 к ветвям выше (под mutmut `ai_coach.web.plan:*`): `resize` без `end_at` → `MarkError`, ничего не сдвинуто;
  `id: "7"` и `id: true` → `MarkError` (не `NoEvent`), событие 1 на месте; `kind: "training"`, `"checkin"` → `MarkError`,
  в `coach_events` ничего.
- Ошибки — два слоя по П2 Р10 = 2: тексты сервера под шкалой/в блоке, протокольные — «Не сохранилось, ошибка пульта (код N)».
- `pantry_view.rows` — порядок `stock()` (по алфавиту), `expired` и `soon` (≤ 2 дней, `expiring(days=2)`) — флаги строк; при
  Р7 = 1 `remaining`/`food` — `meal_view` + `list_food` дня.
- `state_view.signals` — пять источников по дню просмотра: `sleep_report(day, now)`, `illness_report(day, tss, sleep)`,
  `overload_report(day, tss)` (`tss` из `tools.load(day-13, day)`, `ToolError` → `{}` и `load_error`), `who5_report`,
  `find_deviations`; `trends` — `list_daily_metrics`/`list_recovery_days` за 14 дней, `list_weights` за 30.
- `dom.js` снимает шесть копий `el` (BACKLOG 66 закрывается партией 2); `chart.js` — вынос из `week-*` без смены поведения
  (тест `chartPoints` меняет импорт).
- Таймер `pult.js` при `dragging` и при открытом поле веса (`typing()` уже ловит `INPUT`) не перерисовывает.
- Тесты JS — чистые функции в `*-model.js`, DOM — руками (правило П2в).

## Открытые вопросы

Р1–Р12 — «Развилки». Первые блокируют партии: 1 — Р4, Р5 (сервер `create`); 2 — Р1; 3 — Р2, Р3; 4 — Р6, Р7, Р8; 5 — Р9,
Р10, Р11; порядок — Р12.

1. Р4 — новый пункт черновиком или сразу в календарь (`agenda/service.py:153 create_draft`, `:178 write_event`); рекомендую 2;
   разблокирует партию 1; решает Влад.
2. Р1 — вид шкалы (`scale-model.js` новая); рекомендую 1; разблокирует партию 2; решает Влад.
3. Р9 — куда справку (`coach-help/day-plan.md:14-22`); рекомендую 1 (+ строка allow Влада); разблокирует партию 5 и
   «Вне репо»; решает Влад.
4. Р2, Р3, Р5–Р8, Р10–Р12 — рекомендую 1 во всех, кроме Р4 = 2; решает Влад окнами по одному (okna.md).

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
  партии 2 не меняется. Срок прогона (Влад, окно 2026-11-09): до старта партии 2.
- Перетаскивание на телефоне (Safari iOS) и в Chrome device mode — руками в партии 2; DOM тестами не покрыт.

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
