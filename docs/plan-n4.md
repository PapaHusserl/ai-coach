# Шаг Н4. Долг сна и время бодрствования

Закрывает BACKLOG 18. План — папа-кабан, 2026-11-01, режим «встроить». Разведка на HEAD aba17d4. Основание —
docs/research-brain.md п. 16 (Borbély, Van Dongen 2003: 14 ночей по 6 ч ≈ 1–2 ночи без сна, субъективная сонливость этого
не видит; провалы внимания растут сверх ~15,8 ч бодрствования), «Топ-5» п. 1. Место в очереди — docs/plan-roadmap-r1.md:37
(после Н1 — поправка «время от подъёма» к дневным оценкам), :145 (Н4 → Н11: долг сна для сигнала болезни), :185 (Н4 после
выхода добавляет правило в план дня Н13 — партия этого плана, не отдельный шаг). Решение Влада — NOTES.md 2026-10-31:
текущее поведение тренера не трогать, новые фичи стартуют в режиме наблюдения. Живая база — только чтение (`?mode=ro`);
в документе — счётчики без личных цифр (репо публичное).

## Суть

Три куска из BACKLOG 18, всё — на данных Garmin, которые уже лежат в `daily_metrics`:

- **Долг сна.** Личная норма — медиана ночей за 90 дней (Р1); долг — сумма (норма − сон) за 7 и за 14 ночей (Р2);
  короткая ночь — ночь короче нормы на порог (Р3). Пороги — константы нового модуля `load/sleep.py`, «догадка, калибруется
  в v2.9», как `TOTAL_HIGH` в `load/overload.py:28`.
- **Время от подъёма.** Подъём — `sleepEndTimestampLocal` из сырого ответа сна в `raw_json` (API-строки, с 2026-10-01);
  `awake_h` у каждой дневной оценки `focus_log` (Н1) считается при чтении в `get_focus_log`; в snapshot `sleep.awake_h` —
  часов от подъёма «сейчас». Тренер сам не считает (`coach.md:8`) — цифры даёт код.
- **Сигнал тренеру.** `short_night`, `sleep_debt` и `caution_from` (подъём + 16 ч) в snapshot `sleep` и `get_sleep(date)`;
  правило словами в `coach-wellbeing.md`: после недосыпа «чувствую себя нормально» — не восстановление, тяжёлые решения
  после `caution_from` не планировать (Р4); план дня при сигнале — фокус-блоков меньше и не позже `caution_from` (Р5).
  План тренировок и `find_deviations` не трогаем.

Что есть по коду (как встраиваем):

- **Данные.** `daily_metrics` (0001): `sleep_seconds`, `sleep_score`, `raw_json` — весь ответ Garmin. `sync/garmin_sync.py:76
  day_metrics` берёт `sleepTimeSeconds` из `$.sleep.dailySleepDTO`; `sync/export_days.py:24 add_sleep` (zip-импорт) — сумму
  фаз, в `raw.sleep` кладёт элемент экспорта. Живая база: 560 дней (2025-01-16…2026-10-31), ночей с `sleep_seconds > 0` —
  407, с нулём/NULL — 153 (в импорте `sleepWindowConfirmationType = OFF_WRIST` — 145 строк: ноль здесь — «часов не было»,
  не «не спал»). API-строк (`dailySleepDTO`) — 32, с `sleepEndTimestampLocal` — 31 (2026-10-01…10-31); импортные строки
  несут только `sleepEndTimestampGMT` строкой. За последние 90 дней ночей с данными — 90. `sleepEndTimestampLocal` — мс
  epoch, сдвинутые на пояс: `datetime(x/1000, 'unixepoch')` в SQLite даёт местное время стены (проверено: у 31 из 31 строк
  дата совпадает с `date`). Garmin ещё отдаёт `sleepNeed.baseline/actual` (минуты, только API-строки) — вариант Р1 (3).
- **Чтение из raw_json.** Образец — `store/garmin_data.py:100 last_rest_hr`: `json_extract(raw_json, '$.sleep.…')` в SQL, без
  разбора JSON в Python. Так же читаем подъём. API-строка `raw_json` — ~177 КБ (среднее по 32), поэтому `list_daily_metrics`
  (`SELECT *`) за 90 дней не годится — нужна выборка только трёх колонок (`date`, `sleep_seconds`, подъём); `json_extract`
  по 93 строкам — 31 мс (замер на живой базе).
- **Правила и сигналы.** `load/deviations.py:11 SLEEP_MIN_HOURS = 6`, `:47-51` — отклонение `sleep` (остаётся как есть,
  Р4). `load/overload.py:94 _recovery_drop` — образец «окно последних дней против базы», `:168 overload_report(conn, day,
  tss)` — образец отчёта для MCP и snapshot (`mcp_server/overload.py:14`, `snapshot.py:184`, `NOT_LISTS` `:65`).
- **MCP.** `tools.py:177 focus_log` — куда ложится `awake_h`; `tools.py:283 now()`, `:287 today()` — подменяемые часы
  (тесты `test_mcp_day_plan.py:22`). Новый инструмент: `server.py:49 TOOLS`, `coach.md:5 tools:` (аудит Н1 п1),
  `tests/test_mcp_no_push.py:33 EXPECTED_TOOLS` (35 имён), `test_skills_help.py:300 test_every_mcp_tool_is_in_help`.
- **План дня (Н13).** `agenda/day_plan.py:151 _Layout.focus` — `FOCUS_UNTIL` (`:68`, = 19:00) и `FOCUS_MAX` (`:67`, = 3);
  `:167 plan_day` (6 параметров, порог qlty 15), `:247 create_day_plan` (знает `now`, `day == today`).
- **Тексты.** `coach.md` 15 344 Б при лимите 15 360 (запас 16 Б — строка нового инструмента +26 Б не влезает, лимит в
  5 тестах: `test_skills_workload.py:90`, `test_skills_evening.py:83,132`, `test_skills_text.py:264`, `test_skills_day.py:29`);
  `coach-wellbeing.md` 6 898 / 7 168 (`test_skills_workload.py:10`, запас 270 Б); `coach-morning/recovery.md` 1 298 / 3 072;
  `coach-day.md` 5 034 / 6 144; справка `coach-help/wellbeing.md` 7 179 / 8 192 (запас 1 013 Б, который plan-n2 «Риски»
  отложил для Н12 WHO-5), `coach-help.md` 3 358 / 6 144. Новая тема справки — образец `coach-help/pvt.md` (Н2) + строка allow
  руками Влада (`settings.json:66`).

**Правило:** новое — долг сна, норма, короткая ночь, время от подъёма (`load/sleep.py`). Существующее `find_deviations`:
`sleep < SLEEP_MIN_HOURS * 3600` (`load/deviations.py:48`) — не меняется. При Р5 = 1: было `FOCUS_MAX = 3`, `limit =
datetime.combine(…, FOCUS_UNTIL)` (`day_plan.py:67-68, :153, :160`) → станет параметры `focus_max`, `focus_until` у
`plan_day`; при сигнале сна на сегодня — `FOCUS_MAX - 1` и `min(FOCUS_UNTIL, caution_from)`, на завтра — только `FOCUS_MAX - 1`
при `sleep_debt`.
**Поведение:** меняется — (1) новый MCP `get_sleep(date)`; (2) ключ `sleep` в `get_morning_snapshot`; (3) `awake_h` в строках
`get_focus_log`; (4) при Р4 = 1 — фраза в утренней сводке при сигнале и правило «не доверять „нормально“» (текст, план
тренировок не меняется); (5) при Р5 = 1 — план дня при сигнале ставит меньше фокус-блоков. Не меняется: `find_deviations`
(сон < 6 ч остаётся), `recalc.md`, `find_overload`, недельный обзор, `coach log focus`, `get_wellbeing`.
**Вне репо:** `.claude/settings.json` — строка allow `Bash(cat .claude/agents/coach-help/sleep.md)` руками Влада до `make
check` партии 1 (среда запрещает агентам, прецедент Н2; без неё `test_allow_has_every_topic_file` красный); MCP-сервер
перезапустить после партии 1 (новый инструмент) и после партии 2 при Р5 = 1 (описание `create_day_plan`). Garmin — новых
запросов нет, данные уже в `raw_json`. Новых зависимостей нет.

## Решения

Влад, 2026-11-01 (окна):

- Р1 — норма: медиана 90 ночей (рекомендация).
- Р2 — долг со знаком (рекомендация).
- Р3 — пороги 1 ч / 3 ч / 5 ч / 16 ч (рекомендация).
- Р4 — фраза с цифрами в сводке, правило «„нормально“ после недосыпа — не восстановление» (рекомендация).
- Р5 — план дня при сигнале в этом шаге (рекомендация).
- Р6 — `wake_at`/`caution_from` — полные дата и время `YYYY-MM-DD HH:MM`, не `HH:MM` (против рекомендации).
- Умолчание 2, дневной сон: учесть — папе на доработку (вопрос Влада «почему не считается»).
- Р7 — дневной сон гасит долг, не входит в норму и короткую ночь (рекомендация).
- Остальные умолчания приняты.

## Справка (правило AGENTS.md)

Новые функции: MCP `get_sleep`, поле `sleep` в сводке, `awake_h` в `get_focus_log`, при Р4 — фраза и правило тренера, при
Р5 — поправка плана дня. Правки:

- `.claude/agents/coach-help/sleep.md` — новая тема (образец `pvt.md`, 1 809 Б): «# Сон: долг и время бодрствования»;
  зачем одной строкой (недосып копится и сам себя не видит — тренер считает его по часам Garmin); карточка «## Долг сна -
  `get_sleep`»: что это (норма — медиана ваших ночей за 90 дней, нужно не меньше 20 ночей; долг — сколько часов не доспали
  против нормы за 7 и за 14 ночей, минус — выспались; короткая ночь — короче нормы на 1 ч и больше; `caution_from` — час,
  после которого тяжёлые решения лучше не ставить: 16 ч от подъёма), как запустить («как мой сон?», «долг сна» — тренер
  читает `sleep` из сводки или `get_sleep`; своей команды CLI нет, часы Garmin считают сами), что получу (норма, ночей в
  норме, последняя ночь, дневной сон за день `nap_h` (по Р7), долг за 7/14 ночей и сколько ночей учтено, подъём и
  `caution_from` — дата и время `ГГГГ-ММ-ДД ЧЧ:ММ` (Р6; `caution_from` может быть уже следующей датой), часов от подъёма,
  сигналы `short_night` / `sleep_debt`; ночь без часов не считается — не ноль), «время от подъёма» у дневных оценок
  (`get_focus_log`, поле `awake_h`); что делает тренер — по Р4: (1) «после недосыпа ваше „нормально“ тренер не считает
  восстановлением и тяжёлые дела после `caution_from` не планирует; план тренировок по сну не меняет» / (2) «пока только
  копит». Пороги в тексте — те же константы `load/sleep.py` (тест-сверка ниже). Размер — кабан меряет `wc -c`, лимит 8 192.
- `.claude/agents/coach-help.md:15-16` — строка оглавления «Сон - долг сна, норма, короткая ночь, время от подъёма,
  `get_sleep` - `sleep.md`» между «Тест реакции» и «Самочувствие».
- `.claude/settings.json` — allow-строка (руками Влада, см. «Вне репо»).
- `tests/test_skills_help.py`: `test_sleep_topic_has_fields` (`get_sleep`, `debt_7_h`, `debt_14_h`, `awake_h`, `caution_from`,
  `short_night`, `nap_h` — при Р7 ≠ «не учитывать»), `test_sleep_topic_thresholds_match_constants` по образцу `test_pvt_topic_thresholds_match_constants`
  (`:143`): `f"{sleep.NORM_DAYS} дней"`, `f"{sleep.NORM_MIN_NIGHTS} ночей"`, `f"{sleep.SHORT_NIGHT_H:g} ч"`, `f"{sleep.AWAKE_LIMIT_H}
  ч от подъёма"`, `f"{sleep.DEBT_7_H:g}"`, `f"{sleep.DEBT_14_H:g}"`; полнота имён — существующие `test_every_mcp_tool_is_in_help`,
  `test_index_mentions_every_topic_file`, `test_allow_has_every_topic_file`.
- `docs/architecture.md` — раздел «## Н4: долг сна» после «Н3 … (партия 2)» (`:234`), в разделе Н14 (`:238`) «11 тем» →
  «12 тем» + `sleep`. `README.md` — абзац после строки про тест реакции (`:67`).

## Модули, файлы, функции

Партия 1 — данные, MCP, справка:

- `src/ai_coach/load/sleep.py` — новый (образец `load/overload.py`: константы + чистые функции + отчёт по базе):
  `NORM_DAYS = 90`, `NORM_MIN_NIGHTS = 20`, `DEBT_WINDOWS = (7, 14)`, `SHORT_NIGHT_H = 1.0`, `DEBT_7_H = 3.0`, `DEBT_14_H = 5.0`,
  `AWAKE_LIMIT_H = 16` (значения — Р1–Р3; пороги — догадка, калибрует v2.9);
  `night_hours(row) -> float | None` — `sleep_seconds` > 0 → часы, иначе None (0 и NULL — нет данных);
  `sleep_norm(nights, today) -> dict | None` — медиана часов ночей `[today − NORM_DAYS + 1, today]` с данными, `{"norm_h",
  "nights"}`; ночей меньше `NORM_MIN_NIGHTS` — None;
  `sleep_debt(nights, today, norm_h, days) -> dict` — `{"debt_h": round(Σ(norm_h − h), 1), "nights": n}` по ночам окна с
  данными (Р2: со знаком);
  `awake_hours(sleep_end, at) -> float | None` — часы от подъёма до `at`, один знак;
  `sleep_signals(report) -> list[dict]` — `short_night` (`norm_h − last_night_h >= SHORT_NIGHT_H`), `sleep_debt`
  (`debt_7_h >= DEBT_7_H or debt_14_h >= DEBT_14_H`); формат `{"kind", "value", "limit"}` как у `find_overload`;
  `sleep_report(conn, day, now=None) -> dict` — `{date, norm_h, norm_nights, last_night_h, debt_7_h, nights_7, debt_14_h,
  nights_14, nap_h, wake_at ("YYYY-MM-DD HH:MM" | None), awake_h (только если day == now.date(), иначе None),
  caution_from ("YYYY-MM-DD HH:MM" | None; подъём + 16 ч, дата может быть day + 1), signals}` (Р6 = полный формат, решение
  Влада 2026-11-01; `nap_h` и его роль в долге — Р7, «Открытые вопросы» 1); нормы нет — долги и сигналы None/пусто, `norm_nights` показывает, сколько ночей есть.
- `src/ai_coach/load/__init__.py` — экспорт `sleep_report` (Н11 импортирует оттуда).
- `src/ai_coach/store/garmin_data.py`: `list_sleep_nights(conn, start, end) -> list[dict]` — новая (образец `last_rest_hr`
  `:100`): `SELECT date, sleep_seconds, datetime(json_extract(raw_json, '$.sleep.dailySleepDTO.sleepEndTimestampLocal') / 1000,
  'unixepoch') AS sleep_end, <nap_seconds> FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date`; без `raw_json` в
  ответе; у импортных строк `sleep_end` NULL (умолчание 4). `nap_seconds` (Р7, при любом варианте кроме «не учитывать») —
  `COALESCE(json_extract(raw_json, '$.sleep.dailySleepDTO.napTimeSeconds'), (SELECT SUM(json_extract(value, '$.napTimeSec'))
  FROM json_each(raw_json, '$.sleep.napList')))`: в API-строках поле `napTimeSeconds`, в импортных — список `napList`
  (`napTimeSec`); NULL — дневного сна не записано.
- `src/ai_coach/mcp_server/tools.py`: `sleep(conn, date)` — новая: `period(date, date)`, `sleep_report(conn, date, now())`;
  `focus_log` (`:177`) — к каждой строке `awake_h` по `list_sleep_nights(conn, start, end)` (ключ `date` строки; нет подъёма —
  None); помощник `with_awake(rows, nights) -> list[dict]` — новая, рядом.
- `src/ai_coach/mcp_server/server.py:147` — `get_sleep` после `get_deviations`: «Долг сна на дату (YYYY-MM-DD): norm_h —
  личная норма (медиана за 90 ночей, null — ночей меньше 20), last_night_h, debt_7_h / debt_14_h — недосып против нормы за
  7 / 14 ночей (минус — выспался; ночи без часов не считаются, nights_* — сколько учтено), nap_h (дневной сон за день, Р7),
  wake_at (YYYY-MM-DD HH:MM), awake_h (часов от подъёма, только на сегодня), caution_from (YYYY-MM-DD HH:MM, подъём + 16 ч,
  может быть следующей датой — после этого момента тяжёлых решений не планировать), signals —
  short_night, sleep_debt (kind, value, limit; пусто — норма)»; описание `get_morning_snapshot` (`:50`) — «sleep (как
  get_sleep)»; `get_focus_log` (`:135`) — «awake_h — часов от подъёма (null — подъёма нет)».
- `src/ai_coach/mcp_server/snapshot.py:184` — `snapshot["sleep"] = sleep_report(conn, date, tools.now())`; `NOT_LISTS` (`:65`)
  + `"sleep"`.
- `.claude/agents/coach.md:5` — `, mcp__ai-coach__get_sleep` после `get_deviations` (15 344 + 26 = 15 370 Б, `wc -c`);
  лимит 15 360 → 16 384 в пяти тестах (умолчание 8). Текст `coach.md` в партии 1 не меняется.
- Справка — раздел выше; `README.md:67`; `docs/architecture.md`.
- Тесты: новые `tests/test_load_sleep.py`, `tests/test_mcp_sleep.py`; правки `tests/test_store_garmin_data.py`,
  `tests/test_mcp_focus_log.py`, `tests/test_mcp_snapshot.py:86` (+`"sleep"`), `tests/test_mcp_no_push.py:33` (+`get_sleep`),
  `tests/test_skills_help.py`, пять тестов лимита `coach.md`.

Партия 2 — реакция тренера (состав — по Р4 и Р5):

- При Р4 = 1: `.claude/agents/coach.md:18` — после фразы про `overload.signals` одно предложение: «`sleep.signals` в snapshot
  (короткая ночь, долг сна) - одной фразой, правило - там же в `coach-wellbeing.md`» (~110 Б; лимит уже поднят в партии 1).
  `.claude/agents/coach-wellbeing.md` — абзац «Сон» после абзаца про перегруз (`:9`): поля `sleep` (как в описании
  `get_sleep`), что делать: при `short_night` или `sleep_debt` — сказать одной фразой с цифрами; самочувствие «нормально»
  после недосыпа не считать восстановлением — опереться на readiness, HRV, PVT (`get_pvt_log` по просьбе); после `caution_from`
  тяжёлых решений и дел не планировать (план дня — Р5); план тренировок по сну не менять (`recalc.md` — только по
  `get_deviations`); практика `sleep` из `get_practices` — как в строке `:17`. ~600 Б → лимит 7 168 → 8 192 в
  `tests/test_skills_workload.py:10` (прецедент v2.8: 6 144 → 7 168). `.claude/skills/coach-morning/recovery.md:5` — «…
  readiness; `sleep` - норма, последняя ночь, долг за 7/14 ночей, `caution_from`» (одна строка).
- При Р5 = 1: `src/ai_coach/agenda/day_plan.py`: `_Layout.focus(self, focus_until, focus_max)` (`:151`) — параметры вместо
  констант; `plan_day(…, focus_until=FOCUS_UNTIL, focus_max=FOCUS_MAX)` (`:167`, 8 параметров — под порогом 15);
  `_sleep_limits(conn, day, today, now) -> tuple[time, int, str | None]` — новая: `sleep_report(conn, today, now)`; `day ==
  today` и есть сигнал → `(min(FOCUS_UNTIL, caution_from.time()), FOCUS_MAX − 1, причина)`, где `caution_from` разбирается
  `datetime.strptime(…, "%Y-%m-%d %H:%M")`, а дата `caution_from` позже `day` → предел `FOCUS_UNTIL` (Р6 = полный формат); `day == today + 1` и среди сигналов
  `sleep_debt` → `(FOCUS_UNTIL, FOCUS_MAX − 1, причина)`; иначе `(FOCUS_UNTIL, FOCUS_MAX, None)`; `create_day_plan` (`:247`) —
  вызов и причина в `skipped` («фокус: блоков меньше - короткая ночь / долг сна N ч», умолчание 11). `src/ai_coach/mcp_server/
  agenda.py:69` — docstring `create_day_plan` + «при сигнале сна фокус-блоков меньше, причина в skipped».
  `.claude/agents/coach-day.md:5` — одно предложение про поправку по сну (5 034 / 6 144).
- Тесты: `tests/test_skills_workload.py` (+ поля `sleep` описаны, лимит), `tests/test_skills_text.py` или `test_skills_evening.py`
  (строка в `coach.md`), `tests/test_agenda_day_plan.py` (`plan_day` с `focus_max=2`, `focus_until`), `tests/test_mcp_day_plan.py`
  (сигнал → 2 фокус-блока и причина в `skipped`; нет сигнала — 3), `tests/test_skills_day.py`.

Не трогаем: `load/deviations.py`, `load/overload.py`, `review/service.py`, `sync/garmin_sync.py`, `sync/export_days.py`,
`.claude/skills/coach-evening/SKILL.md`, `.claude/skills/coach-plan/recalc.md`, `cli/*` (своей команды нет), `bin/trener`.

## Партии

Две партии — граница по развилкам: партия 1 работает при любых ответах на Р4/Р5 (режим наблюдения: данные и инструмент есть,
тренер не реагирует); партия 2 — только то, что Влад выберет в Р4/Р5; при Р4 = 2 и Р5 ≠ 1 партии 2 нет. Прецедент — Н3
(две партии, граница по источникам, 62 мин, docs/plan-n3.md «Итог»). Каждая партия самодостаточна: свой коммит после
ревью и тестов, аудит по коммиту, `docs/pipeline.md` — строка (оркестратор). Внутри партии — порядок family.md:
кабан-доеба (красные тесты) → кабан → `make check` → ревью, аудит → коммит → проверка Влада.

1. **Данные, MCP, справка** — `load/sleep.py`, `store/garmin_data.py`, `tools.py`, `server.py`, `snapshot.py`, `coach.md:5`,
   `sleep.md`, `coach-help.md`, README, architecture, тесты. На выходе: `get_sleep("2026-11-01")` отдаёт норму, долг за
   7/14 ночей, подъём и сигналы; snapshot содержит `sleep`; `get_focus_log` — `awake_h`; «что такое долг сна?» — ответ по
   справке. Объём: ~110 строк кода, ~200 строк тестов, ~2 КБ текста (ожидание, не проверено; аналог — Н3 партия 1: ~50
   строк кода, 9 файлов тестов). После партии — перезапуск MCP.
   Граница по справке (решение архитектора 2026-11-01 по хэнд-бэку кабана): `sleep.md` строка «Что делает тренер» написана
   сразу по Р4 = 1 (решение Влада), тексты тренера появятся в партии 2 — между коммитами п1 и п2 справка опережает поведение.
   Принято: правило AGENTS.md требует справку в том же шаге, Р4 решён, переписывать строку дважды дороже. Следствие: партия 2
   обязательна; если Р4 будет пересмотрен — строку `sleep.md:11` переписать на «пока только копит» в том же коммите.
2. **Реакция тренера** — тексты (Р4 = 1) и план дня (Р5 = 1). На выходе: утро после короткой ночи — в сводке фраза с цифрами
   и «„нормально“ не считаю восстановлением»; «разложи день» — два фокус-блока вместо трёх, причина в `skipped`. Объём: ~25
   строк кода, ~900 Б текста, ~60 строк тестов (ожидание, не проверено). Перезапуск MCP при Р5 = 1.

## Тесты (кабан-доеба)

Партия 1 — `tests/test_load_sleep.py` (чистые функции; ночь — `{"date", "sleep_seconds", "sleep_end"}`):

- `night_hours`: `27000` → `7.5`; `0` → None; `None` → None.
- `sleep_norm`: 20 ночей по 7 ч и одна 4 ч (внутри 90 дней) → `norm_h 7.0`, `nights 21`; 19 ночей → None; ночь старше
  `NORM_DAYS` не считается; ночи с `sleep_seconds 0` не считаются и не входят в `nights`.
- `sleep_debt`: норма 7, ночи 6, 7, 8 → `debt_h 0.0` (со знаком, Р2 = 1; в первой редакции плана стояло «6, 6, 8» — арифметическая
  ошибка, там 1.0); 6, 6, 6 → `3.0`; окно 7 берёт ровно 7 последних
  дат до `today` включительно, 14 — 14; ночь без данных → не считается, `nights` меньше; норма None → `debt_h None`.
- `awake_hours("2026-10-31 07:10:00", 2026-10-31 11:00)` → `3.8`; подъём None → None; `at` раньше подъёма → `0.0`.
- Дневной сон (по ответу на Р7; при рекомендованном (1)): норма 7, ночи 6, 6, 6 и `nap_seconds` 3600 в одной → `debt_h 2.0`;
  `nap_seconds` None → как 0; `sleep_norm` и `short_night` от `nap_seconds` не меняются (ночь 5 ч + дневной 2 ч → `short_night`
  есть); ночь без данных и `nap_seconds` 3600 → ночь не учитывается, `nights` меньше; `nap_h` в отчёте — `1.0`, без дневного — `0.0`.
- `sleep_signals`: `last_night_h 5.9`, `norm_h 7.0` → `short_night` (value 1.1, limit 1.0); `debt_7_h 3.0` → `sleep_debt`;
  `debt_14_h 5.0` без `debt_7` → `sleep_debt`; `last_night_h None` → `short_night` нет; оба порога не достигнуты → `[]`.
- `sleep_report(conn, day, now)`: база с 25 ночами (`upsert_daily_metrics` с `raw_json = {"sleep": {"dailySleepDTO":
  {"sleepEndTimestampLocal": <мс>}}}`, как `tests/test_mcp_snapshot.py:31` кладёт `restingHeartRate`) → поля по формулам;
  `wake_at` `"2026-10-31 07:10"`, `caution_from` `"2026-10-31 23:10"` (подъём + 16 ч, `AWAKE_LIMIT_H`); подъём 09:30 →
  `caution_from "2026-11-01 01:30"` (переход даты, Р6); `now` того же дня 11:00 → `awake_h 3.8`,
  `now` другого дня → `awake_h None`; день без строки → `last_night_h None`, `wake_at None`, `caution_from None`; строка без
  `dailySleepDTO` (импорт) → `wake_at None`, часы считаются; `raw_json` в ответе нет (`"SECRET"` не встречается в
  `json.dumps`).

`tests/test_store_garmin_data.py`: `list_sleep_nights` — три колонки, по возрастанию даты, включительно; `sleep_end` из
`sleepEndTimestampLocal` в формате `YYYY-MM-DD HH:MM:SS` (`1793435400000` → `2026-10-31 08:30:00`, проверено
`datetime.fromtimestamp(…, UTC)`); строка без ключа → None; `nap_seconds` (Р7): `dailySleepDTO.napTimeSeconds 4620` → 4620,
`napList` из двух записей 1500 и 600 → 2100, ни того ни другого → None;
ключа `raw_json` в строках нет.

`tests/test_mcp_sleep.py` (образец `tests/test_mcp_overload.py`, `mcp_fakes.call`): `get_sleep` в `tool_names`; пустая база →
нормы и долги None, `signals []`, `norm_nights 0`; 30 ночей → числа как у `sleep_report`; плохая дата → `ToolError`;
snapshot содержит `sleep` с теми же ключами и `test_snapshot_has_all_sections` зелёный; `test_snapshot_fits_total_limit`
зелёный; `test_snapshot_has_no_raw_json` (`:150`) зелёный с `sleep`.

`tests/test_mcp_focus_log.py`: строка `focus_log` за день с подъёмом `07:10` и `logged_at 11:00` → `awake_h 3.8`; день без
строки `daily_metrics` → `awake_h None`; порядок и `truncated` как были.

Тексты: `coach.md` содержит `mcp__ai-coach__get_sleep` и ≤ 16 384 Б (пять тестов); `test_mcp_no_push`: `tool_names ==
EXPECTED_TOOLS` с `get_sleep`; справка — раздел «Справка».

Партия 2 (при Р4 = 1): `coach-wellbeing.md` содержит `short_night`, `sleep_debt`, `caution_from`, `debt_7_h`, «не считай
восстановлением» (или формулировка кабана — доеба согласует), ≤ 8 192 Б; `coach.md:18` содержит `sleep.signals`;
`recovery.md` содержит `caution_from`, ≤ 3 072 Б. При Р5 = 1 (`tests/test_agenda_day_plan.py`, `tests/test_mcp_day_plan.py`):
`plan_day(…, focus_max=2)` в будни → 2 фокус-блока; `focus_until=time(15, 0)` → все фокус-блоки заканчиваются не позже
15:00; `create_day_plan` на сегодня при `short_night` (строка `daily_metrics` на `today` с подъёмом 07:10 и 5 ч сна, 25 ночей
по 7 ч до) → 2 блока, последний не позже `min(19:00, 23:10)` = 19:00, в `skipped` строка с «короткая ночь»; подъём 03:00 →
`caution_from "<день> 19:00"` не режет, подъём 02:00 → `"<день> 18:00"` режет; подъём 09:30 → `caution_from` следующей
даты 01:30 → предел 19:00, а не 01:30 (Р6); на завтра при `sleep_debt` → 2 блока без ограничения по часу;
на завтра при одном `short_night` → 3 блока; без строк сна → 3 блока, `skipped` без строки про сон; ответ без новых ключей
(`test_response_shape` зелёный).

Проверка руками (Влад): после партии 1 и перезапуска MCP — `тренер` → «как мой сон?» → тренер читает `sleep` из сводки или
`get_sleep` и называет норму, последнюю ночь, долг за 7 и 14 ночей, подъём; «покажи дневные оценки за неделю» →
`get_focus_log` со `awake_h`; «что такое долг сна?» → ответ по `sleep.md`. После партии 2: утро после короткой ночи — в
сводке одна фраза про сон и `caution_from`, самочувствие «4, нормально» не превращается в «восстановился»; «разложи день» →
два фокус-блока и причина в `skipped`; обычное утро — сводка как раньше, три блока.

Для mutmut (`модуль:функция` — TESTS по `grep -l`): `load.sleep:night_hours`, `load.sleep:sleep_norm`, `load.sleep:sleep_debt`,
`load.sleep:awake_hours`, `load.sleep:sleep_signals`, `load.sleep:sleep_report` (новые) — `tests/test_load_sleep.py`,
`tests/test_mcp_sleep.py`; `store.garmin_data:list_sleep_nights` (новая) — `tests/test_store_garmin_data.py`,
`tests/test_mcp_sleep.py`; `mcp_server.tools:sleep`, `mcp_server.tools:with_awake` (новые) — `tests/test_mcp_sleep.py`,
`tests/test_mcp_focus_log.py`; `mcp_server.tools:focus_log` — `tests/test_mcp_focus_log.py`, `tests/test_cli_focus.py`,
`tests/test_mcp_no_push.py`, `tests/test_skills_help.py`, `tests/test_store_migration_0021.py` (5 файлов по `grep -l focus_log
tests/` после партии 1); `mcp_server.snapshot:morning_snapshot` — `tests/test_mcp_snapshot.py`, `tests/test_mcp_overload.py`,
`tests/test_mcp_sleep.py` (всего 24 файла по `grep -l morning_snapshot tests/` после партии 1); при Р5 = 1 `agenda.day_plan:plan_day`, `agenda.day_plan:create_day_plan`,
`agenda.day_plan:_sleep_limits` (новая), `agenda.day_plan:_Layout.focus` — `tests/test_agenda_day_plan.py`,
`tests/test_mcp_day_plan.py`. Каталоги — `make mutate` по правилу проекта (фоном вне агента; долги Н2/Н13 — handoff).

## Развилки и риски

Видимое Владу — развилки, решает Влад. Первая — блокирующая для партии 1.

- **Р1. Личная норма сна.** (1) Медиана часов сна за последние 90 ночей с данными, не меньше 20 ночей (в живой базе за 90
  дней — 90 ночей); пассивно, без ввода. Слабость: при хроническом недосыпе медиана сползает за ним — хронику ловит порог
  долга и существующее «сон < 6 ч». (2) Значение профиля `coach profile set sleep_norm <ч>` (`profile/service.py:38
  SETTABLE`, `FLOAT_RANGES`), пока не задано — (1); +~15 строк и справка `goals-profile.md`. (3) Garmin `sleepNeed.baseline`
  из `raw_json` (есть только в API-строках с 2026-10-01; у Влада — константа 420 мин, то есть возрастная норма, не личная).
  Рекомендую (1): минимум, личная по данным; (2) — отдельным пунктом беклога, если медиана покажется заниженной.
  Разблокирует партию 1.
- **Р2. Долг со знаком или только недосып.** (1) Сумма (норма − сон) со знаком: длинная ночь гасит долг, итог может быть
  отрицательным («выспался на N ч»). (2) Только недосыпы (`max(0, …)`): долг не гасится. Рекомендую (1): двухпроцессная
  модель — восстановительный сон возвращает долг; читается честнее.
- **Р3. Пороги сигнала** (когда тренер скажет фразу). Рекомендую: короткая ночь — короче нормы на 1 ч и больше; долг — 3 ч за
  7 ночей или 5 ч за 14 (≈ 25 мин недосыпа в среднем за ночь; у Van Dongen 14 × 1 ч ≈ ночь без сна); `caution_from` —
  подъём + 16 ч (Van Dongen ~15,8 ч). Всё — догадка, константы `load/sleep.py`, калибрует v2.9 вместе с `TOTAL_HIGH`.
  Альтернатива: доля нормы (ночь < 85 % нормы) — то же самое другими словами, хуже читается в справке.
- **Р4. Что видно в утренней сводке.** (1) При сигнале — одна фраза с цифрами и `caution_from`; правило в `coach-wellbeing.md`:
  «нормально» после недосыпа не считать восстановлением (опора — readiness, HRV, PVT), тяжёлых дел после `caution_from` не
  планировать; план тренировок по сну не менять — `recalc.md` и `find_deviations` не трогаются. Это текст, а не действие
  тренера: NOTES 2026-10-31 «новые фичи — наблюдение» не нарушается по сути, но фраза в сводке — новое видимое поведение.
  (2) Чистое наблюдение: `get_sleep` по просьбе и `sleep` в snapshot без слов тренера, через 2 недели (К1) — решить про (1).
  Рекомендую (1): BACKLOG 18 — именно про осторожность тренера; без слов долг никому не виден; стоимость — ~700 Б промпта.
  Разблокирует тексты партии 2.
- **Р5. План дня при сигнале сна (r1:185).** (1) В этом шаге: `create_day_plan` на сегодня при `short_night`/`sleep_debt` —
  фокус-блоков на один меньше и не позже `caution_from`; на завтра (вечернее планирование) — на один меньше только при
  `sleep_debt` (долг не исчезает за ночь, короткая ночь ещё неизвестна); причина — в `skipped`; рамку дня (`day_start`)
  не сдвигаем — «позже начало» Влад говорит словами (`day_start`). (2) Без кода: предложение в `coach-day.md` — при сигнале
  предложить `day_start` позже и меньше задач. (3) Отложить пунктом беклога до v2.9. Рекомендую (1): r1 запланировал это
  партией Н4; черновики утверждает Влад — риск мал; ~25 строк. Разблокирует код партии 2.
- **Р6. Формат времени в ответах.** Решено Владом 2026-11-01 («Решения»): `wake_at`, `caution_from` — полные `YYYY-MM-DD
  HH:MM` местного времени; `debt_7_h`, `debt_14_h`, `nap_h`, `awake_h` — часы с одним знаком; `norm_h` и `last_night_h` — два
  знака (как медиана, умолчание 3; кабан выровнял `last_night_h` по `norm_h`, принято 2026-11-01). Следствие: `_sleep_limits` (Р5) сравнивает дату
  `caution_from` с `day`, справка не нуждается в оговорке «после полуночи».
- **Р7. Дневной сон (`napTimeSeconds`).** Влад 2026-11-01: учесть. Как — «Открытые вопросы» 1.

Риски:

- Строка сегодняшнего дня без сна (sync до того, как часы отдали ночь): `last_night_h None`, `short_night` не считается,
  долг — по 6 и 13 ночам; тренер скажет «ночи ещё нет». На живой базе на момент разведки у строки 2026-11-01 подъёма нет.
- `sleep_seconds = 0` у 145 импортных строк OFF_WRIST: `find_deviations` (`deviations.py:48`) считает такой день «сон 0 ч <
  6» — существующее поведение, не наш шаг; в `load/sleep.py` ноль — «нет данных». Кандидат беклога (только если Влад
  захочет): `sleep is not None and sleep > 0` в `find_deviations`.
- Подъём только у API-строк (с 2026-10-01): `awake_h` у оценок Н1 есть для всех их дней (`focus_log` с 2026-10-31); для
  истории импорта `wake_at None`. Если Н9 захочет подъём за 2025 год — конверсия `sleepEndTimestampGMT` импорта через пояс
  (пояс поездок неизвестен) или колонка при импорте — отдельно, не здесь.
- `caution_from` за полночь (подъём после 08:00 → после 00:00 следующего дня): при Р6 = полный формат дата видна в ответе;
  `_sleep_limits` обязан сравнить дату, иначе `time()` 01:30 урежет фокус до 01:30 — тест в партии 2.
- Дневной сон (Р7) в живой базе (чтение `?mode=ro`, 2026-11-01): в API-строках `dailySleepDTO.napTimeSeconds` есть у 31 из
  32, > 0 — у 1; в импортных — не поле, а список `$.sleep.napList[].napTimeSec`, есть у 22 строк (2025-12-01…2026-09-26),
  по одной записи. Ночной `sleep_seconds` дневной сон не включает (импорт: сумма фаз = окно ночи без пробуждений у 4 из 4
  проверенных; API: `sleepTimeSeconds` = `sleep_seconds` при отдельном `napTimeSeconds`). Отсутствие обоих полей — «не
  записано», не отличимо от «не спал днём».
- Snapshot: `sleep` ~250 Б (расчёт по длине ключей, не прогон); лимит 20 000 держит цикл `snapshot.py:208`; `NOT_LISTS`
  обязателен — иначе цикл обрезки упадёт на `snapshot["sleep"]["rows"]`.
- Чтение 90 ночей — `list_sleep_nights` без `raw_json` в `SELECT`; `json_extract` по 93 строкам — 31 мс (замер), на snapshot
  ложится один вызов, на `get_focus_log` — один.
- Лимиты промптов: `coach.md` 15 360 → 16 384 (умолчание 8; прецеденты Н1 умолчание 11, v2.8); `coach-wellbeing.md` 7 168 →
  8 192 при Р4 = 1. Кабан меряет `wc -c` после правок.
- Пороги Р3 — догадка: много фраз про сон → поднять `DEBT_*` в v2.9; тренер начнёт менять план тренировок «по сну» вопреки
  тексту — пункт беклога на промпт, не код (как риск Н1 партии 3).
- Н11 ждёт долг сна: интерфейс — `ai_coach.load.sleep_report(conn, day)` и `sleep_debt`; менять формат после Н11 дороже —
  поля зафиксированы в «Модулях».
- Smells: `sleep_report` собирает 12 ключей — держать под порогом длины qlty (`SMELLS_MAX=0`), при росте — вынос
  `_debts(nights, today, norm_h)`.

## Умолчания (внутреннее)

1. Модуль `load/sleep.py`; имена ключей ответа — как в «Модулях» (`norm_h`, `last_night_h`, `debt_7_h`, `debt_14_h`,
   `nights_7`, `nights_14`, `norm_nights`, `wake_at`, `awake_h`, `caution_from`, `signals`); `kind` сигналов — `short_night`,
   `sleep_debt`; формат сигнала `{"kind", "value", "limit"}` как у `find_overload`.
2. Ночь = строка `daily_metrics` за дату подъёма (Garmin `calendarDate`), как и `sleep_seconds`; `sleep_seconds` 0 или NULL —
   нет данных: ночь не входит ни в норму, ни в долг, `nights_*` показывает учтённое. Дневной сон — по Р7 (решение Влада
   2026-11-01 «учесть», способ — «Открытые вопросы» 1): читается из `raw_json` двумя путями (`dailySleepDTO.napTimeSeconds` у
   API, сумма `napList[].napTimeSec` у импорта), отсутствие — 0; дневной сон принадлежит дате строки (сон после подъёма этой
   даты); строка без ночного сна не учитывается и при дневном сне. Ключ ответа — `nap_h`.
3. Окно нормы `[day − 89, day]` включает окна долга; медиана — `statistics.median`, `round(…, 2)`; долг — `round(…, 1)`.
4. Подъём читается при чтении из `raw_json` (`json_extract`, образец `last_rest_hr`), колонка и миграция не добавляются;
   импортные строки (без `dailySleepDTO`) — `wake_at None`. Альтернатива — колонка `sleep_end` с backfill в миграции — если
   Н9/Н11 начнут читать подъём массово.
5. `awake_h` — только в `get_focus_log` (не в `coach log focus`, не в `get_wellbeing`): поправка нужна анализу Н9, Владу на
   экране — нет. В snapshot `sleep.awake_h` — только при `date == today` (часы `tools.now()`), иначе None.
6. `caution_from` отдаётся всегда, когда известен подъём (Р6: `YYYY-MM-DD HH:MM`, `strftime("%Y-%m-%d %H:%M")` от `sleep_end +
   timedelta(hours=AWAKE_LIMIT_H)`; `wake_at` — тот же формат, секунды отбрасываются); применять его велит текст Р4/Р5 только при
   сигнале.
7. `get_sleep(date)` — один день, `period(date, date)`; `raw_json` наружу не идёт (в ответе только агрегаты).
8. Лимит `coach.md` 15 360 → 16 384 Б везде, где он проверяется (`git grep 15360 tests/` на HEAD aba17d4 — 14 строк в 11
   файлах: `test_skills_workload.py:90`, `test_skills_evening.py:83,132`, `test_skills_text.py:264,267`, `test_skills_day.py:29`,
   `test_coach_link_texts.py:6,9`, `test_mcp_focus_log.py:68`, `test_mcp_pvt_log.py:70`, `test_skills_agenda.py:23`,
   `test_skills_practices.py:11,27`, `test_skills_week.py:17`); в плане было 5 — недосчёт архитектора, кабан поднял все 11
   (принято 2026-11-01). Кандидат беклога (оптимизация, не этот шаг): одна константа лимита в общем модуле тестов.
9. Справка — новая тема `coach-help/sleep.md`, не раздел в `wellbeing.md`: запас `wellbeing.md` (1 013 Б) оставлен Н12 по
   plan-n2 «Риски»; строка оглавления и allow — как у `pvt.md`.
10. `NOT_LISTS` + `"sleep"`; `DATE_SERIES` не меняется.
11. При Р5 = 1 причина в `skipped`: «фокус: блоков меньше - короткая ночь (N ч против нормы M)» или «… - долг сна N ч за 7
    ночей»; ключи ответа `create_day_plan` не меняются (`test_response_shape`). `_sleep_limits` считает отчёт на `today`, не
    на `day`: ночь завтрашнего дня неизвестна.
12. `sleep_report` импортируется в `snapshot.py` и `day_plan.py` из `ai_coach.load` (как `overload_report`); `tools.sleep`
    — имя функции в `tools.py` (модуль `time` там не импортируется, конфликта нет).
13. Коммит после каждой партии; `docs/pipeline.md` — строка на партию (оркестратор); ROADMAP, карточка 018 и handoff — после
    аппрува и закрытия.

## Открытые вопросы

1. Р7 — как учесть дневной сон (`load/sleep.py:sleep_debt`, `sleep_norm`, `sleep_signals`, `store/garmin_data.py:
   list_sleep_nights` — новые). Блокирующий для партии 1.
   варианты: (1) в долг, не в норму и не в короткую ночь: долг = Σ(норма − (ночь + дневной)), норма — медиана только ночей,
   `short_night` — по ночи; `nap_h` в ответе; (2) в норму и долг: «сон за сутки» = ночь + дневной везде, включая короткую ночь;
   (3) только показать `nap_h` в ответе и справке, в расчёты не входит.
   Импортные строки «без поля»: у них не поле, а список `napList` (22 строки) — читаем оба источника; нет ни того ни другого —
   0 (не отличимо от «не спал днём»; Garmin пишет дневной сон, только если часы на руке).
   рекомендую (1) — по двухпроцессной модели (research-brain п. 16) дневной сон снижает давление сна и гасит долг, поэтому
   в долг; но не в норму — иначе 23 дня с дневным сном сдвинут «обычную ночь»; и не в короткую ночь — утренний сигнал
   нужен до того, как дневной сон случился (дневной сон даты D идёт после подъёма D). (2) смешивает дневной и ночной сон в
   пороге короткой ночи; (3) — не «учесть» в смысле вопроса Влада.
   разблокирует: формулы и тесты партии 1, текст справки (`nap_h`); решает Влад.

## Правки по ревью

Партия 1, аудит свекрови 2026-11-01, два пункта «к папе» по `load/sleep.py:sleep_signals` (архитектор, 2026-11-01):

1. **`sleep_debt` — один сигнал, при обоих порогах `value`/`limit` из окна 7 ночей (`elif`).** Оставить как в коде, план
   уточнён. Основание: один `kind` — один триггер, как у `find_overload` (каждый `kind` не повторяется, тренер и
   `_sleep_limits` партии 2 проверяют «есть ли `sleep_debt`», а не считают сигналы); окно 7 — свежее и острее, его цифра
   точнее описывает «сейчас»; оба долга и так лежат рядом в отчёте (`debt_7_h`, `debt_14_h`) — фраза тренера по Р4 берёт
   цифры оттуда, а не из сигнала. Умолчание 11 уже закрепило текст `skipped` «долг сна N ч за 7 ночей» — код ему
   соответствует. Окно сигнала читается по `limit` (`DEBT_7_H` → 7 ночей, `DEBT_14_H` → 14) — ключ `days` не добавляем,
   формат `{kind, value, limit}` остаётся. Альтернатива (не берём): два `kind` `sleep_debt_7`/`sleep_debt_14` — тренеру два
   сигнала об одном, справка и `coach-wellbeing.md` длиннее. Не развилка Влада: на экране оба долга видны всегда, выбор
   касается только того, какая из двух уже показанных цифр дублируется в `signals`. Тест
   `test_debt_signal_is_single_when_both_reached` — оставить; доеба добавляет сверку `value == debt_7_h` в этом случае.
   Партии 2: причина в `skipped` при `limit == DEBT_14_H` — «… долг сна N ч за 14 ночей».
2. **`short_night`: `round(norm - last, 1) >= SHORT_NIGHT_H` — недосып 0,95 ч даёт сигнал.** Править код. Округление
   нужно (без него `7.1 − 6.1 = 0.9999999999999996 < 1.0` — ровно час недосыпа по отчёту не даст сигнала), но до одного
   знака — грубо: `norm_h` и `last_night_h` отдаются с двумя знаками (Р6, умолчание 3), значит и разница — с двумя. Станет:
   `gap = round(norm - last, 2)`; сигнал при `gap >= SHORT_NIGHT_H`; `value = gap` (два знака, как операнды; в прежних тестах
   `7.0 − 5.9 → 1.1` — не меняется). Проверено: `round(7.1 − 6.1, 2) = 1.0`, `round(7.0 − 6.05, 2) = 0.95`. Тесты доебе
   (`tests/test_load_sleep.py`, рядом с `test_slightly_short_night_is_quiet`): `last_night_h 6.05` при норме 7.0 → `[]`;
   норма 7.1, `last_night_h 6.1` → `short_night`, `value 1.0`. Справка `sleep.md:7` «короче нормы на 1 ч и больше» — верна,
   не трогаем. Правило: было `round(norm - last, 1) >= SHORT_NIGHT_H` → станет `round(norm - last, 2) >= SHORT_NIGHT_H`.

Замечания мамы (неблокирующие) — кабану: `sleep_norm` — лишний `if (h := …)` убрать (`_window` уже отбросил пустые ночи);
имя теста `…_three_columns` → `…_four_columns`; импорты в `tools.py` — оставить.

Исправлено 2026-11-01: кабан — `short_night` по `round(…, 2)`, `sleep_norm` без лишнего `if`; доеба — сверка `value`
в `test_debt_signal_is_single_when_both_reached`, тесты `test_gap_just_under_limit_is_quiet` и
`test_gap_rounded_to_limit_fires`, переименование `…_four_columns`. Решения — архитектора (п. 1–2) и мамы; Влада
не требовали. Повторное ревью мамы — `sleep_norm` через `night_hours(n) or 0.0` (кабан; `or 0.0` — только для pyright,
`_window` пустые ночи уже отбросил). Строку allow `coach-help/sleep.md` в `.claude/settings.json` добавил Влад (подтвердил 2026-11-01).

## Смета (кабан-тесть, режим 1)

**Что проверено:** план Н4 после решений Влада 2026-11-01 («Суть», «Решения», «Партии», «Тесты», «Развилки и риски»):
Р1–Р5 по рекомендациям, Р6 (полные дата и время), Р7 (дневной сон гасит долг, `nap_seconds` из двух путей `raw_json`);
сценарий — две партии, Р4 = 1 и Р5 = 1, Декарт — по умолчанию звать (в Н3 и Н14 Влад отказался). Цены — тариф
metrics.py от 2026-10-25 (страницу pricing не сверял), fable — по ценам Opus. Масштаб по «Модулям/файлам»: п1 ~130 строк
кода (было ~110; +~20 на Р7: `nap_seconds` через `COALESCE`/`json_each`, `nap_h`, ветка долга) против ~50 у Н3 п1, ~230
строк тестов (+~30 на Р7, Р6); п2 ~25 строк кода (+ разбор даты `caution_from`, тест перехода через полночь) против Н3 п2;
опора — «Итог» Н3 (docs/plan-n3.md:433: 62 мин, 34,5M, $19,53 факт при смете $9,7–13,8) и Н14. Р6/Р7 добавили
~5–8 % к смете против прошлой редакции, не больше: развилки решены, один раунд ожидания окон меньше. Подписок, API вне
конвейера, хостинга и БД шаг не добавляет (Garmin — новых запросов нет, зависимостей нет): платное — только токены LLM.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Токены конвейера Н4 | разово $15–24 без Декарта; $22–31 с ним | один шаг, 2 партии; в месяц — по числу шагов (в Н3 $19,5, Н14 $13,5) | не звать Декарта на Н4 (как в Н3, Н14) | ~$6,6 (3 вызова × $2,2, факт Ш28: $10,95 / 5 вызовов) | разбор конвейера по этому шагу; решает Влад |
| Оркестратор (opus) | $3,4–6,0 | 9–16M токенов; Н3 был 17,9M из-за 3 /compact и 15 окон | решения Р1–Р7 уже приняты — окон Влада в партиях меньше; /compact не между партиями, а только по handoff | до ~$1,5 | ничего, порядок вопросов |
| Партия 2 отдельно (ревью + аудит + коммит) | ~$3–5 из общей суммы | партия ~25 строк кода, ~900 Б текста | слить п2 в п1 (один круг ревью и аудита) | ~$1,5–2,5, ~15 мин | граница «наблюдение / реакция тренера» (откат реакции отдельным коммитом); при Р4 = 2 и Р5 ≠ 1 п2 нет вообще: экономия ~$3–5 |
| Доеба, кабан (sonnet) | $2,4–4,0 | уже на sonnet; тестов больше из-за Р7 | haiku-5-5 (тариф $0,10/$0,50) для доебы | ~$0,8 | качество красных тестов (догадка, не мерено) — не рекомендую |
| Р7 в п1 (дневной сон: два пути `raw_json`) | ~$0,8–1,2 из общей суммы | +~20 строк кода, +~30 строк тестов, ревью лишний круг | показать `nap_h` без расчёта (вариант 3 из Р7 снят Владом) | ~$0,8–1,2 | снято решением Влада «учесть»: не предлагаю, только отмечаю цену |
| mutmut | $0 токенов | фоном вне агента, локально | — | — | — |

Ревью и аудит (мама, свекровь) не трогаю; слабую модель им и оркестратору не предлагаю.

| Партия | Время |
|---|---|
| План (папа) + доработка Р6/Р7 | уже прошло: 16,2 мин + 1,7 мин (metrics.py, a703117c… 19:02–19:19 UTC, aa75146d… 19:37–19:39) |
| 1. Данные, MCP, справка | ~45–65 мин (в Н3 п1: ~41 мин при вдвое меньшем коде; +Р7; mutmut и окна Влада — внутри) |
| 2. Реакция тренера (Р4 = 1, Р5 = 1) | ~15–25 мин (нет партии при Р4 = 2 и Р5 ≠ 1) |
| Декарт (3 вызова) + тесть р.3 | ~10–15 мин |
| Весь шаг (после плана) | ~70–105 мин (без п2 и Декарта: ~45–70) |

Уже прошло: $3,28 (папа-кабан a703117c9d2b6780c $2,78 + aa75146d90b0a12b0 $0,50, metrics.py; id из agents.md) и тесть
р.1 первая редакция ae25d496bae4c5a61 $0,22 — нижняя граница сметы ≥ $3,28 (тесть — в строке kaban-test); мой запуск
a142b0f6bd89500cb не включён.

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| orchestrator | opus | 9–16M | 3,4–6,0 |
| papa-kaban (прошло $3,28, 2 запуска; +1–2 по ревью) | fable (по Opus) | 2,6–4,2M | 4,3–6,0 |
| kaban | sonnet | 2,8–4,5M | 1,5–2,4 |
| kaban-doeba | sonnet | 2,8–5M | 1,1–1,9 |
| mama-kaban | opus | 2,8–4,8M | 2,3–4,0 |
| kaban-svekrov | opus | 2,2–3,8M | 2,0–3,3 |
| kaban-test (р.1 ×2 sonnet — прошло $0,22 + этот запуск, р.3 opus) | sonnet / opus | 0,3–0,5M | 0,35–0,6 |
| **итого без Декарта** | | 22,5–39M | **15,0–24,2** |
| kaban-dekart (3 вызова = 2 партии + 1 сводный) | fable (по Opus) | 2–3M (допущение) | 6,6 (2,2 × 3, последний факт Ш28: $10,95 / 5 вызовов) |
| **итого с Декартом** | | 24,5–42M | **21,6–30,8** |

Модели (`grep -H '^model:' ~/.claude/agents/<роль>.md`): kaban-dekart.md:model: fable; kaban-doeba.md:model: sonnet;
kaban.md:model: sonnet; mama-kaban.md:model: opus; kaban-svekrov.md:model: opus; kaban-test.md:model: opus;
papa-kaban.md:model: fable. Мой запуск — sonnet-5-5, kaban-test.md просит opus: р.3 считаю по opus.
Допущение по Н3: факт был ×1,4–2 выше сметы (оркестратор, ревью с 8–9 хэнд-бэками) — верхняя граница заложена с этим.
