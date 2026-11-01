# Шаг Н11. Сигнал «возможно, заболеваешь»

Закрывает BACKLOG 24. План — папа-кабан, 2026-11-01, режим «встроить». Разведка на HEAD bcbe3ec. Основание —
docs/research-baseline.md «Физиологические базы» (HRV и пульс покоя: 7-дневное среднее и коридор ±SWC, Plews) и «Болеть
меньше» (рост пульса покоя и падение HRV предшествуют симптомам на 1–2 дня; сон < 6 ч — риск простуды ×4, Prather 2015).
Место в очереди — docs/plan-roadmap-r1.md:142 (после Н4: «с учётом сна» берёт `sleep_report`), :149–153 (развилка
«наблюдение / действие», ложные срабатывания после тяжёлой тренировки — учесть нагрузку дня), :164 (к К3 — хотя бы одно
срабатывание, сверенное с самочувствием), :185 (сигнал болезни → лёгкий день в плане дня — партия этого плана). Решения
Влада — NOTES.md 2026-10-31: цель — болеть по минимуму; текущее поведение тренера не трогать; новые фичи стартуют в
режиме наблюдения; красные флаги — тренер действует. Живая база — только чтение (`?mode=ro`); в документе — счётчики без
личных цифр (репо публичное).

## Суть

Личный коридор для пульса покоя и HRV по ночам Garmin, которые уже лежат в `daily_metrics`; день «вне коридора» — пульс
выше и HRV ниже; подряд `STREAK_DAYS` дней — сигнал `illness_risk`. Сон и вчерашняя тренировка — контекст сигнала
(Р3, Р4). Тренер видит сигнал в утренней сводке и реагирует по Р5; план дня при сигнале — лёгкий день по Р6.

Что есть по коду (как встраиваем):

- **Данные.** HRV: колонка `daily_metrics.hrv_last_night` (0001; API — `hrvSummary.lastNightAvg`, `sync/garmin_sync.py:86`;
  импорт — `metrics[type=HRV].value`, `sync/export_days.py:39`). Пульс покоя: колонки нет, читается из `raw_json`:
  API-строки — `$.sleep.restingHeartRate` (так читает `store/garmin_data.py:116 last_rest_hr`); импортные строки — список
  `$.hrv.metrics[]` с `type` HR/HRV/SPO2/SKIN_TEMP_C/RESPIRATION, пульс покоя — `type = 'HR'`, `value` (разведка живой
  базы 2026-11-01: HR есть у 294 из 294 импортных строк с HRV, значения в диапазоне 30–100 у всех; API-строк 32, пульс
  у всех 32). Последние 90 дней: HRV и пульс — 90 из 90 дней (58 импорт до 2026-09-30, 32 API с 2026-10-01). Два пути
  чтения через `COALESCE(json_extract(...), (SELECT ... FROM json_each(...)))` — прецедент `nap_seconds` в
  `list_sleep_nights` (`:32-34`). Выборка трёх колонок без `raw_json` за 28 дней — 13 мс (замер); `SELECT *` не годится
  (API-строка `raw_json` ~183 КБ, среднее по 32).
- **Стык источников.** Среднее пульса покоя за сентябрь (импорт) против октября (API) — отношение 1,10, HRV — 1,04:
  «HR» экспорта и `restingHeartRate` API могут считаться по-разному. База коридора 28 дней на 2026-11-01 целиком из
  API-строк — стыка нет; 60 дней его захватывает (умолчание 1 — 28).
- **Готовые суждения Garmin.** `hrv_status` (API: BALANCED/UNBALANCED/LOW/POOR; импорт: IN_RANGE/BELOW/ABOVE) уже даёт
  отклонение `hrv` в `find_deviations` (`load/deviations.py:9, :44-46`); Garmin-коридор HRV — `hrvSummary.baseline`
  (`balancedLow`, `balancedUpper`) у API и `baselineLowerLimit/UpperLimit` у метрик импорта; у пульса покоя в API
  коридора нет. За 90 дней Garmin пометил HRV плохим (BELOW/LOW/UNBALANCED) 25 дней из 90 — своя калибровка нужна в любом
  случае (Р1 вариант 3 — только HRV).
- **Образцы.** `load/overload.py:94 _recovery_drop` — «последние дни против базы»; `:168 overload_report(conn, day, tss)` —
  отчёт для MCP и snapshot с `days` и `signals`; `mcp_server/overload.py:14` — инструмент в своём модуле с `load()` и
  `load_error`; `load/sleep.py` (Н4) — константы-догадки + чистые функции + `sleep_report`; `snapshot.py:65 NOT_LISTS`,
  `:185-186` — ключи `overload`, `sleep`; `agenda/sleep_limits.py:21 sleep_limits` — поправка плана дня по сигналу.
- **Замер коридора на живой базе** (скрипт в scratchpad, 90 дней до 2026-11-01, центр — среднее 7 предыдущих дней, SWC —
  k × SD за базу, сегодняшний день в центр и базу не входит; только счётчики):

  | база | k | оба (пульс выше и HRV ниже) | любой из двух | эпизодов ≥ 2 дней подряд (оба / любой) |
  |---|---|---|---|---|
  | 28 | 0,5 | 20 дней из 90 | 38 | 4 / 12 |
  | 28 | 1,0 | 4 | 15 | 0 / 4 |
  | 60 | 0,5 | 22 | 38 | 4 / 12 |

  Логарифм HRV (Plews, Ln rMSSD) против сырых мс — 19 против 20 дней, эпизодов 3 против 4: разницы нет, берём мс
  (умолчание 2). Вывод: k = 0,5, «оба» и 2 дня подряд дают ~4 эпизода за квартал — порядок «возможно, заболеваешь»;
  «любой» — 12, k = 1 — ноль. Сколько раз Влад реально болел за эти 90 дней — не знаем, сверка — К3 (r1:164).
- **TSS как признак тяжёлой тренировки** (r1:153): за 60 дней `get_load` TSS > 0 у 12 дней, ≥ 50 — у 0 (силовые и
  растяжка по пульсу дают мало). Абсолютный порог «тяжёлой» не сработает — признак `trained_yesterday` (TSS вчера > 0) с
  цифрой `tss_yesterday`, без порога (Р4).
- **Тексты и лимиты** (`wc -c`): `coach.md` 15 524 / 16 384 (запас 860 Б; строка инструмента +30 Б, фраза ~150 Б —
  влезает); `coach-wellbeing.md` 8 160 / 8 192 — абзац не влезает, лимит → 9 216 (`grep -rn 8192 tests/`: 4 строки в
  3 файлах — `test_skills_workload.py:10`, `test_skills_agenda.py:84`, `test_skills_practices.py:12,31`; `test_skills_help.py:22`
  — лимит тем справки, не трогаем). ROADMAP:82 записал этот подъём долгом Н12 — забирает Н11, строку Н12 правит архитектор
  при закрытии. `recovery.md` 1 396 / 3 072; `recalc.md` 1 623 / 3 072; `coach-day.md` 5 336 / 6 144; справка
  `coach-help/sleep.md` 2 293 / 8 192 (allow-строка уже есть, `settings.json:8`), `wellbeing.md` 7 179 / 8 192 (запас для
  Н12 WHO-5 — plan-n2 «Риски», не трогаем).
- **Snapshot на живой базе сегодня — 19 813 Б при лимите 20 000** (замер `morning_snapshot(conn, "2026-11-01")`; `sleep`
  260 Б, `overload` 1 292 Б). Новый ключ в 200–300 Б пройдёт через цикл обрезки `snapshot.py:210` — тот укоротит самый
  длинный список (рядов по датам — с начала) и поставит `truncated`. Поэтому в snapshot — отчёт без `days` (умолчание 7),
  полный — в `get_illness`.

**Правило:** новое — коридор и сигнал (`load/illness.py`): день вне коридора — `rhr > mean7(rhr) + SWC_K × sd28(rhr)` и
`hrv < mean7(hrv) − SWC_K × sd28(hrv)` (Р1); сигнал `illness_risk` — `streak >= STREAK_DAYS` (Р2). Существующее
`find_deviations`: `status.upper() in BAD_HRV_STATUSES` (`load/deviations.py:45`) — не меняется (при Р5 = 2 в
`tools.day_deviations` добавляется kind `illness` из отчёта, сама `find_deviations` не трогается). При Р6 = 1: было
`signals = [s for s in report["signals"] if ...]` по одному отчёту сна (`sleep_limits.py:36`) → станет сигналы сна + сигнал
`illness_risk`, блоков `focus_max − 1` при любом из них, причина — по первому.
**Поведение:** меняется — (1) новый MCP `get_illness(date)`; (2) ключ `illness` в `get_morning_snapshot`; (3) по Р5 — фраза
в утренней сводке при сигнале и реакция тренера (предложение снять интенсивное, совет сна и отдыха); (4) по Р6 — план дня при
сигнале ставит фокус-блоков меньше. Не меняется: `find_deviations` (кроме Р5 = 2), `recalc.md` (кроме строки-триггера по Р5),
`get_sleep`, `find_overload`, недельный обзор, вечерний чек-ин, `coach feel`.
**Вне репо:** MCP-сервер перезапустить после партии 1 (новый инструмент) и после партии 2 при Р6 = 1 (описание
`create_day_plan`). Garmin — новых запросов нет, пульс и HRV уже в `raw_json`/колонках. `settings.json` — не нужен
(раздел в `sleep.md`, allow есть). Новых зависимостей нет (`statistics.mean`, `statistics.pstdev` из stdlib).

## Решения

Влад, 2026-11-01 (окна по одному):

- Р1 — (1) оба: пульс покоя выше и HRV ниже коридора.
- Р2 — (1) сигнал при 2 днях подряд, один уровень.
- Р3 — (1) сон — контекст (`short_night` в confounders, `sleep_debt` — «риск выше»).
- Р4 — (1) тренировка накануне — контекст (`trained_yesterday`, TSS рядом).
- Р5 — (3) фраза с цифрами и вопрос о симптомах, предложение снять интенсивное после «да», совет сна и отдыха.
- Р6 — (1) план дня в этом шаге: фокус-блоков на один меньше, причина в `skipped`.
- Умолчания 1–12 — приняты.

## Справка (правило AGENTS.md)

Новые функции: MCP `get_illness`, поле `illness` в сводке, по Р5 — фраза и реакция тренера, по Р6 — поправка плана дня.

- `.claude/agents/coach-help/sleep.md` — новый раздел «## Возможно, заболеваешь - `get_illness`» после «Долг сна»
  (умолчание 9: раздел здесь, не новый файл — allow-строки Влада не нужно; заголовок файла → «# Сон и восстановление: долг
  сна, сигнал болезни»): что это (личный коридор — среднее ваших ночей за 7 дней ± половина разброса за 28 дней, нужно
  не меньше 14 дней; день вне коридора — пульс покоя выше и HRV ниже; 2 дня подряд — сигнал «возможно, заболеваешь»;
  предвестник на 1–2 дня, не диагноз), как запустить («не заболеваю ли?», «как пульс и HRV?» — тренер читает `illness` из
  сводки или `get_illness`; своей команды нет), что получу (пульс покоя и HRV за ночь, центр и граница коридора по каждому
  — `rhr_high_from`, `hrv_low_from`; `out_today`, `streak` — дней вне коридора подряд; `days` — 7 дней с флагами;
  `confounders` — что могло сдвинуть цифры без болезни: короткая ночь, тренировка вчера; `sleep_debt`; сигнал
  `illness_risk`; данных меньше 14 дней — коридора нет), что делает тренер — по Р5. Цифры в тексте — те же константы
  `load/illness.py` (тест-сверка ниже). Размер — кабан меряет `wc -c`, лимит 8 192.
- `.claude/agents/coach-help.md:16` — строка «Сон - долг сна, норма, короткая ночь, время от подъёма, `get_sleep` -
  `sleep.md`» → «Сон и восстановление - долг сна, короткая ночь, время от подъёма, сигнал «возможно, заболеваешь»
  (пульс покоя и HRV), `get_sleep`, `get_illness` - `sleep.md`» (≤ 200 симв., лимит файла 6 144, сейчас 3 482).
- `tests/test_skills_help.py`: `test_illness_topic_has_fields` (`get_illness`, `illness_risk`, `streak`, `rhr_high_from`,
  `hrv_low_from`, `confounders`), `test_illness_topic_thresholds_match_constants` по образцу `:170`
  (`f"{illness.CENTER_DAYS} дней"`, `f"{illness.BASELINE_DAYS} дней"`, `f"{illness.MIN_BASELINE_DAYS} дней"`,
  `f"{illness.STREAK_DAYS} дня подряд"`); полнота — существующие `test_every_mcp_tool_is_in_help`,
  `test_index_mentions_every_topic_file`, `test_allow_has_every_topic_file`.
- `docs/architecture.md` — раздел «## Н11: сигнал „возможно, заболеваешь“» после «## Н4: долг сна» (`:237-241`);
  `README.md:68` — абзац после «Долг сна».

## Модули, файлы, функции

Партия 1 — данные, расчёт, MCP, snapshot, справка (работает при любых ответах Р5/Р6 — режим наблюдения):

- `src/ai_coach/store/garmin_data.py`: `list_recovery_days(conn, start, end) -> list[dict]` — новая (образец
  `list_sleep_nights` `:24`): `SELECT date, hrv_last_night AS hrv, COALESCE(json_extract(raw_json,
  '$.sleep.restingHeartRate'), (SELECT json_extract(value, '$.value') FROM json_each(raw_json, '$.hrv.metrics') WHERE
  json_extract(value, '$.type') = 'HR')) AS rhr FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date`; без
  `raw_json`; нет ни того ни другого — `rhr None`.
- `src/ai_coach/load/illness.py` — новый (образец `load/sleep.py`; docstring: коридор, формула, «константы — догадка,
  калибрует v2.9»): `CENTER_DAYS = 7`, `MIN_CENTER_DAYS = 4`, `BASELINE_DAYS = 28`, `MIN_BASELINE_DAYS = 14`, `SWC_K = 0.5`,
  `STREAK_DAYS = 2`, `SHOWN_DAYS = 7`;
  `corridor(rows, day, key) -> dict | None` — `{"mean7", "swc"}` по строкам с `key` не None за `[day − CENTER_DAYS, day − 1]`
  (центр) и `[day − BASELINE_DAYS, day − 1]` (SWC = `SWC_K × pstdev`); меньше `MIN_CENTER_DAYS` или `MIN_BASELINE_DAYS` — None;
  `day_flags(row, rhr_corridor, hrv_corridor) -> dict` — `{"rhr_high", "hrv_low", "out"}` (`out` — по Р1; значения или
  коридор None → все None);
  `out_streak(flags_by_date, day) -> int` — дней подряд с `out True`, считая с `day` назад; день с `out` None или False
  прерывает (умолчание 5);
  `illness_signals(report) -> list[dict]` — `illness_risk` при `streak >= STREAK_DAYS` (`{"kind", "value": streak,
  "limit": STREAK_DAYS}`, формат как `sleep_signals`); при Р2 = 2 ещё `illness_watch` при `streak == 1`;
  `illness_report(conn, day, tss=None, sleep=None) -> dict` — `{date, rhr, rhr_mean7, rhr_high_from (mean7 + swc),
  rhr_high, hrv, hrv_mean7, hrv_low_from (mean7 − swc), hrv_low, out_today, streak, baseline_days, days: [{date, rhr, hrv,
  out}] × SHOWN_DAYS, confounders: ["short_night", "trained_yesterday"] (по Р3/Р4), tss_yesterday, sleep_debt (bool),
  signals}`; `tss` — словарь TSS по дням как у `overload_report` (нет — `tss_yesterday None`, `trained_yesterday` не
  ставится); `sleep` — готовый `sleep_report` (snapshot уже его посчитал; None — считает сам через `ai_coach.load.sleep_report`).
  Чтение одним `list_recovery_days(conn, day − BASELINE_DAYS, day)`.
- `src/ai_coach/load/__init__.py` — экспорт `illness_report`.
- `src/ai_coach/mcp_server/illness.py` — новый (образец `mcp_server/overload.py`): `illness(conn, date)` — `period(date,
  date)`, `load(conn, shift_day(date, −1), date)` → `tss`; `ToolError` → отчёт с `tss = {}` и `load_error`.
- `src/ai_coach/mcp_server/server.py:153` — `get_illness` после `get_sleep`: «Сигнал „возможно, заболеваешь“ на дату
  (YYYY-MM-DD): rhr / hrv — пульс покоя и HRV за ночь; rhr_mean7, hrv_mean7 — среднее за 7 предыдущих дней; rhr_high_from /
  hrv_low_from — границы личного коридора (±0,5 SD за 28 дней; null — данных меньше 14 дней); rhr_high, hrv_low, out_today —
  день вне коридора (пульс выше и HRV ниже); streak — таких дней подряд; days — 7 дней (date, rhr, hrv, out); confounders —
  что могло сдвинуть цифры без болезни (short_night, trained_yesterday); tss_yesterday; sleep_debt — долг сна (риск выше);
  signals — illness_risk (kind, value = streak, limit; пусто — норма). Не диагноз.»; описание `get_morning_snapshot` (`:61`) —
  «sleep (как get_sleep), illness (как get_illness, без days)».
- `src/ai_coach/mcp_server/snapshot.py:186` — `snapshot["illness"] = illness_report(conn, date, tss, snapshot["sleep"])`
  без ключа `days` (умолчание 7); `NOT_LISTS` (`:65`) + `"illness"`.
- `.claude/agents/coach.md:5` — `, mcp__ai-coach__get_illness` после `get_sleep` (+30 Б; 15 554 / 16 384, лимит не
  поднимаем). При Р5 = 1 в партии 1 — одно предложение в п. 2 «`illness` в snapshot — наблюдение: без вопроса не озвучивай»
  (чтобы тренер не реагировал сам; см. риски).
- Справка — раздел выше; `README.md:68`; `docs/architecture.md`.
- Тесты: новые `tests/test_load_illness.py`, `tests/test_mcp_illness.py`; правки `tests/test_store_garmin_data.py`,
  `tests/test_mcp_snapshot.py:86` (+`"illness"`), `tests/test_mcp_no_push.py:33` (+`get_illness`, 36 → 37 имён),
  `tests/test_skills_help.py`.

Партия 2 — реакция тренера (состав — по Р5 и Р6):

- При Р5 = 3 (рекомендация) или 2: `.claude/agents/coach.md:18` — после фразы про `sleep.signals`: «`illness.signals`
  (возможно, заболеваешь: пульс покоя выше и HRV ниже личного коридора 2 дня подряд) - одной фразой с цифрами, реакция - там же
  в `coach-wellbeing.md`» (~170 Б). `.claude/agents/coach-wellbeing.md` — абзац «Возможно, заболеваешь» после абзаца «Сон»
  (`:11`): поля `illness` (как в описании `get_illness`); при `illness_risk` — назвать с цифрами (пульс N против границы M,
  HRV N против M, дней подряд), спросить о самочувствии и симптомах; предложить на ближайшие 2–3 дня снять интенсивное из
  черновиков (интервалы, тяжёлая силовая → лёгкое, растяжка или отдых) и после «да» действовать по `recalc.md`;
  утверждённые и отправленные — попросить снять на часах самому; совет сна и отдыха: лечь раньше, практика `sleep` из
  `get_practices`, не добирать нагрузку; `confounders` назвать («вчера тренировка / короткая ночь — сдвиг может быть от них»),
  `sleep_debt` — «риск выше»; Garmin-отклонение `hrv` из `get_deviations` в тот же день — одна фраза, не две; температура,
  боль — п. 8б `coach.md` («к врачу»). ~800 Б → лимит 8 192 → 9 216 в трёх файлах тестов (см. «Суть»).
  `.claude/skills/coach-plan/recalc.md:3` — в «Когда» добавить «или `illness_risk` в `illness` и пользователь согласился
  снять интенсивное (`coach-wellbeing.md`)» (~90 Б). `.claude/skills/coach-morning/recovery.md:5` — «…`caution_from`;
  `illness` - пульс покоя и HRV против коридора, дней подряд» (одна строка).
  При Р5 = 2 ещё: `src/ai_coach/mcp_server/tools.py:212 day_deviations` — к `find_deviations(...)` добавить сигналы
  `illness_report(conn, day, {}, None)["signals"]` как `{"kind": "illness", "value": streak, "limit": STREAK_DAYS}`;
  `coach.md:22` и `recalc.md:3`, `coach-help/wellbeing.md:33` — порог «пульс покоя выше и HRV ниже коридора 2 дня»;
  `test_wellbeing_topic_deviation_thresholds_match_deviations` (`test_skills_help.py:123`).
  При Р5 = 1: партии 2 по текстам нет (строка «наблюдение» уже в партии 1).
- При Р6 = 1: `src/ai_coach/agenda/sleep_limits.py:21 sleep_limits` — после `sleep_report` ещё `illness_report(conn,
  today.isoformat(), {}, report)`; `signals` — сигналы сна (как сейчас) + `illness_risk` (для `day` сегодня и завтра:
  болезнь за ночь не проходит); `_sleep_reason` (`:13`) — ветка `illness_risk`: «фокус: блоков меньше - возможно,
  заболеваешь (пульс покоя N, HRV M вне коридора {streak} дня подряд)»; предел `caution_from` — только от сигналов сна
  (умолчание 11); docstring модуля — «по сну и сигналу болезни». `src/ai_coach/mcp_server/agenda.py:58-72` — docstring
  `create_day_plan` («При сигнале сна фокус-блоков меньше…», `:72`) + «и при сигнале „возможно, заболеваешь“». `.claude/agents/coach-day.md:5` — «При сигнале сна
  (`short_night`, `sleep_debt`) или сигнале болезни (`illness_risk`) фокус-блоков на один меньше…» (+~40 Б, 5 376 / 6 144).
  Имя модуля `sleep_limits` остаётся (умолчание 11; переименование — 9 ссылок в `tests/test_agenda_day_plan.py`).
- Тесты партии 2: `tests/test_skills_workload.py` (абзац «Возможно, заболеваешь», лимит 9 216, `illness.signals` в `coach.md`,
  `recovery.md`), `tests/test_skills_text.py` или `test_skills_evening.py` (строка `coach.md`), при Р6 = 1 —
  `tests/test_agenda_day_plan.py`, `tests/test_mcp_day_plan.py`, `tests/test_skills_day.py`.

Не трогаем: `load/deviations.py`, `load/overload.py`, `load/sleep.py`, `review/service.py`, `sync/garmin_sync.py`,
`sync/export_days.py`, `store/garmin_data.py:last_rest_hr`, `.claude/skills/coach-evening/SKILL.md` (сигнал — утренний:
ночь известна утром), `cli/*` (своей команды нет), `bin/trener`, миграции (колонки не добавляем — умолчание 4).

## Партии

Две партии — граница по развилкам, как в Н4 (docs/plan-n4.md «Партии»): партия 1 — данные и инструмент при любых ответах
(наблюдение); партия 2 — только то, что Влад выберет в Р5/Р6; при Р5 = 1 и Р6 ≠ 1 партии 2 нет. Каждая партия
самодостаточна: свой коммит после ревью и тестов, аудит по коммиту, `docs/pipeline.md` — строка (оркестратор). Внутри
партии — порядок family.md: кабан-доеба (красные тесты) → кабан → `make check` → ревью, аудит → коммит → проверка Влада.

1. **Коридор, MCP, snapshot, справка** — `store/garmin_data.py`, `load/illness.py`, `mcp_server/illness.py`, `server.py`,
   `snapshot.py`, `coach.md:5`, `sleep.md`, `coach-help.md`, README, architecture, тесты. На выходе: `get_illness("2026-11-02")`
   отдаёт пульс, HRV, коридор, `streak`, `days`, `confounders`, сигналы; snapshot содержит `illness`; «не заболеваю ли?» —
   ответ по справке. Объём: ~120 строк кода (`illness.py` ~85, store ~15, MCP-модуль ~20), ~220 строк тестов, ~1,5 КБ
   текста (ожидание, не проверено; аналог — Н4 партия 1: ~130 строк кода по смете, docs/plan-n4.md «Смета»). После партии —
   перезапуск MCP.
2. **Реакция тренера** — тексты по Р5, план дня по Р6. На выходе (Р5 = 3, Р6 = 1): утро с `illness_risk` — в сводке одна
   фраза с цифрами, вопрос о симптомах, предложение снять интенсивное на 2–3 дня (черновики — после «да»), совет сна и
   отдыха; «разложи день» — фокус-блоков на один меньше, причина в `skipped`; обычное утро — как раньше. Объём: ~1,1 КБ
   текста, ~15 строк кода, ~60 строк тестов (ожидание, не проверено). Перезапуск MCP при Р6 = 1.

## Тесты (кабан-доеба)

Партия 1 — `tests/test_load_illness.py` (чистые функции; строка — `{"date", "rhr", "hrv"}`, `TODAY = date(2026, 11, 2)`):

- `corridor`: 28 дней по пульсу 50 и один день 60 внутри базы → `mean7` по 7 предыдущим, `swc = 0.5 × pstdev` базы;
  13 дней в базе → None; 7 дней есть, но в центре 3 (пропуски) → None; `TODAY` в центр и базу не входит (значение `TODAY`
  = 90 не сдвигает `mean7`); строки с `None` не считаются.
- `day_flags`: `rhr` на границе (`== rhr_high_from`) → `rhr_high False` (строго больше); выше → True; `hrv` ниже
  `hrv_low_from` → `hrv_low True`; `out` по Р1 (при 1: оба True → True, один → False); значение None → все None.
- `out_streak`: флаги `… F T T` → 2; `… T F T` → 1; сегодня None → 0; сегодня True, вчера None → 1.
- `illness_signals`: `streak 2` → `illness_risk` (value 2, limit `STREAK_DAYS`); `streak 1` → `[]` (при Р2 = 2 —
  `illness_watch`); `streak 5` → один сигнал, value 5.
- `illness_report(conn, day, tss, sleep)`: база 28 дней (`upsert_daily_metrics` с `hrv_last_night` и `raw_json = {"sleep":
  {"restingHeartRate": N}}`, как `tests/test_mcp_read.py:163`) → поля по формулам, `days` ровно `SHOWN_DAYS` строк по
  возрастанию даты; два последних дня вне коридора → `streak 2`, сигнал; импортная строка (`raw_json = {"hrv": {"metrics":
  [{"type": "HR", "value": 52}, {"type": "HRV", "value": 60}]}}`) читается как пульс 52; день без строки → `rhr None`,
  `out_today None`, `streak 0`, сигналов нет; `tss = {вчера: 30}` → `trained_yesterday` в `confounders`, `tss_yesterday 30`;
  `tss = {}` → `tss_yesterday None`; `sleep` с `short_night` → в `confounders`; с `sleep_debt` → `sleep_debt True`;
  `baseline_days` — сколько дней базы с данными; `raw_json` в ответе нет (`"SECRET"` не встречается в `json.dumps`).

`tests/test_store_garmin_data.py`: `list_recovery_days` — три ключа `date`, `hrv`, `rhr`, по возрастанию, включительно; `rhr`
из `$.sleep.restingHeartRate`; при его отсутствии — из `$.hrv.metrics[type = HR].value`; оба есть — API-путь главнее; ни
того ни другого → None; `raw_json` в строках нет.

`tests/test_mcp_illness.py` (образец `tests/test_mcp_overload.py`, `mcp_fakes.call`): `get_illness` в `tool_names`; пустая база
→ коридоры None, `streak 0`, `signals []`, `baseline_days 0`; 30 дней → числа как у `illness_report`; нет пульса покоя для
`load` → `load_error` в ответе и отчёт без `tss_yesterday`; плохая дата → `ToolError`; snapshot содержит `illness` без
ключа `days` с остальными ключами; `test_snapshot_has_all_sections`, `test_snapshot_fits_total_limit`,
`test_snapshot_has_no_raw_json` зелёные.

Тексты партии 1: `coach.md` содержит `mcp__ai-coach__get_illness` и ≤ 16 384 Б (тесты лимита как есть); `test_mcp_no_push`:
`tool_names == EXPECTED_TOOLS` с `get_illness`; справка — раздел «Справка».

Партия 2 (при Р5 = 3): `coach-wellbeing.md` содержит `illness_risk`, `rhr_high_from`, `hrv_low_from`, `streak`, `confounders`,
«снять интенсивное» (или формулировка кабана — доеба согласует), ≤ 9 216 Б (три файла тестов); `coach.md:18` содержит
`illness.signals`; `recalc.md` содержит `illness_risk`, ≤ 3 072 Б; `recovery.md` содержит `illness`, ≤ 3 072 Б. При Р5 = 2
ещё: `get_deviations` при `streak 2` → kind `illness`; `test_wellbeing_topic_deviation_thresholds_match_deviations`. При
Р6 = 1 (`tests/test_agenda_day_plan.py`, `tests/test_mcp_day_plan.py`): `create_day_plan` на сегодня при `illness_risk` (28 дней
базы, два последних дня вне коридора, сон в норме) → 2 фокус-блока, предел 19:00 (не `caution_from`), в `skipped` строка
«возможно, заболеваешь»; на завтра при `illness_risk` → тоже 2 блока; `short_night` и `illness_risk` вместе → 2 блока (не
один), причина по первому сигналу (сон); без сигналов → 3 блока; `coach-day.md` содержит `illness_risk`, ≤ 6 144 Б;
`test_response_shape` зелёный.

Проверка руками (Влад): после партии 1 и перезапуска MCP — `тренер` → «как пульс и HRV?» / «не заболеваю ли?» → тренер
читает `illness` из сводки или `get_illness` и называет пульс, HRV, коридор, дней подряд; «что значит коридор?» → ответ
по `sleep.md`. После партии 2: утро с двумя днями вне коридора — в сводке одна фраза с цифрами, вопрос о самочувствии,
предложение облегчить ближайшие тренировки (черновики — после «да»), совет лечь раньше; «разложи день» → два
фокус-блока и причина в `skipped`; обычное утро — сводка как раньше, три блока.

Для mutmut (`модуль:функция` — TESTS по `grep -l`): `load.illness:corridor`, `load.illness:day_flags`, `load.illness:out_streak`,
`load.illness:illness_signals`, `load.illness:illness_report` (новые) — `tests/test_load_illness.py`, `tests/test_mcp_illness.py`;
`store.garmin_data:list_recovery_days` (новая) — `tests/test_store_garmin_data.py`, `tests/test_mcp_illness.py`;
`mcp_server.illness:illness` (новая) — `tests/test_mcp_illness.py`; `mcp_server.snapshot:morning_snapshot` —
`tests/test_mcp_snapshot.py`, `tests/test_mcp_overload.py`, `tests/test_mcp_sleep.py`, `tests/test_mcp_illness.py` (24 файла
по `grep -l morning_snapshot tests/` на HEAD + новый); при Р5 = 2 `mcp_server.tools:day_deviations` — `tests/test_mcp_read.py`,
`tests/test_mcp_snapshot.py` (по `grep -l deviations tests/` — уточнит доеба); при Р6 = 1 `agenda.sleep_limits:sleep_limits`,
`agenda.sleep_limits:_sleep_reason` — `tests/test_agenda_day_plan.py`, `tests/test_mcp_day_plan.py` (`grep -l 'sleep_limits\|create_day_plan'
tests/` — 4 файла, из них `test_skills_day.py` и `test_mcp_no_push.py` текстовые). Каталоги — `make mutate` по правилу проекта
(фоном вне агента, `Makefile:5`: новый файл в `MOD` только после `git add`); время — как в Н4 (~17 мин `make check` + mutmut,
docs/plan-n4.md «Итог»).

## Развилки и риски

Видимое Владу — развилки, решает Влад. Первая — блокирующая для партии 1.

- **Р1. Что считать днём вне коридора.** (1) Оба: пульс покоя выше `mean7 + SWC` и HRV ниже `mean7 − SWC` (так в BACKLOG 24:
  «пульс выше и HRV ниже»). На живой базе за 90 дней — 20 таких дней, 4 эпизода по 2+ дня. (2) Любой из двух — 38 дней,
  12 эпизодов: каждую неделю «возможно, заболеваешь». (3) Только HRV, через готовый `hrv_status` Garmin (LOW/UNBALANCED/BELOW
  2 дня подряд) — без своего коридора, но 25 плохих дней из 90 и пульса покоя в нём нет; к тому же `hrv` уже отклонение в
  `find_deviations`. Рекомендую (1): под формулировку беклога, срабатываний — порядок квартала; флаги `rhr_high` и `hrv_low`
  видны по отдельности в отчёте, тренер может назвать «пульс выше, HRV в норме» словами. Разблокирует партию 1.
- **Р2. Сколько дней подряд и один ли уровень.** (1) Сигнал `illness_risk` при 2 днях подряд; один день — только `out_today`
  и `streak 1` в отчёте, тренер молчит. (2) Два уровня: `illness_watch` при 1 дне (одна фраза без действий), `illness_risk`
  при 2 (реакция по Р5). (3) Сигнал уже при 1 дне — 20 фраз за квартал против 4. Рекомендую (1): 1 день — шум (CV HRV
  день к дню велик), r1:164 предлагал «требовать 2 дня» как ответ на ложные; при болезни «за 1–2 дня до симптомов» второй
  день — ещё до симптомов. (2) — если Влад хочет слышать и первый день.
- **Р3. Роль сна («с учётом сна»).** (1) Контекст: `short_night` этой ночи — в `confounders` (недосып сам снижает HRV и
  поднимает пульс), `sleep_debt` — поле «риск выше» (Prather 2015: сон < 6 ч — простуда ×4); сигнал от сна не меняется,
  тренер называет словами. (2) Короткая ночь гасит: день с `short_night` не считается днём вне коридора — сигнал только на
  «чистых» ночах; пропустим болезнь, начавшуюся вместе с недосыпом. (3) Долг усиливает: при `sleep_debt` хватает 1 дня вне
  коридора (`STREAK_DAYS − 1`). Рекомендую (1): наблюдение не теряет срабатываний, а сверка с самочувствием (К3) покажет,
  нужно ли (2) или (3) — тогда это смена константы/условия в v2.9. Разблокирует формулы партии 1.
- **Р4. Тяжёлая тренировка накануне (r1:153).** (1) Контекст: `trained_yesterday` в `confounders` при `tss_yesterday > 0`,
  цифра TSS рядом; порога «тяжёлой» нет — на живой базе TSS ≥ 50 за 60 дней не было ни разу (силовые по пульсу дают мало),
  абсолютная константа не сработает. (2) Гасит: день после тренировки не считается. (3) Не учитывать. Рекомендую (1):
  тренер видит «вчера тренировка, TSS N» и говорит «возможно, от неё»; алкоголь и перелёт данных не имеют — Влад скажет
  словами, тренер спросит (текст партии 2). Разблокирует партию 1.
- **Р5. Что делает тренер при `illness_risk` (r1:149–151: «наблюдение» против «действует»).** (1) Чистое наблюдение 2 недели:
  `illness` в snapshot и `get_illness` по просьбе, строка в `coach.md` «без вопроса не озвучивай»; в К-точку — решить про
  реакцию. (2) Действует: `illness` — отклонение в `get_deviations` → `recalc.md` пересчитывает план автоматически (как
  readiness < 33), плюс совет сна и отдыха. (3) Фраза и предложение: в сводке одна фраза с цифрами и вопрос о симптомах;
  предложение снять интенсивное из черновиков на 2–3 дня (после «да» — `recalc.md`, утверждённые — снять самому на часах);
  совет сна и отдыха (практика `sleep`); `find_deviations` не трогаем. Рекомендую (3): это стиль `coach-wellbeing.md:17`
  (сигнал перегруза → предложить снизить объём → после «да»); черновики всё равно утверждает Влад — риск мал; срабатывания
  видны и сверяются с самочувствием (К3), то есть наблюдение сохраняется; (2) делает автоматом то, что при 4 эпизодах за
  квартал и неизвестной доле ложных лучше спрашивать; (1) оставляет «болеть по минимуму» без единого действия до К1.
  Разблокирует тексты партии 2.
- **Р6. План дня при сигнале (r1:185 «сигнал болезни → лёгкий день»).** (1) В этом шаге: `create_day_plan` на сегодня и
  завтра при `illness_risk` — фокус-блоков на один меньше (как при сигнале сна; предел `caution_from` только от сна), причина
  в `skipped`; тренировка плана дня не трогается (её снимает Р5 через черновики). (2) Без кода: `coach-day.md` — при сигнале
  предложить меньше задач и `day_start` позже. (3) Отложить до v2.9 пунктом беклога. Рекомендую (1): r1 запланировал это
  партией Н11; ~15 строк в готовом `sleep_limits`; при Р5 = 1 — (3), чтобы наблюдение было чистым. Разблокирует код партии 2.

Риски:

- Snapshot 19 813 / 20 000 Б на живой базе: любой новый ключ запускает обрезку списков (`snapshot.py:210`), пострадает
  самый длинный (`wellbeing` за 30 дней или `metrics`) — молча, с `truncated`. `illness` без `days` ~250 Б (оценка по длине
  ключей, не прогон). Поднимать `MAX_CHARS` — не этот шаг (кандидат беклога).
- Строка сегодняшнего дня без ночи (sync до того, как часы отдали сон): `rhr`/`hrv None` → `out_today None`, `streak 0`,
  сигнала нет даже если вчера и позавчера были вне коридора (умолчание 5). Тренер скажет «ночи ещё нет». Альтернатива —
  считать `streak` от последнего дня с данными — если Влад заметит пропуски, пункт беклога.
- Стык импорт/API 2026-10-01: отношение средних пульса 1,10 — база 28 дней уже чистая, но `get_illness` на даты до
  2026-10-28 считает по смешанной базе (история, не сегодня). Для Н6/Н9 — в беклог («Побочные находки» 2, 4).
- Двойное срабатывание с Garmin: `hrv` LOW/UNBALANCED в `get_deviations` и `illness_risk` в один день → тренер по п. 5
  `coach.md` пойдёт в `recalc.md` по отклонению, а по Р5 = 3 ещё предложит снять интенсивное — текст `coach-wellbeing.md`
  велит «одна фраза, не две»; при Р5 = 2 это один путь.
- Режим наблюдения (Р5 = 1) без строки в `coach.md`: тренер видит `illness.signals` в snapshot и может среагировать сам (как
  риск Н1 партии 3) — поэтому строка «без вопроса не озвучивай» в партии 1 при Р5 = 1.
- Пороги — догадка: `SWC_K 0.5`, `STREAK_DAYS 2`, база 28 — калибрует v2.9 вместе с `TOTAL_HIGH` и порогами `load/sleep.py`
  (ROADMAP:84). Замер на 90 днях — на одном человеке и без сверки с болезнями; К3 — сверка (r1:164).
- `pstdev` против `stdev`: при 14 значениях разница ~4 % ширины коридора; берём `pstdev` (население = база), умолчание 2.
- Лимиты текстов: `coach-wellbeing.md` 8 192 → 9 216 в трёх файлах (ROADMAP:82 записал долгом Н12 — забираем, строку Н12 правит
  архитектор при закрытии); `coach.md` остаётся в 16 384 (15 554 + ~170 = ~15 720, ожидание — кабан меряет `wc -c`).
- Smells: `tools.py` файл 40 при пороге 50 (`qlty metrics`, 2026-11-01) — поэтому инструмент в своём модуле
  `mcp_server/illness.py` (прецедент `overload.py`); `sleep_limits.py` 6 — +ветка и вызов ≈ +3, порог функции 15 (`qlty.toml:62`).
  `illness_report` собирает ~16 ключей — держать под порогом qlty; при росте — вынос `_corridors(rows, day)`.
- Н12 (WHO-5) захочет `coach-wellbeing.md` — после Н11 запас в 9 216 ≈ 250 Б: Н12 поднимет до 10 240 — в его план.

## Умолчания (внутреннее)

1. База коридора `BASELINE_DAYS = 28` (не 60): по замеру то же число срабатываний, а стык источников 2026-10-01 не
   захватывается; центр `CENTER_DAYS = 7` (BACKLOG 24, Plews); минимум `MIN_BASELINE_DAYS = 14`, `MIN_CENTER_DAYS = 4`
   (Plews et al.: 3–4 дня из 7 эквивалентны недельному среднему).
2. HRV — в мс как есть, без логарифма (замер: 19 против 20 дней); SD — `statistics.pstdev`; SWC = `SWC_K × SD`,
   `SWC_K = 0.5` (Plews/AIS: «smallest worthwhile change» = 0,5 SD — в источниках дяди не проверено первоисточником; на
   нашей базе k = 1 даёт ноль эпизодов).
3. Сегодняшний день в центр и базу не входит (иначе выброс тянет среднее к себе); округление: `mean7`, `*_from` — один знак;
   `rhr`, `hrv` — как в базе (целые).
4. Пульс покоя читается `json_extract` из `raw_json` двумя путями (API `$.sleep.restingHeartRate`, импорт
   `$.hrv.metrics[type=HR].value`), колонка и миграция не добавляются (как подъём в Н4, умолчание 4 там). `last_rest_hr` не
   трогаем (беклог).
5. `streak` считается с `day` назад, день без данных или в коридоре прерывает; данных сегодня нет — `streak 0`.
6. Имена: модуль `load/illness.py`, инструмент `get_illness`, ключ snapshot `illness`, kind `illness_risk` (при Р2 = 2 —
   `illness_watch`); формат сигнала `{"kind", "value", "limit"}` как у `sleep_signals`; ключи отчёта — как в «Модулях».
7. В snapshot `illness` — без `days` (размер); `NOT_LISTS` + `"illness"`; `DATE_SERIES` не меняется; `sleep_report` в snapshot
   считается один раз и передаётся в `illness_report`.
8. `confounders` — список строк из фиксированного набора `("short_night", "trained_yesterday")`; `sleep_debt` — отдельный bool
   (не confounder — усиливает, а не объясняет); `tss_yesterday` — число или None.
9. Справка — раздел в `coach-help/sleep.md` (заголовок файла и строка оглавления шире), не новый файл: allow-строка Влада
   не нужна; `wellbeing.md` оставлен Н12 (plan-n2 «Риски»).
10. MCP-инструмент в `mcp_server/illness.py` (размер `tools.py`), TSS — через `load()` как в `overload.py`; `load_error`
    в ответе при отсутствии пульса покоя для TSS.
11. При Р6 = 1 — поправка внутри `agenda/sleep_limits.py:sleep_limits` (имя модуля не меняем — 9 ссылок в тестах), предел
    `caution_from` только от сигналов сна, при двух сигналах блоков `focus_max − 1` (не минус два), причина по первому —
    порядок: сон, затем болезнь (как Р8 Н4).
12. Коммит после каждой партии; `docs/pipeline.md` — строка на партию (оркестратор); ROADMAP (строка Н11 ✅, правка строки
    Н12 про лимит), карточка 024 и handoff — после аппрува и закрытия.

## Открытые вопросы

Нет: все развилки — Р1–Р6, первая блокирующая. Вне плана: сколько раз Влад болел за последние 90 дней — пригодится для
сверки 4 эпизодов (К3), не блокирует.

## Побочные находки (для беклога, не этот шаг)

1. `find_deviations` `BAD_HRV_STATUSES = ("LOW", "UNBALANCED")` не знает статусов импорта (IN_RANGE/BELOW/ABOVE): у
   импортных строк до 2026-09-30 плохой HRV (BELOW — 19 строк) отклонением не считается. История, не сегодня.
2. `store/garmin_data.py:116 last_rest_hr` читает только `$.sleep.restingHeartRate` (API): для дат до 2026-10-01 `get_load`
   отвечает «нет свежего пульса покоя» (`REST_HR_MAX_AGE_DAYS 14`), хотя пульс есть в `$.hrv.metrics[type=HR]`. Мешает
   анализу истории (Н6, Н9).
3. Snapshot 19 813 / 20 000 Б на живой базе: каждый новый ключ молча режет списки; кандидаты — поднять `MAX_CHARS` или
   вынести редкие разделы (`recipes`, `pantry`) из сводки.
4. Пульс покоя импорта (метрика HR экспорта) и API (`restingHeartRate` сна) — средние за сентябрь/октябрь расходятся на 10 %:
   возможно, разные определения. Для Н6/Н9 при чтении истории — проверить на перекрытии (его нет: импорт до 09-30, API с 10-01).
5. `export_days.add_hrv` не пишет `hrv_weekly_avg` и `hrv_status` импорта — другой словарь статусов (п. 1); Garmin-коридор
   (`hrvSummary.baseline`, `baselineLowerLimit/UpperLimit`) не хранится в колонках — источник для сверки своего коридора в v2.9.
6. `tests/`: лимит `coach-wellbeing.md` в трёх файлах, `coach.md` — в 11 (Н4 умолчание 8): одна константа лимитов в общем
   модуле тестов — оптимизация.

## Правки по ревью

Партия 1 — трактовки кабана, которых план не задавал (папа, п1, 2026-11-01; код смотрит мама):

1. Округление (умолчание 3). `corridor` без округления — принято. Правка: `day_flags` сравнивает с границей
   `round(mean7 ± swc, 1)` — той же, что отдаёт `_edges`, иначе флаг и показанная цифра расходятся на краю (rhr 52,
   граница 51,96 → показано 52,0 и `rhr_high True`), а тест плана «`rhr == rhr_high_from` → `rhr_high False`» не
   гарантирован. Один helper `_edge(found, sign) -> float | None` для `day_flags` и `illness_report`; `*_mean7` —
   округление в отчёте, как сейчас.
2. `streak` ≤ `SHOWN_DAYS` (флаги только за 7 дней) — принято: при 8+ днях подряд число уже не информация, лишних строк
   не читаем; записать в docstring `illness_report` и в описание `get_illness` («streak — таких дней подряд, до 7»).
   Не развилка: видно только при неделе болезни.
   Правка (ошибка плана, «Модули»: чтение `day − BASELINE_DAYS`): у показанных дней база коридора укорочена (у `today − 6`
   — 22 дня, у вчера — 27), поэтому `days[].out` и `streak` могут не совпасть с `get_illness` на ту дату. Читать
   `list_recovery_days(conn, day − (BASELINE_DAYS + SHOWN_DAYS − 1), day)` — 34 дня, тот же запрос. Тест: `out` у
   `today − 6` в `days` равен `out_today` у `illness_report(conn, today − 6)` на той же базе.
3. `baseline_days` «rhr или hrv». Правка: считать дни, где есть оба — `out` требует обоих, и `baseline_days ≥
   MIN_BASELINE_DAYS` тогда гарантирует базу обоим коридорам; при «или» тренер скажет «данных 20 дней», а `hrv_low_from`
   — null. В описание `get_illness` добавить «baseline_days — дней из 28 с пульсом и HRV» (~45 Б).
4. `tss_yesterday = tss.get(вчера)`, `trained_yesterday` при > 0 — принято (Р4): `daily_tss` даёт 0.0 на каждый день
   (`load/training.py:54`), None — только при `tss = {}` (`load_error` или вызов без нагрузки).
5. Строка «наблюдение» в `coach.md` при Р5 = 3 не нужна — принято. Окно между п1 и п2 (тренер сам реагирует на
   `illness.signals`): п2 — следующая партия этого шага, проверка п1 руками идёт вопросом («как пульс и HRV?»), не
   сводкой; временную строку не ставим (две правки текста и тестов туда-обратно). Если п2 отложится дольше суток —
   оркестратору добавить в п. 2 `coach.md` «`illness` в snapshot - наблюдение: без вопроса не озвучивай» (~90 Б,
   сейчас 15 552 / 16 384).

Развилок для Влада нет.

Партия 1 — по ревью мамы (2026-11-01): `load/illness.py _context` — `sleep or sleep_report(...)` заменено на
`sleep if sleep is not None else sleep_report(conn, day)` (неблокирующее замечание мамы, решение кабана; пустой `{}`
больше не пересчитывается). Аудит свекрови п1: код по плану; приоритеты BACKLOG 29–34 поставил оркестратор без
Влада — окно Владу (варианты у папы). Влад, 2026-11-01: вариант (2) папы — 31 medium (закрыть внутри Н12),
30 и 32 medium (вход Н6/Н9), 29, 33, 34 low; priority в BACKLOG и строку долга в Н12 правит архитектор. Влад, 2026-11-01: mutmut по п1 пропустить —
мутанты п1 не сняты. make check после правки зелёный (3844 passed).

Партия 2 — трактовки кабана (папа, п2, 2026-11-01; дерево поверх e93b455, `git diff` 8 файлов):

1. `coach-wellbeing.md` 9 200 / 9 216 Б (`wc -c`). «Практика `sleep`» убрана из абзаца «Возможно, заболеваешь» — принято:
   она в абзаце «Сон» того же файла, тренер читает файл целиком. Правка: вместе с ней выпало «не добирать нагрузку»
   (план, «Модули», п2: «совет сна и отдыха: лечь раньше, практика `sleep`, не добирать нагрузку») — это совет тренера,
   видимый Владу, а не стиль; вернуть («Совет: лечь раньше, нагрузку не добирать.»), байты взять внутри абзаца (например,
   «(интервалы, тяжёлая силовая - на лёгкое)» → «(интервалы, тяжёлая силовая)»), лимит 9 216 не поднимать. Для Н12: запас
   файла после Н11 ≈ 16 Б, не ~250 как в «Рисках»; подъём до 10 240 — в план Н12, как и записано.
2. `agenda/sleep_limits.py` — по умолчанию 11 без расхождений: `focus_max − 1` при любом наборе сигналов, предел
   `caution_from` только при сигналах сна (`if sleep_signals and day == today …`), причина по первому (сон, затем болезнь),
   `illness_report(conn, today, {}, report)` с `tss = {}` (TSS плану дня не нужен — `trained_yesterday` в причину не входит;
   так же план задавал в «Модулях»). Принято. Тест на мутант `sleep_signals and` — доебе (п. 3).
3. Ожидание предела в тесте плана дня по `focus_until` (`FOCUS_UNTIL = EVENING_FROM`, `day_plan.py:69`), а не «19:00» —
   принято: «19:00» в плане — значение константы, не отдельное требование. Чтобы тест ловил мутант `sleep_signals and`:
   ночь нормальная (7 ч) с подъёмом «02:00» (`caution_from` 18:00 есть, сигналов сна нет) + `illness_risk` → `until ==
   focus_until` (не 18:00), блоков `FOCUS_MAX − 1`, причина «возможно, заболеваешь»; образец — `test_caution_at_1800_*`
   (`tests/test_agenda_day_plan.py:881`). Тесты п2 в дереве пока нет (`grep -rl illness tests/` — только файлы п1;
   `test_skills_workload.py:10` всё ещё 8 192 → сейчас красный): порядок family.md — доеба до кабана.
4. `docs/architecture.md:246` «`find_deviations` и план не меняются» и `README.md:69` «Пока только показ цифр» — правка
   (устарели с п2, план «Справка»: architecture и README — в том же шаге). architecture, раздел Н11: `:246` → «`find_deviations`
   и план тренировок не меняются: интенсивное снимается черновиками после «да» (`recalc.md`)»; новая строка по образцу
   Н4 (`:241`): «`agenda/sleep_limits.py`: `illness_risk` на сегодня и завтра — фокус-блоков на один меньше, предел
   `caution_from` только от сна, при двух сигналах — минус один, причина по первому (сон, затем болезнь)». README:69 «Пока
   только показ цифр;» → «При сигнале тренер называет цифры, спрашивает о симптомах, предлагает на 2–3 дня снять
   интенсивное (черновики — после «да») и лечь раньше; «разложи день» ставит фокус-блоков на один меньше;».
5. Остальные тексты — по плану, лимиты (`wc -c`): `coach.md` 15 814 / 16 384, `coach-day.md` 5 415 / 6 144, `recalc.md`
   1 765 / 3 072, `recovery.md` 1 491 / 3 072, `coach-help/sleep.md` 4 791 / 8 192 («Что делает тренер» — по Р5/Р6, принято).

Развилок для Влада нет.

Партия 2 — по ревью мамы. Аудит свекрови п2 чистый.
1. `coach-wellbeing.md`, абзац «Возможно, заболеваешь»: «снять самому» перевернуло смысл (снимает будто тренер) →
   «утверждённые и отправленные - пусть снимет сам», 9 209 / 9 216 Б (кабан, по совету мамы).
2. `test_illness_today_gives_two_focus_blocks_with_reason`: «T19:00» → `FOCUS_UNTIL`, как в п. 3 выше (доеба).

Мутанты партии 2 (mutmut `agenda/sleep_limits.py`: убито 110, выжило 6) — доеба тестов не добавил, папа сверил по коду
(2026-11-01), все шесть эквивалентны: 13, 16 — `now` → None/нет в `sleep_report(conn, today, now)`: `now` влияет только на
`awake_h` (`load/sleep.py:92–105`), который `sleep_limits` не читает — те же мутанты приняты эквивалентными в Н4
(docs/plan-n4.md:508–511); 30 — `{}` → None в `illness_report(…, {}, report)`: в `_context` `(tss or {})`
(`load/illness.py:117`); 34 — `report` на месте `tss`: `report.get("<вчера>")` → None, `sleep=None` → `_context` сам зовёт
`sleep_report(conn, day)` (`:114`); 31, 35 — `report` → None/нет: тот же пересчёт внутри, разница — второй запрос 90 ночей,
не результат. Убить их можно только шпионом на аргументы вызова (тест проводки, не поведения). Окно Владу — варианты:
(1) принять как эквивалентные этой записью, повтор mutmut не нужен (тестов нет), п2 идёт на коммит — рекомендую: поведение
и тесты не меняются, прецедент Н4; (2) кабан убирает «лишние» аргументы — `{}` (гасит только 30 и 34; `sleep=None` и снятие
kwarg останутся эквивалентами 31/35), `report` (гасит 31/35 ценой второго запроса `list_sleep_nights`, против замысла
`illness_report`: «sleep — готовый отчёт», и образца `snapshot.py:187–188`), `now` из сигнатуры `sleep_limits` (правка
`day_plan.py:301` и 7 прямых вызовов `tests/test_agenda_day_plan.py:997–1053`, против решения Н4) — поведение то же, но
новый круг ревью, аудита и mutmut (Н4 п2: три прогона, docs/plan-n4.md «Итог»); (3) `# pragma: no mutate` на строках 43 и 45
— новая для репо конвенция (grep `pragma` по `src/` — пусто), комментарий в коде ради метрики. Решение Влада — ниже.
Решение Влада (2026-11-01, окно): (1) — 6 мутантов приняты эквивалентными, повтор mutmut не нужен.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план Н11 («Суть», «Модули», «Партии», «Тесты», «Развилки и риски»); сценарий — Р1–Р6 по рекомендациям
(Р5 = 3, Р6 = 1), две партии, Декарт по умолчанию зовут. Цены — тариф metrics.py от 2026-10-25 (страницу pricing не сверял),
fable — по ценам Opus. Масштаб по «Модулям/файлам»: п1 ~120 строк кода (illness.py ~85, store ~15, MCP ~20), ~220 строк
тестов — против ~130 / ~230 у Н4 п1; п2 ~15 строк кода, ~1,1 КБ текста, ~60 строк тестов — против ~25 строк у Н4 п2 (в Н4 п2
вылезла по smells и mutmut). Опора — «Итог» Н4 (docs/plan-n4.md:571: 197 мин, 44,2M, $25,54 без Декарта при смете $15,0–24,2;
оркестратор $8,36, 189 вызовов, 19 окон, 3 /compact). Объём чуть меньше Н4, но стык источников пульса, три файла лимита и
snapshot 19 813 / 20 000 Б — те же риски дрейфа; верхнюю границу держу ближе к факту Н4. Подписок, хостинга, БД и внешних API
шаг не добавляет (Garmin — новых запросов нет): платное — токены LLM.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Токены конвейера Н11 | разово $15,8–27,1 без Декарта; $26,2–37,5 с ним | один шаг; в месяц — по числу шагов (Н4 $25,5) | не звать Декарта (как Н3, Н4, Н14) | ~$10,4 (3 × $3,47) | разбор конвейера по шагу; решает Влад |
| Оркестратор (opus) | $4,5–8,5 | 14–22M токенов; в Н4 21,4M, $8,36 | решения Р1–Р6 в плане (по рекомендациям) — окон меньше; /compact только по handoff | до ~$2 | ничего, порядок вопросов |
| Партия 2 отдельно | ~$5–8 из общей суммы | ~15 строк кода, ~1,1 КБ текста; свой круг ревью, аудита, mutmut | слить п2 в п1 (один круг ревью и аудита) | ~$2,5–4, ~20 мин | граница «наблюдение / реакция тренера» (откат отдельным коммитом); при Р5 = 1 и Р6 ≠ 1 п2 нет: ~$5–8 |
| Доеба, кабан (sonnet) | $1,3–2,2 | уже sonnet | haiku-5-5 (тариф $0,10/$0,50) | ~$0,7 | качество красных тестов (догадка) — не рекомендую |
| Папа (fable по Opus), доработки плана | прошло $2,54 + $1,5–4,0 | 1–3 запуска по ревью, отступлениям, ROADMAP | мелкие замечания — правкой оркестратора, без запуска папы | ~$1–2 | план может расползтись; решает оркестратор |
| mutmut | $0 токенов | фоном вне агента, локально | — | — | — |

Ревью и аудит (мама, свекровь) не трогаю; слабую модель им и оркестратору не предлагаю.

| Партия | Время |
|---|---|
| План (папа) | уже прошло: 17,5 мин (metrics.py, a9f1c69d45063b8af, 08:53–09:11 UTC) |
| 1. Коридор, MCP, snapshot, справка | ~40–60 мин (Н4 п1 ~45 мин работы + make check/mutmut ~17 мин; код чуть меньше) |
| 2. Реакция тренера (Р5 = 3, Р6 = 1) | ~15–25 мин (Н4 п2 вылезла: smells, три mutmut — закладываю риск) |
| Декарт (3 вызова) + тесть р.3 | ~10–15 мин |
| Весь шаг (после плана) | ~65–100 мин (без п2 и Декарта: ~40–60); окна Влада и простой — вне |

Уже прошло: $2,54 (папа-кабан a9f1c69d45063b8af, metrics.py; id из agents.md) — нижняя граница сметы ≥ $2,54; тесть р.1
a5302cecb938455b3 и мой запуск не включены.

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| orchestrator | opus | 14–22M | 4,5–8,5 |
| papa-kaban (прошло $2,54; +1–3 запуска) | fable (по Opus) | 3,2–5M | 4,0–6,5 |
| kaban | sonnet | 2,8–5M | 1,6–2,6 |
| kaban-doeba | sonnet | 2,8–5M | 1,3–2,2 |
| mama-kaban | opus | 1,8–3,5M | 2,0–3,3 |
| kaban-svekrov | opus | 1,8–3,5M | 2,0–3,3 |
| kaban-test (р.1 sonnet, р.3 opus) | sonnet / opus | 0,3–0,6M | 0,35–0,7 |
| **итого без Декарта** | | 26,7–44,6M | **15,8–27,1** |
| kaban-dekart (3 вызова = 2 партии + 1 сводный) | fable (по Opus) | 3–4M × 3 (допущение) | 10,4 (3 × 3,47, последний факт Ш9, plan-sh9.md:241) |
| **итого с Декартом** | | 36–57M | **26,2–37,5** |

Модели (`grep -H '^model:' ~/.claude/agents/<роль>.md`): kaban-dekart.md:model: fable; kaban-doeba.md:model: sonnet;
kaban.md:model: sonnet; mama-kaban.md:model: opus; kaban-svekrov.md:model: opus; kaban-test.md:model: opus;
papa-kaban.md:model: fable. Мой запуск — sonnet-5-5, kaban-test.md просит opus: р.3 считаю по opus.

## Итог

**Источник токенов:** `python3 ~/projects/semia-kabanov/etalon/bin/metrics.py ~/.claude/projects/-Users-vladislavahtamov-projects-ai-coach/98b4be99-91b2-4b26-9d8f-3d8afa8afb7a.jsonl` (вся сессия — один шаг Н11, `--from` не нужен; старт 2026-11-01 08:52 UTC); **цены:** тариф metrics.py от 2026-10-25, https://platform.claude.com/docs/en/about-claude/pricing (страницу не сверял — «не проверено»); fable — по ценам Opus. Закрывает BACKLOG 24; коммиты e93b455 (п1), eb7356c (п2).

| Партия | Смета | Факт |
|---|---|---|
| План (папа) | прошло 17,5 мин | 17,5 мин (a9f1c69d45063b8af, 08:53–09:11 UTC) |
| 1. Коридор, MCP, snapshot, справка | 40–60 мин | ~27 мин работы: кабан 11,2 + доеба 4,5 + папа (трактовки, приоритеты) 4,9 + мама 1,3 + свекровь 1,6 + make check 3,5 (сумма сегментов старт/resume → хэнд-бэк); mutmut п1 пропущен по решению Влада — отсюда меньше сметы |
| 2. Реакция тренера (Р5 = 3, Р6 = 1) | 15–25 мин | ~42 мин работы: кабан 5,0 + доеба 6,4 + папа 3,3 + мама 1,3 + свекровь 1,7 + make check 11 (до правок) и 8 (после) + mutmut 1 + мутанты (доеба 0,5 + папа 3,3). Превышение — два прогона make check (19 мин вместо одного) и разбор 6 выживших мутантов; ревью и аудит вышли чистыми |
| Закрытие (архитектор) | не было в смете | 2,5 мин |
| Декарт (3 вызова) | 10–15 мин вместе с тестем | не звали (agents.md: вызовов нет), 0 мин |
| Весь шаг | 65–100 мин | 81 мин по metrics.py (08:52–10:52 UTC, до запуска тестя), из них «Ожидание» 38,9 мин: вопросы и просьбы текстом 23,5, /compact 1,9; 14 окон AskUserQuestion, отклонено 0 |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| orchestrator (на момент подсчёта 10:52 UTC; сессия идёт) | opus (claude-opus-5-5) | 13,22M (133 вызова) | 5,41 |
| papa-kaban (6 запусков: план, трактовки п1, приоритеты, трактовки п2, мутанты, архитектор) | fable (по Opus) | 4,00M | 4,83 |
| kaban | sonnet | 4,35M | 1,88 |
| kaban-doeba (2 запуска: тесты, мутанты) | sonnet | 3,11M | 1,40 |
| mama-kaban | opus | 1,23M | 1,27 |
| kaban-svekrov | opus | 1,77M | 1,36 |
| kaban-test (р.1 и р.3 — оба запуска sonnet-5-5, kaban-test.md просит opus; р.3 на момент подсчёта, неполный) | sonnet | 0,43M | 0,35 |
| kaban-dekart | fable (по Opus) | не звали | 0 |
| **итого** | | 28,12M | **16,51** |

**Итого:** смета $15,8–27,1 без Декарта (26,2–37,5 с ним), 26,7–44,6M токенов, 65–100 мин → факт $16,51 (нижняя граница сметы; «уже прошло» $2,54 папы входит), 28,1M токенов, 81 мин. По ролям ниже сметы мама ($1,27 против 2,0–3,3) и свекровь ($1,36 против 2,0–3,3): по одному запуску, ревью п1 и п2 с одной правкой каждое; выше сметы нет никого. Время: п1 быстрее (mutmut пропущен), п2 дольше (два make check, мутанты); в целом укладываемся — Декарт не звали, п1 и п2 короче по ожиданию.
Churn после ревью: код +55/−39, тесты +198/−31 (30 % от строк до T0)
Разбор — кабан Декарта.
