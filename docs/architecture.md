# Архитектура MVP (кабан-архитектор, 2026-10-06) — утверждена пользователем 2026-10-06

Версии на PyPI 2026-10-06: garminconnect 0.3.17, mcp 2.3.0, typer 0.27.2.

## Стек
Python 3.12+, uv; python-garminconnect ≥0.3; SQLite (stdlib sqlite3 + SQL-миграции, без ORM); typer (CLI); mcp SDK / FastMCP (сервер для тренера); pydantic; pytest.
Не берём garmin_mcp / garmin-givemydata (лишняя авторизация); читаем их и athlete-management-system как образцы workout JSON. GarminDB — запасной вариант импорта.

## Разделение
- CLI `coach`: sync, import <fit/zip>, weight, food, push <id> (подтверждение y/N), status. Всё, что пишет в Garmin.
- MCP-сервер (stdio): чтение метрик/истории/целей/плана/нагрузки; запись только черновиков (план, предложение фазы) и КБЖУ еды без КБЖУ — сразу окончательно (решение по шагу 8). Отправки на часы в MCP нет.
- Скиллы Claude Code: /coach-morning, /coach-plan, /coach-food. Логика тренера — в промптах, цифры (CTL/ATL, прогрессия) — в Python.

## Модули
garmin/ · store/ · sync/ · goals/ · plan/ · load/ · workouts/ · cli/ · mcp_server/ (последние два — тонкие обёртки).

## Схема
daily_metrics, activities, strength_sets, weight_log, goals, phases (proposed/accepted), goal_events, planned_workouts (draft/approved/pushed), plan_actual, food_log, wellbeing_log, profile_log, sync_log. raw_json хранится всегда.

## Шаги MVP
0. Кабан-кволити: линтеры, пороги, мутации.
1. Спайк: логин (MFA, токены), чтение сна/HRV/BB/стресса/readiness с FR970 за 30 дней, загрузка силовой с весами и планирование на дату, экспорт FIT/zip. Если силовая не грузится — стоп и развилка 5.
2. store + миграции. 3. sync/import (идемпотентно, offline import). 4. goals/фазы. 5. workouts/plan + push. 6. план/факт + CTL/ATL. 7. MCP + /coach-morning, /coach-plan. 8. вес и питание (?).

## Тестовые сценарии
Идемпотентный sync; поломка авторизации → понятная ошибка, кэш цел; пропуски метрик; через MCP нельзя отправить на часы; push без «y» ничего не шлёт; план/факт при пропуске/лишней/другой тренировке; история целей на любую дату; сериализация силовой = эталон из спайка; CTL/ATL = ручной расчёт.

## Развилки (рекомендация — A)
1. Данные для тренера: A свой MCP / B CLI с JSON через Bash.
2. Подтверждение отправки: A только `coach push` / B MCP + подтверждение в чате.
3. Нагрузка: A свой TSS/CTL/ATL / B Garmin Training Load.
4. Ручной импорт: A полный экспорт Garmin (zip/FIT) / B только FIT активностей.
5. Если силовая не грузится: FIT по USB / текстом / убрать из MVP.

## Риски
Garmin ломает доступ (кэш, import, raw_json); недокументированный формат силовых; лимиты подписки (MCP отдаёт агрегаты); токены на диске (600, вне репо); блокировка за частые логины.

## Открытые вопросы
1. Вес и питание в MVP (шаг 8)? 2. Какие виды спорта на часах кроме силовой? 3. План недели: тренер с нуля или пользователь задаёт каркас? 4. MFA на аккаунте Garmin? 5. Развилки 1–5.

## Ответы пользователя (2026-10-06)
- Развилки: 1A (свой MCP), 2A (только `coach push`), 3A (свой TSS/CTL/ATL), 4A (полный экспорт Garmin), 5 — если силовая не грузится, отправлять текстом.
- Вес и питание входят в MVP (шаг 8 — в MVP).
- На часах: силовая, бег, вело, плавание + утренняя растяжка. Плюс текстовые рекомендации по восстановлению (массаж, баня).
- План недели: тренер выдаёт рекомендации, пользователь правит.
- MFA на Garmin: пользователь не знает — выяснить на спайке (или Garmin Connect → Настройки → Безопасность).

## Уточнения после проверки по деньгам (приняты пользователем 2026-10-06)
- LLM/API из Python-кода запрещены. `coach food` только сохраняет сырой текст; КБЖУ считает скилл /coach-food.
- MCP отдаёт только агрегаты (без raw_json), с жёстким лимитом строк/размера ответа; утренний разбор — одним `get_morning_snapshot`.
- Модель на скилл: /coach-morning и /coach-food — Sonnet/Haiku, /coach-plan — Sonnet, Opus только по запросу.
- Еда: копится текстом через CLI, /coach-food раз в день пачкой.

## Итоги спайка Garmin (2026-10-06)
Отчёт: [research-garmin.md](research-garmin.md). Развилка 5 не нужна — силовая грузится на FR970.
- Силовая: сериализация = `spikes/garmin/reference/strength.json`. `weightValue` — в кг; `create_strength_set` из garminconnect 0.3.17 пишет граммы (баг) — не использовать как есть.
- Растяжка: `sportType` = `mobility` (id 11), шаги с упражнениями каталога `WARM_UP/STRETCH_*` (`garminconnect/exercises.py`), эталон `reference/stretch_mobility_named.json`. Анимаций упражнений на часах нет — краткая техника по-русски пишется в `description` шага (на часах — заметка).
- Бег/вело/плавание: эталоны `reference/run.json`, `bike.json`, `swim.json`; цели по темпу и шаги по дистанции работают.
- `coach push` может заменять план: снятие из календаря (`unschedule_workout`) и удаление (`delete_workout`) работают. Заменяются только свои тренировки и только после отдельного y/N с показом, что удаляется.
- План/факт: подходы силовой несут `wktStepIndex` — номер шага плана. Повторы/вес в факте есть, только если их ввели на часах.
- Метрики (сон, HRV, BB, стресс, readiness) — без пейволла Connect+.
- Логин: MFA выключена; Garmin отвечает 429 на частые полные логины. Полный логин — только явной командой (`coach login`), остальное по токенам; 429 и протухшие токены → понятная ошибка, кэш цел.
- Команды с вводом пароля или y/N запускаются в обычном терминале (в `!` Claude Code нет TTY).
- Раскладка полного экспорта (развилка 4A) — после п.8 спайка.

## Решения пользователя после аудита шага 1 (2026-10-06, «по рекомендациям»)
- `coach login` — отдельная команда CLI, единственное место полного логина.
- Повторный `coach push` заменяет только свои тренировки, после отдельного y/N с показом удаляемого.
- БД по умолчанию: `~/.local/share/ai-coach/coach.db`.
- Техника упражнений по-русски — в `description` шага.
- Рекомендации по восстановлению (массаж, баня) — текстом в /coach-morning (шаг 7).
- Шаг 3 закрывается без разбора полного экспорта; разбор — отдельно после п.8 спайка.
- `spikes/**` исключён из qlty (одноразовый код).

## Решения пользователя по шагу 2 (2026-10-06)

Пункты кабана (8 неясностей с рекомендациями оркестратора, сообщение после отчётов кабана и доебы) приняты пользователем («согласен»); FK plan_actual — «сначала должен измениться план, а потом удаляются или изменяются тренировки»; после аудита — ответы ниже («норм», «согласен», «подтверждаю»). Схему пользователь сам не смотрит — поручено папе-кабану.

- Колонки таблиц — как в `src/ai_coach/store/migrations/0001_init.sql`; в `daily_metrics` выжимка + один `raw_json` на день.
- Путь к БД: аргумент `path` → `$AI_COACH_DB` → `~/.local/share/ai-coach/coach.db`.
- `plan_actual.kind`: `done / skipped / extra / different`; пересчёт за период — удалить и добавить заново; естественного ключа у planned_workouts/plan_actual нет.
- Commit делает вызывающий код (sync — одной транзакцией).
- Upsert только по ключевым колонкам → `ON CONFLICT DO NOTHING`.
- `weight_log`, `food_log` без `raw_json` (ручной ввод).
- Отложено: статусы `goals` и `sync_log` — шаг 4; единица веса в `strength_sets` — шаг 3/6.
- FK `plan_actual.planned_id` без `ON DELETE` (запрет): сначала меняется план (и plan_actual), потом удаляются/меняются тренировки.
- После ревью: `None` в `*_json` → SQL NULL; миграции — только `*.sql`, при ошибке rollback.
- После аудита: `goals.status DEFAULT 'active'` — временно до шага 4 («норм»); `strength_sets` удаляются каскадом с активностью («согласен»); цель с событиями удалить нельзя («подтверждаю»).
- После ревью схемы папой-кабаном («да, принимаем 1–4»): статус `cancelled` у planned_workouts; CHECK связки `plan_actual.kind` ↔ ссылки (done/different — обе, skipped — только план, extra — только активность); время по умолчанию — местное; `planned_workouts.sport` ∈ strength/mobility/run/bike/swim (соответствие типам Garmin — в коде, шаг 6).
- Отложено папой-кабаном: история фаз и связь с целями — шаг 4; пульс покоя, индекс для план/факт, признак «КБЖУ посчитано» — по ходу шагов 3–8; CHECK статусов goals/sync_log — шаг 4; активность с plan_actual удалить нельзя — переимпорт (шаг 3) обновляет активность upsert-ом, не удаляет. Список отложенного и запрет приняты пользователем после второго аудита («согласен на всё»).

## Решения пользователя по шагу 3 (2026-10-06, «по рекомендациям»)

- Зависимость `fitdecode` для чтения FIT (в garminconnect только энкодер).
- Ошибка sync пишет строку `status=error` в `sync_log` (отдельной транзакцией); остальные таблицы не меняются.
- `coach import <fit> [--id N]`: id активности из имени `<id>_ACTIVITY.fit`, иначе `--id`.
- Вес в `strength_sets` — кг (API отдаёт граммы, переводится при sync).
- Несколько записей readiness / Body Battery за день — берётся последняя.
- `coach login` при протухших токенах сразу переходит к полному логину.

После аудита свекрови («1. оставляем 2. принимаю 3. рекомендация»):
- Каталог токенов: `$AI_COACH_GARMIN_DIR` → `~/.config/ai-coach/garmin` (предложение мамы-кабана, в коде до согласия — ошибка оркестратора).
- `coach sync` по умолчанию 7 дней, пауза 0.5 с между запросами.
- Подсказка при протухших токенах — просто «выполни coach login» (файл удалять не нужно).

Факты (не решения) об импорте FIT: упражнения — числовые коды (названия пустые, коды в `raw_json`); `type_key` из `sport/sub_sport`; без локального времени — время старта.

## Решения пользователя по шагу 4 (2026-10-06)

- Статусы `goals`: `active / done / cancelled` (CHECK, миграция 0002); `sync_log.status`: `ok / error`.
- Фазы: связь с целями (`phase_goals`) и события `proposed/accepted` (`phase_events`); `phases_on(день)`.
- После аудита свекрови (ответы пользователя): цели не удаляются, закрытие — статусом; изменения раньше последнего события запрещены; «на дату» — конец локального дня, без часовых поясов; у фаз есть отклонение (`rejected`) и правка черновика (`proposed`), включая набор целей; `list_phase_goal_ids` и выборка событий всех фаз остаются под шаг 7.
- Решение кабана (мелочь): событие `updated` хранит только изменённые поля, без изменений события нет.

## Решения пользователя по шагу 5 (2026-10-06)

- Повторный push: сначала загрузка и план новой, потом unschedule + delete старой (при сбое — дубль, а не пустой день).
- Темп бега перед отправкой показывается в мин/км; JSON Garmin — м/с по эталону.
- Приняты решения кабана: команда `coach approve` (draft→approved); `coach status` без фильтра по дате (фильтр — бэклог); длительность по умолчанию 0; ошибка Garmin → код 1 без отката статусов.
- Решения кабана (мелочи, утверждены пользователем 2026-10-07): в `workout_json` хранится spec, JSON Garmin собирается при отправке; база обновляется только после успешного schedule, id осиротевших копий — только в сообщении об ошибке; `push_workout_to_device` не используется (календарь + синхронизация часов).

## Решения пользователя по шагу 6 (2026-10-07, «пока по рекомендациям»)

- TSS — hrTSS по резерву ЧСС: `IF = (avg_hr − rest_hr)/(lthr − rest_hr)`, `TSS = часы × IF² × 100`; `rest_hr`/`lthr` — параметры функций, источник (конфиг / Garmin) решается на шаге 7. Нет пульса или длительности → TSS 0, без фолбэка на training_load Garmin.
- CTL τ=42, ATL τ=7, старт с 0; сглаживание `x + (tss − x)/τ`.
- Силовая: упражнение i ↔ ACTIVE-подход с `wktStepIndex = 3i+1` — допущение, проверить на часах на шаге 7 (фикстура спайка его не подтверждает).
- План/факт: в сопоставление идут только `pushed`; частичная силовая → `different` с `missing_exercises`, без порога; при двух одинаковых тренировках в день — план с меньшим id берёт более раннюю активность.
- Растяжка (mobility) в сопоставлении — после выяснения typeKey на шаге 7.
- После ревью мамы-кабана (ответы пользователя: «давай добавим, давай уберем, согласен с мамой»): планы с видом спорта без маппинга (mobility) пропускаются в сопоставлении до шага 7; добавлены частые typeKey Garmin (trail/track/virtual run, road/mountain/gravel biking, virtual ride); `lthr <= rest_hr` → ValueError; `ctl0`/`atl0` убраны из `load_series`.
- Решения кабана (утверждены пользователем: «согласен с мамой»): активность чужого типа достаётся плану без пары с меньшим id, из нескольких — самая ранняя; у `different` по типу `details_json` пустой; нулевая длительность → TSS 0.
- После аудита свекрови (пользователь: «утверждаю»): средний пульс ≤ `rest_hr` → TSS 0.

## Решения пользователя по шагу 7 (2026-10-07)

- Списочные инструменты MCP отдают `{"rows": [...], "truncated": bool}`; у рядов по датам при обрезке остаются самые новые строки.
- Лимиты: 60 строк, 20 000 символов, период ≤ 92 дней; в снапшоте каждый список ≤ 20 строк / 4000 символов; снапшот — 7 дней назад, план на 7 дней вперёд, вес за 14 дней, прогрев CTL/ATL 120 дней («всё так», «всё оставить»).
- Запись через MCP: `create_draft_workout` (по одной), `propose_phase`, `cancel_draft_workout` (только draft, без Garmin). `get_goals_on` оставлен.
- Скиллы в репо (`.claude/skills/`), оба на Sonnet, без `.mcp.json`; тренерские правила в скиллах — стартовые, правятся после прогона.
- qlty: порог параметров 7; vulture игнорирует `__signature__` и `@pytest.fixture*`; перехват исключений в `create_draft_workout` оставлен.
- rest_hr и lthr — из Garmin, не из env. rest_hr — последний из сна, не старше 14 дней (иначе ошибка «сделай coach sync»). Пороги хранятся с историей (`thresholds`).
- Порог — свой для каждого вида спорта; если Garmin его не даёт — считать самим по совокупности данных (проектируется отдельно).
- Растяжка в план/факт — перенесена: после выяснения typeKey на часах.
- Пороги по видам (2026-10-07, план папы-кабана, ответы пользователя «Recommended»): цепочка — пульсовые зоны Garmin по виду → беговой LTHR Garmin → смещение от бега (вело −7, плавание −12, константы в коде) → если бегового LTHR нет, 0.89 × max HR. Источник порога хранится и отдаётся через MCP. Силовая — фиксированно 35 TSS/час, растяжка — 0. TypeError не глушить: прямой вызов endpoint порога с разбором пустого ответа. Сначала спайк `get_heart_rate_zones` на реальном аккаунте.
- После ревью порогов (2026-10-07, ответы пользователя «Recommended»): max HR для запасного порога — `maxHeartRateUsed` из зон Garmin по виду, если нет — бег/вело за 365 дней; вело-порог `heartRateCycling` из latestLactateThreshold берётся как `bike`/`garmin_lt`. Строка из зон пишется только при изменении значения; 404 на зонах не валит sync.
- После аудита порогов (2026-10-07, «Recommended»): действует порог с более новой датой, при равной — зоны; вид без порога (нет ни LT, ни max HR) не блокирует нагрузку — его активности TSS 0 и предупреждение в ответе; незнакомые кардио-виды — по беговому порогу; список растяжки (yoga, pilates, stretching, mobility, flexibility_training) оставить, уточнить на часах. На сведение (технические, по ревью): PK thresholds (sport, calendar_date, source), строка зон только при изменении, lthr nullable, столбец max_hr, DEFAULT и trainingMethod игнорируются.

## Решения пользователя по шагу 8 (2026-10-07, «по рекомендациям»)
- Вес: допустимо 20–300 кг; nan/inf отвергаются; запятая как десятичный разделитель («81,7») принимается.
- КБЖУ: на всю запись целиком, каждое значение 0–10000; «посчитано» = `kcal IS NOT NULL`; посчитанное через MCP не перезаписывается.
- Время записи веса и еды — всегда «сейчас» (местное); `--at` и правка/удаление/пересчёт — в бэклог.
- `get_food_pending` с `truncated=true` → /coach-food просит повторный запуск.
- /coach-food пишет КБЖУ сразу окончательно, без черновика и подтверждения (отступление от плана «MCP-черновик»); исправление оценок — с пунктом бэклога о правке записей.
- /coach-food требует граммы у каждого продукта, «порции» не угадывает: без граммов спрашивает пользователя, запись остаётся непосчитанной (пользователь 2026-10-07). Остальное в скилле (итог дня, Sonnet) — по рекомендациям.

## Профиль спортсмена (шаг 11, 2026-10-07)
- `profile_log(id, key, value TEXT, source manual/garmin, logged_at, raw_json)` — миграция 0007, только добавление, индекс (key, logged_at). Текущее значение ключа — последняя запись; ручное главнее Garmin (Garmin — только если ручного нет); состояние на дату — записи с датой `logged_at` не позже неё. Та же запись из Garmin повторно не пишется.
- Ключи (белый список в `profile/service.py`): sex (m/f), birth_date, height_cm, activity_level, max_hr, injuries, limitations, equipment, schedule, preferences, diet, target_weight_kg, weight_goal (lose/keep/gain), weekly_rate_kg, kcal_target; `weight` — только из Garmin (запасной, в weight_log не пишется); `resting_hr` — только чтение из daily_metrics. Числа хранятся каноническим текстом, наружу отдаются числами.
- `current_profile(conn, day)` -> `values` (key -> value, source, logged_at), `age`, `weight_kg` (последний weight_log, иначе Garmin), `missing` (обязательные пустые + `goals`, если нет активных целей).
- `profile/nutrition.py`: Mifflin-St Jeor x коэффициент (1.2/1.375/1.55/1.725) + калории активностей дня минус BMR за время тренировки (не ниже 0); lose −15…20% (не ниже BMR), keep 0, gain +10% (weekly_rate_kg задаёт долю в пределах lose 15–20%, gain 5–15%, зажим — в assumptions); белок 1.8 (lose 2.0) г/кг, жир 0.9 г/кг, углеводы — остаток; `kcal_target` вручную главнее; нет пола/возраста/роста/веса — `kcal_target` None и `missing`.
- `coach sync` читает `get_user_profile()` (1 запрос); ошибка или неполный ответ — предупреждение в итоге, sync не падает. max_hr — из зон шага 7.
- CLI: `coach profile show/set`, `coach goal add/list/done/cancel`. MCP: `get_profile(date?, history?)` — значения с источниками, age, weight_kg, resting_hr, missing, nutrition; без raw_json, пишущих инструментов нет. `snapshot["profile"]` — только текущие значения, missing, nutrition, активные цели; в NOT_LISTS, не ужимается.
- Опрос — `.claude/agents/coach-onboarding.md`, читается тренером при непустом `missing`.

## Питание: продукты дома и рацион (шаг 12, 2026-10-07)
- `pantry_log(id, item, qty REAL, unit g/ml/pcs, op add/use/set, logged_at, note)` — миграция 0008, только добавление, индекс (item, logged_at). Остаток = последний `set` + Σadd − Σuse после него, не ниже 0 (use больше остатка — остаток 0 и предупреждение). Название — нижний регистр, без лишних пробелов; у продукта одна единица. `meal_plan_log(date PK, logged_at)` — дни, за которые рацион уже предложен.
- `store/pantry.py` (add_entry, list_entries, mark_meal_plan, has_meal_plan), `pantry/service.py` (record, stock, missing, shopping_list); `profile/nutrition.remaining(targets, eaten)` — цель минус съеденное (минус — перебор), `pending_count` — записи без КБЖУ; нет цели — None.
- CLI (`cli/pantry.py`): `coach pantry add|use|set|remove|list`, `coach shop "<продукт> <qty> <unit>" ...` / `--from-file` -> `data/shopping/YYYY-MM-DD.md` (база не меняется, наружу ничего), `coach shop done <файл>` — оприходовать строки «- продукт qty unit», `coach meal done` — отметить рацион на сегодня. Списание после еды — только по «да» (`coach pantry use`), `coach food` pantry не трогает.
- MCP: `get_pantry` ({rows: item, qty, unit, updated_at; truncated}, только qty > 0); `get_profile` и `snapshot["profile"]` + `nutrition_remaining`; snapshot + `pantry` (до 30 строк, только item/qty/unit, ужимается) и `meal_plan_today: bool` (в NOT_LISTS). Пишущих pantry-инструментов в MCP нет.
- Срок годности (шаг 13, миграция 0009; запись - dataclass `PantryEntry(op, item, qty, unit, now, expires_on, opened)`, `record(conn, entry)`): `pantry_log` + `expires_on TEXT` (NULL - не портится или неизвестно), `opened INTEGER` (0/1); ops + `open` (открыли упаковку: новый срок, qty 0, количество не меняется) и `spoil` (списание порчей, в остатке как use). Срок у партии: `add`/`set` с датой создают партию; `use`/`spoil` уменьшают партию с ближайшим сроком (FIFO, без срока - в конце); `open` ставит срок первой ЗАКРЫТОЙ партии (по ближайшему сроку) и помечает её открытой целиком (ограничение: одна запись add - одна партия; закрытых нет - ошибка); `pantry set` тоже принимает `--until`/`--opened`. `service`: `stock` + `expires_on` (ближайший), `opened`; `expiring(conn, today, days=2)` - партии со сроком ≤ today+days (qty только таких партий, `expired` - срок раньше today); `spoil(...)` без qty списывает весь просроченный остаток (срок раньше today).
- CLI: `coach pantry add ... [--until YYYY-MM-DD] [--opened]`, `coach pantry open <продукт> --until <дата>` (в allow, только меняет срок), `coach pantry spoil <продукт> [<qty> <unit>]` (НЕ в allow - с подтверждением Claude Code, после «да» пользователя). MCP: `get_pantry` + `expires_on`, `opened`; snapshot + `pantry_expiring` (≤ 10 строк, истекает ≤ 2 дней и просрочено; не в NOT_LISTS). Агент спрашивает «открыта ли упаковка?» при add; coach-meal берёт истекающее первым.
- Рацион на день тренер предлагает сам только при `meal_plan_today = false` (рацион ещё не предложен), потом `coach meal done`; дальше — по запросу. Первый запуск тренера за день — `first_run_today: bool` в snapshot (в NOT_LISTS, из `sync_log` kind=sync за дату: ≤ 1 запуска), по нему п. 8а coach.md спрашивает «что принимаешь» (шаг 22). Скилл `.claude/skills/coach-meal/SKILL.md` (≤ 3 КБ, Sonnet): только простые блюда, `diet` — жёсткий фильтр, КБЖУ — оценка.

## v2: нагрузка вне тренировок (шаг v2.1, 2026-10-10)
- Миграция 0015: `calendar_events` (UNIQUE (source, uid, start_at), `category` work/personal/hobby/rest/unknown, время местное, `date` — день начала, в `raw_json` нет участников и адресов) и `day_counters` (PK (date, kind), `value` REAL, `source`, `synced_at`). Белый список `kind` — `COUNTER_KINDS` в `store/workload.py`: todo_open, todo_closed, grooming_done, grooming_pending (ручные work_hours/hobby_hours/rest_hours добавит v2.2). Новый признак = новый kind без миграции.
- `store/workload.py`: `replace_calendar_window` (окно заменяется: пришедшее пишется, исчезнувшее удаляется, вне окна не трогается; неизменённая запись не перезаписывается, id и `synced_at` стабильны), `list_calendar_events`, `upsert_counter` (то же правило для счётчиков), `list_counters`.
- Конфиг вне репо `~/.config/ai-coach/workload.toml` (`$AI_COACH_WORKLOAD_CONFIG`): `[calendar] work/personal/hobby/rest/ignore`, `[paths] todo, hb_watch`. Названия календарей сравниваются по `strip()`; неразмеченный — `unknown` (хранится, в нагрузку не входит, имя в итоге sync); `ignore` не сохраняется. Нет конфига или нет разметки календарей — календарь пропущен, туду и груминг читаются по умолчаниям.
- Источники (только чтение, в базу — числа): `workload/calendar_eventkit.py` (`CalendarReader.read(date_from, date_to)`, EventKit через pyobjc импортируется лениво, `CalendarError` с подсказкой про настройки конфиденциальности), `workload/todo.py` (`todo_closed` — done/dropped по дню `updated`, `todo_open` — снимок на сегодня), `workload/grooming.py` (`grooming_done` — все файлы `done/` по дню mtime, `grooming_pending` — снимок). Закрытое и сделанное пишется за каждый день окна, в том числе нулём.
- `sync/workload_sync.py`: `sync_workload(conn, days, today, reader, config)` — окно `[today−days, today+14]`, читаем всё, потом одна транзакция; упавший источник — замечание в итоге и `sync_log` status error, остальные источники пишутся. `sync_log kind='workload'` (не `sync`, иначе ломается `first_run_today`). `coach sync` после Garmin всегда делает workload; ошибка Garmin нагрузку не прерывает, код выхода 1 сохраняется.
- Правила подсчёта (`workload/service.py`, часы на чтении): в часы идут не отменённые и не отклонённые события без all-day (tentative считается), повторы — каждый экземпляр, пересечения — объединение, через полночь — режется по дням; all-day рабочее событие даёт флаг `all_day_work`; вечер — после `EVENING_FROM` = 19:00; `weekend` — сб/вс. Часы считаются для work/personal/hobby/rest (`<категория>_hours`, `<категория>_evening_hours`).
- MCP: `get_workload(date_from, date_to, events=false)` (до 92 дней; `events=true` только на один день — названия по запросу), snapshot `workload` (7 дней назад, ряд по датам) и `workload_ahead` (7 дней вперёд, без названий и счётчиков). Календарь MCP не читает. Агент: строка нагрузки в сводке, логика — `.claude/agents/coach-wellbeing.md` по требованию.

## v2: вечерний чек-ин и общая нагрузка (шаги v2.2+v2.3, 2026-10-10)
- Миграция 0016: `wellbeing_log.mood`, `stress` (1-5, NULL - не спрашивали; старые строки живы). `coach feel <1-5> ["текст"] [--mood] [--stress] [--work ч] [--hobby ч] [--rest ч]`: оценки - в запись самочувствия, часы (0-24, запятая как точка) - в `day_counters` за сегодня (`source='manual'`, `work_hours`/`hobby_hours`/`rest_hours`; повторный ввод за день заменяет значение, не названное остаётся). Вечерний чек-ин сделан (`evening_done_today` в snapshot) - есть запись дня с `mood` или `stress`. `find_deviations`: `mood <= 2` (`MOOD_MAX`), `stress >= 4` (`STRESS_MIN`); для `mood`/`stress` берётся последнее непустое значение за день, остальное - из последней записи дня.
- `load/overload.py`, `total_load(day)` - линейная сумма (веса - константы модуля, догадка, калибровать по 2-3 неделям, менять только их):
  `total = W_TSS*tss + W_WORK*work + W_HOBBY*hobby + W_EVENING*work_evening_hours + W_WEEKEND*work (сб/вс) + W_TODO*todo_closed + W_GROOMING*grooming_done`
  с весами 0.05 / 1.0 / 0.5 / 0.5 / 0.5 / 0.2 / 0.5 (100 TSS = 5 пунктов; час работы = 1). `work` и `hobby` - ручные часы дня (`manual_work_hours`, `manual_hobby_hours`), если введены (0 тоже), иначе часы календаря; вечерние часы - только календарные. Отдых (`rest_hours`) в сумму не входит, хранится и отдаётся. Нет данных (None) - 0.
- `find_overload(days, metrics)` - сигналы на последний из 7 дней (`kind`, `value`, `limit`): `total_streak` - `total >= TOTAL_HIGH` (10) подряд `TOTAL_STREAK_DAYS` (3) дня до проверяемого включительно; `evening_streak` - рабочие часы после 19:00 подряд `EVENING_STREAK_DAYS` (3) вечера; `weekend_work` - рабочих часов в сб/вс окна не меньше `WEEKEND_WORK_MIN` (1); `recovery_drop` - среднее за 3 последних дня против среднего за 7 предыдущих (одна схема для всех показателей): `readiness` ниже на `READINESS_DROP` (10) и больше, `mood` ниже на `MOOD_DROP` (1.0) и больше, `stress` выше на `STRESS_RISE` (1.0) и больше; `mood`/`stress` - последнее непустое значение дня, окно самочувствия то же, что у `daily_metrics`; по каждому показателю нужны данные не менее чем за 2 и 3 дня (иначе он не считается); `value` и `limit` - объекты по сработавшим показателям (пороги - догадка); `todo_growth` - `todo_open` вырос с первого дня окна с данными до последнего на `TODO_GROWTH_MIN` (5) и больше, нужны два дня с данными.
- MCP `get_overload(date)`: `date`, `total`, `days` (7 дней: `date`, `total`, `manual_work/hobby/rest_hours`), `signals`; нет нагрузки тренировок - TSS считается нулём, `load_error`. Snapshot: `overload` (то же, в `NOT_LISTS`), `evening_done_today`, `workload_ahead[].overloaded` (`total_load` дня по календарю не меньше `TOTAL_HIGH`; тренировки и счётчики вперёд неизвестны, поэтому это прогноз только по календарю: отсутствие флага не гарантия), `wellbeing` с `mood`/`stress`.
- Агент: `.claude/skills/coach-evening/SKILL.md` (чек-ин; `bin/trener вечер`), реакция на сигналы - `.claude/agents/coach-wellbeing.md` (наблюдение, снижение объёма черновиками по `recalc.md` после согласия, «пустой вечер», перегруженные дни вперёд).

## v2: недельный обзор и роль коуча (шаг v2.5, 2026-10-11)
- Миграция 0018: `review_log(week_start PK, done_at, note)` — `week_start` понедельник ISO-недели. `store/review.py`: `mark_review` (upsert), `get_review`. `coach review done [--week YYYY-MM-DD] ["заметка"]`: без `--week` неделя обзора — в понедельник прошедшая, в остальные дни текущая; день считается как у `coach feel` (до `EVENING_CUTOFF` 04:00 — вчера, поэтому ночью на понедельник это ещё воскресенье); `--week` не понедельник — ошибка; повтор заменяет запись.
- `review/service.py`: `weekly_review(conn, today, weeks=4)` — недели ISO Пн-Вс от старой к новой, последняя (с `today`) `partial`. Строится из существующего: `day_entries` (из `load/overload.py`: `workload_series` + ручные часы + `total_load`), TSS из активностей (пульс покоя и пороги как для `get_load`; нет пульса покоя — `tss` недели None, `total` без TSS), самочувствие и `daily_metrics`. Поля недели: `tss`, `total` (сумма `total_load`), `work_hours` (ручные главнее календарных), `evening_hours`, `weekend_work_hours`, `todo_closed` (сумма), `todo_open` (последний снимок недели), `mood`, `stress` (среднее последних за день), `sleep` (`sleep_score`), `readiness` (None — данных нет), `days_with_data`, `delta` (разница с предыдущей неделей; у первой недели `delta` = None, где нет базы — None). Выводы делает агент.
- `review_due`: `week_review_due` в snapshot — день самочувствия Вс или Пн и записи `review_log` за неделю обзора нет (Вс — текущая неделя, Пн — прошедшая).
- MCP `get_weekly_review(weeks=4)`: 1 ≤ weeks ≤ 12, иначе `ToolError`; ответ `{rows, truncated}`.
- Роль коуча из файлов (лимиты проверяют тесты): `coach.md` ≤ 15360 Б (ядро: порядок разговора, строки-триггеры), `coach-wellbeing.md`, `coach-nutrition.md` (в него вынесены срок годности и рецепты из шага 4а), `coach-week.md`, `coach-onboarding.md` — каждый ≤ 6144 Б, читаются `cat` по триггеру, каждый в allow. `coach-week.md`: `get_weekly_review`, выводы по трендам и дельтам со связью с выгоранием, 1-2 изменения на неделю черновиками, в конце `coach review done`.

## v2: запись тренера в Apple Calendar (шаг v2.6, 2026-10-11)
- Схема как у тренировок: MCP пишет только черновик (`create_draft_event`, `cancel_draft_event` — только draft), в календарь пишет CLI `coach event write` после «да» Влада. `write`/`remove` не в allow (двойное подтверждение: «да» в чате и запрос Claude Code), `event list`/`event cancel` — в allow.
- Миграция 0019 `coach_events`: `kind` (training/practice/rest/sleep/checkin/task), `title`, `date` (день начала), `start_at`/`end_at` (местное время без пояса), `all_day`, `note`, `category` (work/personal/hobby/rest или NULL — в нагрузку не входит), `alarm_min`, `repeat` (только `daily` у `checkin`, CHECK), `workout_id`, `practice_id` (без внешних ключей, живость проверяет service), `status` draft/written/cancelled/removed, `calendar_uid`, `created_at`/`written_at`/`removed_at`, `removed_by` cli/calendar. Индексы по `date`, `status`, `calendar_uid`.
- `store/agenda.py`: `add_event`, `get_event`, `update_event`, `list_events(date_from, date_to, statuses)`, `category_by_uid`, `find_by_uid`, `active_repeat`.
- `agenda/service.py`: `validate_draft` (kind; непустое название; начало раньше конца; не длиннее 24 ч; день начала от −30 до +14 дней; `repeat` только `daily` у `checkin` и один активный (draft/written); тренировка (не отменена) и практика (живая) существуют; категория по умолчанию: rest/sleep — `rest`, у task категория обязательна (нет — ошибка), у остальных не задаётся), `create_draft`, `write_event` (draft → written), `remove_event` (written → removed, `removed_by='cli'`, у повторяющегося — будущие вхождения), `cancel_event` (draft → cancelled), `agenda_rows` (draft/written + активный повторяющийся, без служебных полей). Порядок EventKit → база: сбой календаря базу не меняет, сбой базы после календаря — `AgendaError` с uid.
- `agenda/calendar_write.py`: `CalendarWriter(calendar)` — `write(event) -> eventIdentifier`, `remove(uid, future)`; EventKit лениво, `_request_access` и `_ns_date` общие с читателем. Календарь ищется по точному названию (strip), ровно один, `allowsContentModifications`; `save/remove` возвращают `(ok, err)` — проверяется `ok`. `remove` снимает только событие из календаря коуча. Повторяющийся чек-ин — один `eventIdentifier` на все вхождения, снимается с `EKSpanFutureEvents`. MCP модуль не импортирует.
- `workload.toml`: `[coach] calendar = "<название>"`; пусто — не задан; такое же название в `[calendar]` — ошибка; категория календаря `coach`.
- `sync_workload`: события календаря коуча — свои по `calendar_uid` (записанные тренером) идут в `calendar_events` с категорией из `coach_events` (NULL — не хранятся), чужие (добавлены руками) пропускаются со счётчиком в итоге; записанные события, пропавшие из календаря (день начала в окне или повторяющееся), получают `status='removed'`, `removed_by='calendar'`; всё в одной транзакции, ошибка календаря ничего не помечает.
- Событие, перенесённое руками в Calendar.app за окно sync, помечается `removed_by='calendar'` (перенос `move` — в закрома).
- MCP: `get_agenda(date_from, date_to)` (до 92 дней), snapshot `agenda` (день назад и 7 вперёд, draft/written, компактные поля); CLI `coach event list/write/remove/cancel` (`write`, `remove`, `cancel` принимают несколько id, коммит после каждого, ошибка одного не останавливает остальные, код выхода 1); нет `[coach]` — ошибка до обращения к EventKit.
- Роль: `.claude/agents/coach-agenda.md` (≤ 6144 Б, в allow), триггер 9в в `coach.md`, ссылки из `coach-wellbeing.md` и `coach-week.md`.
