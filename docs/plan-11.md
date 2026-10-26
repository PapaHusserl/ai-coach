# Шаг 11 — детальный план папы-кабана (2026-10-07)

Решения пользователя и спайк — docs/plan.md → «Шаг 11». Там, где этот файл расходится с решениями, главнее plan.md.

## Файлы
- `src/ai_coach/store/migrations/0007_athlete_profile.sql` — `profile_log(id, key TEXT NOT NULL, value TEXT NOT NULL, source TEXT CHECK (source IN ('manual','garmin')), logged_at TEXT NOT NULL, raw_json TEXT)`, индекс (key, logged_at). Только добавление; текущее значение ключа — последняя запись; ручное главнее Garmin (Garmin — только если ручного по ключу нет); состояние на дату — `logged_at <= дата`.
- `src/ai_coach/store/profile.py` — слой доступа (как store/goals.py).
- `src/ai_coach/profile/service.py`:
  - белый список ключей с типом и проверкой: sex (m/f), birth_date, height_cm, activity_level (sedentary/light/moderate/active), max_hr; injuries, limitations, equipment, schedule (свободный текст), preferences, diet; target_weight_kg, weight_goal (lose/keep/gain), weekly_rate_kg, kcal_target (ручное переопределение); resting_hr — только чтение из daily_metrics;
  - `set_value(conn, key, value, source, now)` — проверка и одна запись; то же значение из Garmin повторно не пишется (sync идемпотентен);
  - `current_profile(conn, day)` — key→{value, source, logged_at}; вычисляемые age (из birth_date), weight_kg (последний weight_log, иначе Garmin); `missing` — обязательные пустые: sex, birth_date, height_cm, weight, activity_level, schedule, equipment, injuries (ответ «нет» — тоже значение), weight_goal; плюс признак «нет активных целей».
- `src/ai_coach/profile/nutrition.py` — чистые функции, константы в модуле: BMR Mifflin-St Jeor (м: 10w+6.25h−5a+5; ж: −161); TDEE = BMR × (1.2/1.375/1.55/1.725) + калории активностей дня, если поле есть в activities, иначе только коэффициент; lose −15…20% (не ниже BMR), keep 0, gain +10%, weekly_rate корректирует; белок 1.8 г/кг (keep/gain), 2.0–2.2 (lose); жир 0.8–1.0 г/кг; углеводы — остаток; kcal_target вручную — главнее; не хватает пола/возраста/роста/веса → None + список недостающего.
- `src/ai_coach/sync/garmin_sync.py` — `read_user_profile(client)` в `coach sync` (1 запрос `get_user_profile()`), через `garmin_errors()`: ошибка → предупреждение, sync не падает. Пишет в profile_log с source=garmin: sex (MALE→m, FEMALE→f), birth_date, height_cm, weight (граммы→кг, запасной; в weight_log НЕ пишется), schedule-кандидат из `availableTrainingDays` (если нет ручного). VO2max в user-settings null — не берём. Max HR — из зон (шаг 7), если там есть `maxHeartRateUsed`.
- CLI `src/ai_coach/cli/main.py`: `coach profile show` (кратко: текущие значения + missing), `coach profile set <key> <value>` (неизвестный ключ → ошибка с перечнем); `coach goal add "<название>" [--kind] [--target] [--date] [--priority]`, `coach goal list`, `coach goal done <id>`, `coach goal cancel <id>` — через goals.service (события в goal_events). Итог `coach sync` — коротко, только какие ключи профиля обновились.
- MCP `tools.py`/`server.py`: `get_profile(date?)` — профиль с источниками и историей по запросу, `missing`, `nutrition` (bmr, tdee_rest, tdee_today, kcal_target, protein_g, fat_g, carbs_g, формула, допущения); без raw_json. `snapshot["profile"]` — ТОЛЬКО текущие значения (без истории и источников), непустые ключи, `missing`, `nutrition`, активные цели; в NOT_LISTS (не ужимается). Пишущих инструментов не добавлять.
- `.claude/agents/coach.md`: tools + `mcp__ai-coach__get_profile`; 3–5 строк правил: если `profile.missing` не пуст или нет целей — прочитать `.claude/agents/coach-onboarding.md` и провести опрос до сводки; КБЖУ-цели не считать самому — брать `profile.nutrition`; травмы/ограничения учитывать во всех рекомендациях. 
- `.claude/agents/coach-onboarding.md` (новый) — сценарий опроса по блокам: анкета → травмы/ограничения → инвентарь и расписание (предложить дни из Garmin) → цель по весу → цели с датами; каждый ответ сразу `uv run coach profile set` / `uv run coach goal add`; в конце `coach profile show`; при повторе — только недостающее.
- `.claude/settings.json`: allow `Bash(uv run coach profile:*)`, `Bash(uv run coach goal:*)`, `Bash(cat .claude/agents/coach-onboarding.md)`. Если правку заблокирует классификатор — пользователь вручную.
- Скиллы: coach-plan — schedule, equipment, injuries/limitations, цели и фаза (вело сб/вс — как было); coach-food — итог дня против `nutrition` (остаток/перебор); coach-morning — строка «вес → цель, темп за 2 недели».
- Документы: architecture (profile_log, get_profile), pipeline.md.

## Тесты (TDD, кабан-доеба)
- 0007 на пустой базе и после 0006; повторное открытие ничего не меняет.
- `profile set sex x` / `height_cm abc` / неизвестный ключ → ошибка, 0 строк.
- 180 → 181: current 181, 2 строки, на дату между — 180.
- Manual vs Garmin: Garmin 178 + manual 180 → 180 (manual); только Garmin → 178 (garmin).
- Sync с фикстурой `tests/fixtures/garmin/user_profile.json`: 80000 г → 80.0 кг, MALE → m, birthDate → birth_date; повторный sync новых строк не добавляет.
- Garmin 429 / неполный userData → sync завершён, предупреждение, profile_log не тронут.
- weight_log 82.0 и Garmin 81.7 → weight_kg 82.0.
- nutrition: м, 35 лет, 180 см, 80 кг → BMR 1755; moderate → TDEE ≈ 2720; lose → не ниже BMR; Б/Ж/У в сумме = kcal_target ±1%; без пола → None, missing=["sex"]; kcal_target вручную главнее.
- `missing` на пустой базе — все обязательные + «нет целей»; после заполнения пуст.
- `coach goal add "Полумарафон" --date 2027-04-01` → goals + goal_events, get_goals отдаёт; `goal done` → done + событие.
- MCP `get_profile` без raw_json; set через MCP нет; snapshot содержит `profile` (без истории) и не теряет его при ужатии.
- Ручная проверка пользователем: `тренер` на пустом профиле проводит опрос, следующий запуск не спрашивает повторно.
