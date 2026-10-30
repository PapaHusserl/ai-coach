# Шаг Н1. Самооценка днём, отстранение и помехи в чек-ине

Закрывает BACKLOG 16 и 23; из BACKLOG 20 — только вопросы чек-ина (пункт 20 закрывается с Н3,
docs/plan-roadmap-r1.md:50). План — папа-кабан, 2026-10-31. Режим «встроить». Разведка на HEAD 03ca02c; живая база
`~/.local/share/ai-coach/coach.db` — только чтение (`?mode=ro`, `PRAGMA query_only`), в документе — счётчики без
личных данных (репо публичное).

## Суть

Решения Влада: NOTES.md 2026-10-30 (самооценка фокуса и усталости 2–3 раза в день — да; 1–2 вопроса об
отстранении вечером — да), 2026-10-31 (текущее поведение тренера не трогать, новые фичи — в режиме наблюдения);
docs/plan-roadmap-r1.md «Решения» 1–2 (один шаг; напоминания — события календаря, ответ командой или в чате).

Что уже есть (по коду):

- Вечерний чек-ин: `coach feel <1-5> ["текст"] --mood --stress --work --hobby --rest` (`src/ai_coach/cli/main.py:265`),
  оценки — в `wellbeing_log` (миграции 0006, 0016: `mood`, `stress` NULL-able), часы — в `day_counters`; день —
  `wellbeing_day` (до 04:00 — вчера, `store/journal.py:149`). Скилл `.claude/skills/coach-evening/SKILL.md`
  (2925 Б при лимите 3072 — `tests/test_skills_evening.py:15`; запас 147 Б), запуск `тренер вечер`.
- Напоминания: `coach_events` (0019) с `kind=checkin`, `repeat=daily`, `alarm_min`; черновик через MCP
  `create_draft_event`, в календарь — `coach event write` после «да» (v2.6). Правило `validate_draft`
  (`agenda/service.py:109-114`): повторяющийся чек-ин — один на всю базу (`store/agenda.py:53 active_repeat`,
  `fetch_one`). В живой базе один `checkin written daily` — вечернее напоминание.
- Данные: `wellbeing_log` — 24 дня (2026-10-07…10-30), 56 записей, 2,33 в день; вечерние (mood или stress) —
  20 дней; часы записей — 09–13 (сессия `тренер`) и 23–01 (вечер). Днём 14–18 — единицы: дневной профиль Н9
  строить не на чем, это и закрывает Н1.

Что строим (три куска, каждый — партия):

- **День.** Новая таблица `focus_log` (фокус, умственная усталость, «трудно заставить себя» — 1–5, текст) —
  по решению r1 (`plan-roadmap-r1.md:34`: день — новая таблица, вечер — поля `wellbeing_log`). Команда
  `coach focus`, просмотр `coach log focus`, MCP `get_focus_log`. Отдельная таблица, а не колонки `wellbeing_log`:
  дневная оценка — не «самочувствие», иначе три записи в день сдвинут «основную запись дня» `main_wellbeing`
  (`load/deviations.py:14`) и отклонения по `score`.
- **Напоминания.** 2–3 ежедневных события `checkin` в календаре коуча через существующий поток черновик → «да» →
  `coach event write`. Единственная правка кода — снять правило «один повторяющийся на всех» (ниже «Правило»).
- **Вечер.** Четыре NULL-able колонки в `wellbeing_log` (как 0016), четыре опции `coach feel`, вопросы и ритуал
  закрытия дня в `coach-evening`.

**Правило:** было `validate_draft`: `if active_repeat(conn) is not None: raise AgendaError("Повторяющийся чек-ин
уже есть (черновик или в календаре).")` → станет: ошибка только если среди активных повторяющихся
(`active_repeats(conn)`, draft/written) есть событие с тем же временем начала `start_at[11:16]`; число ежедневных
чек-инов не ограничено. Остальное — новое (`coach focus`, `focus_log`, колонки вечера).
**Поведение:** меняется — (1) тренер может поставить несколько ежедневных напоминаний; (2) новая команда
`coach focus`; (3) вечерний чек-ин задаёт новые вопросы и ритуал закрытия дня. Не меняется: отклонения
(`find_deviations`), перегруз (`find_overload`), недельный обзор, `evening_done_today` — новые поля туда не входят
(режим наблюдения, NOTES 2026-10-31); пороги и реакция — после v2.9 / Н6 / Н9.
**Вне репо:** календарь коуча в iCloud — Влад говорит «да» на запись 2–3 напоминаний (`coach event write`,
не в allow — так задумано v2.6); MCP-сервер перезапустить после партии 1 (новый инструмент; architecture.md:152).
Новых зависимостей нет.

## Решения

Влад, 2026-10-31, окнами по одному — все по рекомендациям папы:

- Р3 — `coach focus <фокус> <усталость> <усилие>`, три обязательные цифры 1–5.
- Р2 — CLI + тренер по фразе «фокус 4 2 3».
- Р1+Р4 — 3 напоминания ежедневно 11/15/18, «Фокус 1–5?», 5 мин, alarm 0, в заметке команда.
- Р5 — четыре вопроса вечера (мысли о работе, погружение, помехи, ценность).
- Р6 — ритуал закрытия дня без записи в базу.
- Р7 — только сбор, тренер не реагирует.

## Модули, файлы, функции

Партия 1 — день:

- `src/ai_coach/store/migrations/0021_focus_log.sql` — новая: `focus_log(id, date, logged_at, focus, fatigue,
  effort, text)`, CHECK 1–5, индекс по `date`.
- `src/ai_coach/store/journal.py`: `add_focus`, `list_focus` — новые (образцы `add_wellbeing` :157,
  `list_wellbeing` :163).
- `src/ai_coach/cli/journal.py`: `focus` — новая (образец `weight` :81), `check_scores` — новая (вынос проверки
  1–5 из `feel`, `cli/main.py:277-279`), `log_focus` — новая (`@log_app.command("focus")`, образец `log_weight` :201);
  `src/ai_coach/cli/main.py:56-57` — `app.command()(focus)`.
- `src/ai_coach/mcp_server/tools.py`: `focus_log` — новая (образец `wellbeing` :169); `src/ai_coach/mcp_server/server.py`
  TOOLS — `get_focus_log` (рядом с `get_wellbeing` :124).
- `.claude/settings.json` — `Bash(uv run coach focus:*)` (`coach log` уже в allow); `.claude/agents/coach.md:10` —
  `focus` в список разрешённых команд (+ при Р2 = 1 фраза: «фокус 4 2 3» в чате → `uv run coach focus 4 2 3`);
  14389 Б при лимите 15360 — запас 971 Б.
- `README.md:65` — абзац про `coach focus`; `docs/architecture.md` — раздел «Н1».
- Тесты: новые `tests/test_cli_focus.py`, `tests/test_store_migration_0021.py`, `tests/test_mcp_focus_log.py`;
  `tests/test_skills_evening.py` или `tests/test_coach_link_texts.py` — allow и текст coach.md.

Партия 2 — напоминания:

- `src/ai_coach/store/agenda.py: active_repeat` (:53) → `active_repeats` (список, `fetch_all`,
  `ORDER BY start_at, id`).
- `src/ai_coach/agenda/service.py: validate_draft` (:83; правило :109-114), `agenda_rows` (:201 — в начало
  вставляются все повторяющиеся с `date < date_from`).
- `src/ai_coach/sync/workload_sync.py: vanished` (:78) — уже обходит все повторяющиеся (:83-85), правок не ждём;
  закрепить тестом с двумя.
- Тексты «один на всех»: `src/ai_coach/mcp_server/server.py:309`, `src/ai_coach/mcp_server/agenda.py:33`,
  `.claude/agents/coach-agenda.md:14` (+ абзац «напоминания дневной оценки»: сколько, время, заголовок, заметка с
  командой, `alarm_min=0`; 5542 Б при лимите 6144 — запас 602 Б), `docs/architecture.md:202`, `README.md:68`.
- Тесты: `tests/test_agenda_service.py:154-163` (`test_second_active_repeating_checkin_is_error` → «то же время»),
  `tests/test_mcp_agenda.py`, `tests/test_workload_sync_agenda.py:177`, `tests/test_skills_agenda.py` (тексты,
  лимит 6144), `tests/test_cli_agenda.py` (`event list` с двумя повторяющимися).

Партия 3 — вечер:

- `src/ai_coach/store/migrations/0022_evening_questions.sql` — новая: `ALTER TABLE wellbeing_log ADD COLUMN`
  `work_thoughts`, `hindrance`, `valuable` (CHECK 1–5), `flow` (CHECK 0/1) — как 0016.
- `src/ai_coach/cli/main.py: feel` (:265) — четыре опции; проверку оценок (:277-279) заменить на `check_scores` из
  `cli/journal.py` (появляется в партии 1), иначе `feel` вырастет за порог длины qlty; параметров станет 13 при
  пороге 15 (`.qlty/qlty.toml:62`). Вместе с этим удалить `MIN_SCORE`/`MAX_SCORE` из `main.py:75-76` — после
  переноса проверки они мёртвые; копия живёт в `cli/journal.py` с партии 1 (см. «Правки по ревью»).
- `src/ai_coach/store/journal.py: add_wellbeing` (:157) — docstring; `evening_done` (:169) — без правок.
- `src/ai_coach/mcp_server/server.py:124-128` — описание `get_wellbeing`.
- `.claude/skills/coach-evening/SKILL.md` — п. 2 вопросы, п. 3 опции, п. 4а ритуал закрытия дня; лимит
  `tests/test_skills_evening.py:15` 3072 → 4096 (прецедент: coach-wellbeing 6144 → 7168, v2.8 партия 3, bd739a0).
- `README.md:65`, `docs/architecture.md`.
- Тесты: `tests/test_cli_feel_evening.py`, `tests/test_cli_feel.py`, новый `tests/test_store_migration_0022.py`,
  `tests/test_skills_evening.py`, `tests/test_mcp_wellbeing.py`.

Не трогаем: `load/deviations.py`, `load/overload.py`, `review/service.py`, `mcp_server/snapshot.py` (при Р7 = 1),
`agenda/calendar_write.py` (повтор `daily` уже пишется), `bin/trener`.

## Партии

Три партии — ровно граница риска r1 («больше 3 — резать на Н1а/Н1б», `plan-roadmap-r1.md:81`); не режем. Порядок —
по пользе для данных: день первым (Влад может оценивать уже вручную), потом напоминания (плотность), потом вечер.
Каждая партия самодостаточна: своя миграция, свой коммит после ревью и тестов, аудит по коммиту (память проекта).
Внутри партии — порядок family.md: кабан-доеба (TDD, красные тесты) → кабан → `make check` → ревью, аудит → коммит →
проверка Влада.

1. **День** — `0021_focus_log.sql`, `store/journal.py`, `cli/journal.py`, `mcp_server/tools.py`, `server.py`,
   `settings.json`, `coach.md`, README, architecture. На выходе: `uv run coach focus 4 2 3` → «Оценка записана»,
   `uv run coach log focus` показывает строку, `get_focus_log` отдаёт её. Объём: ~120 строк кода, ~150 строк тестов
   (ожидание, не проверено). После партии — перезапуск MCP.
2. **Напоминания** — `store/agenda.py`, `agenda/service.py`, тексты MCP, `coach-agenda.md`, тесты. На выходе: тренер
   по просьбе ставит 2–3 черновика `checkin daily` на разное время; `coach event write` кладёт их в календарь;
   `coach sync` их не снимает. Объём: ~25 строк кода, ~300 Б промпта, ~8 тестов (ожидание, не проверено).
   Запись в календарь — руками Влада после партии.
3. **Вечер** — `0022_evening_questions.sql`, `cli/main.py`, `coach-evening/SKILL.md`, лимит теста, README,
   architecture. На выходе: `тренер вечер` задаёт новые вопросы, `coach feel … --thoughts 4 --flow --hindrance 2
   --valuable 4` пишет их, `get_wellbeing` отдаёт. Объём: ~30 строк кода, ~400 Б промпта, ~12 тестов (ожидание,
   не проверено).

## Тесты (кабан-доеба)

Партия 1:

- Миграция 0021: `schema_version >= 21`; колонки `id, date, logged_at, focus, fatigue, effort, text`; `focus=0` и
  `6` → `IntegrityError`; индекс по `date`.
- `coach focus 4 2 3` при 12:00 → одна строка `focus_log` с `date` = сегодня, `logged_at` = сейчас (`fake_clock.freeze`),
  `text` NULL; `coach focus 4 2 3 "устал после созвона"` → `text`; при 03:59 → `date` = вчера, при 04:00 — сегодня.
- Плохие значения (`0`, `6`, `abc`, `3.5`, нет третьей цифры при Р3 = 1) → код ≠ 0, таблица пуста; в Garmin не
  ходит (образец `no_network` в `tests/test_cli_feel_evening.py:25`).
- `coach log focus` без записей → «Записей нет.»; с записями → строки `id  время  фокус/усталость/усилие  текст`;
  `--date` фильтрует; плохая дата → код ≠ 0.
- `get_focus_log(from, to)` → `{rows, truncated}`, самые новые при обрезке; период > 92 дней → `ToolError`.
- `settings.json` содержит `Bash(uv run coach focus:*)`; `coach.md` упоминает `focus`; `coach.md` ≤ 15360 Б.
- `get_morning_snapshot` не содержит ключа `focus_*` (при Р7 = 1) — снапшот не растёт.

Партия 2:

- Два активных `checkin daily` на разное время → второй проходит `validate_draft` (сейчас ошибка — красный тест
  на HEAD, ожидание); то же время (`11:00`, день другой) при статусе draft или written → `AgendaError`; то же
  время при cancelled/removed → ок.
- `agenda_rows(from, to)` при двух повторяющихся с `date < from` → обе в начале, по `start_at`; `get_agenda` и
  `coach event list` показывают обе.
- `sync_workload`: два повторяющихся written, в календаре остался один → `removed_by='calendar'` только у
  пропавшего (`tests/test_workload_sync_agenda.py:177` — расширить).
- MCP `create_draft_event(kind=checkin, repeat=daily)` второй раз на другое время → `draft_id`; `{"repeat": "daily"}`
  у `task` по-прежнему ошибка (`tests/test_mcp_agenda.py:61`).
- Тексты: `server.py` и `mcp_server/agenda.py` не содержат «один на всех»; `coach-agenda.md` содержит «focus» и
  ≤ 6144 Б.

Партия 3:

- Миграция 0022: четыре колонки; старые строки живы; `work_thoughts=6`, `flow=2` → `IntegrityError`.
- `coach feel 3 --thoughts 4 --flow --hindrance 2 --valuable 4` → сохранено; `--no-flow` → `flow=0`; без опций →
  NULL (существующие тесты `test_feel_without_options_*` дополнить); плохое значение → код ≠ 0, ни записи, ни
  счётчиков часов (образец `test_bad_mood_stress_is_rejected_and_nothing_saved`).
- `evening_done` не меняется: `feel 3 --thoughts 4` без mood/stress → `evening_done_today` false (умолчание 10).
- `get_wellbeing` и snapshot `wellbeing` отдают новые ключи; snapshot в лимите (`tests/test_mcp_snapshot.py`).
- `SKILL.md` ≤ 4096 Б, содержит `--thoughts`, `--flow`, `--hindrance`, `--valuable`, «туду» (ритуал), «не знает —
  пропусти» остаётся; `coach.md` ≤ 15360 Б.
- `find_deviations`, `find_overload`, `weekly_review` на записях с новыми полями — результат тот же, что без них.

Проверка руками (Влад): `uv run coach focus 4 2 3` → «Оценка записана», `uv run coach log focus` — строка;
`тренер` → «поставь напоминания о дневных оценках» → 3 черновика (id, время, заголовок) → «да» → `coach event write`
→ в Calendar.app и на iPhone три ежедневных события с будильником, вечернее напоминание на месте; `uv run coach sync`
→ события не помечены снятыми; `тренер вечер` → после настроения/стресса/часов — новые вопросы одним окном и
вопрос «что осталось и с чего начнёшь завтра»; `get_wellbeing` за сегодня — поля заполнены.

Для mutmut (`модуль:функция` — TESTS по `grep -l`):

- `cli.journal:focus` (новая), `cli.journal:log_focus` (новая), `store.journal:add_focus` (новая),
  `store.journal:list_focus` (новая), `mcp_server.tools:focus_log` (новая) — TESTS: новые файлы партии 1.
- `agenda.service:validate_draft` — `tests/test_agenda_service.py`, `tests/test_mcp_agenda.py`;
  `agenda.service:agenda_rows` — `tests/test_mcp_agenda.py`, `tests/test_cli_agenda.py`;
  `store.agenda:active_repeats` (переименование `active_repeat`) — `tests/test_agenda_service.py`;
  `sync.workload_sync:vanished` — `tests/test_workload_sync_agenda.py`.
- `cli.main:feel` — `tests/test_cli_feel.py`, `tests/test_cli_feel_evening.py`, `tests/test_cli_feel_after_midnight.py`;
  `cli.journal:check_scores` (новая) — те же плюс `tests/test_cli_focus.py`.

## Развилки и риски

Видимое Владу — развилки, решает Влад. Первый вопрос — блокирующий для партии 1.

- **Р3. Форма команды дневной оценки.** (1) `coach focus <фокус> <усталость> <усилие> ["текст"]` — три обязательные
  цифры 1–5 по порядку: фокус, умственная усталость, «трудно заставить себя» (BACKLOG 16). (2) Опции
  `--focus --fatigue --effort`, любая пропускаема. Рекомендую (1): три раза в день короче набирать `coach focus 4 2 3`;
  строки полные — профилю Н9 не нужны дыры; «не знаю» = не отвечать вовсе. Разблокирует партию 1.
- **Р2. Канал ответа на напоминание.** (1) CLI `coach focus` из терминала (без Claude, 5 секунд, бесплатно); если
  сессия `тренер` открыта — тренер выполняет ту же команду по фразе «фокус 4 2 3» (в allow). (2) Только через
  тренера. Рекомендую (1): сессия `тренер` начинается с `coach sync` и стоит денег (Opus) — для трёх цифр дорого
  и долго; r1 Решение 2 допускает оба.
- **Р1. Сколько напоминаний и когда.** Рекомендую 3, ежедневно, включая выходные: около 11:00, 15:00, 18:00. По живой
  базе утренняя запись `feel` идёт в 09–13 (сессия тренера), вечерняя — 23–01; три дневные точки плюс вечер дают
  четыре отметки суток для профиля Н9 (cosinor-минимум — плотные оценки, `plan-roadmap-r1.md:43`). Вариант — 2
  (например 12:00 и 17:00): меньше дёрганья, грубее профиль. Без выходных нельзя: `repeat` только `daily`
  (`agenda/service.py:28`), недельный повтор — новый код, в Н1 не берём. Времена в черновики ставит тренер по
  словам Влада — менять можно без кода (remove + новый черновик).
- **Р4. Вид напоминания в календаре.** Рекомендую: `kind=checkin`, заголовок «Фокус 1–5?», 5 минут, `alarm_min=0`,
  заметка — команда `coach focus <фокус> <усталость> <усилие>` без личного текста; вечернее напоминание как было.
  Альтернатива — без заметки (чище календарь, команду помнить самому).
- **Р5. Вопросы вечера.** (1) Четыре: «думал ли вечером о работе 1–5» (`--thoughts`, 5 — всё время), «был ли отрезок
  полного погружения» (да/нет, `--flow/--no-flow`), «сколько дня ушло на помехи 1–5» (`--hindrance`), «сколько
  сделанного было ценным 1–5» (`--valuable`) — BACKLOG 23 и 20, research-brain п. 2, 17, 9, 3. (2) Три — без
  «погружения» (прокси — длинные отрезки AW в Н8). Рекомендую (1): одно окно `AskUserQuestion` (до 4 вопросов),
  каждый пропускаем («не знает — пропусти» как сейчас); цена — один лишний экран вечером. Имена опций — там же,
  возражения принимаются.
- **Р6. Ритуал закрытия дня (BACKLOG 23).** (1) Тренер в конце чек-ина спрашивает «что осталось и с чего начнёшь
  завтра» и просит записать в туду самому; в базу не пишет — туду `~/.claude/todo.json` чужого формата
  (`plan-roadmap-r1.md:194`), писать туда нельзя. (2) Сохранять ответ текстом (колонка `tomorrow` в `wellbeing_log`).
  Рекомендую (1): эффект ритуала — выгрузка в план (research-brain п. 14), хранить незачем; понадобится — Н13 читает
  туду.
- **Р7. Что тренер делает с новыми данными в Н1.** (1) Ничего — только собирает (режим наблюдения, NOTES
  2026-10-31): дневные оценки видны `coach log focus` и `get_focus_log`, вечерние — в `get_wellbeing` и snapshot
  `wellbeing`; в итоге чек-ина не упоминаются. (2) Строка в вечернем итоге «днём: фокус 4/3/2, усталость 2/3/4».
  Рекомендую (1); реакция и пороги — v2.9, Н6, Н9.

Риски:

- Усталость от опросов: +3 дневных команды и +4 вопроса вечером. Ранний признак К1 (~2026-11-21): заполнено < 60 %
  дневных оценок → урезать до 1 в день (сценарий «негативный», `plan-roadmap-r1.md:105`); Н2 (PVT) ставить
  только после того, как Н1 прижился (r1 «Зависимости»).
- Лимиты промптов: coach-evening 147 Б запаса → лимит 4096 (умолчание 11); coach-agenda.md 602 Б, coach.md 971 Б —
  кабан меряет `wc -c` после правки, при нехватке — вынос в файл по образцу `coach-morning/*.md` (новая строка в allow).
- `feel`: 13 параметров (порог 15) и длина — помощник `check_scores`; `make smells` при `SMELLS_MAX=0`.
- Snapshot `wellbeing`: +4 ключа × до 60 строк — рост ~1–2 КБ (ожидание, не проверено); обрезка по `MAX_CHARS`
  работает, но проверить `tests/test_mcp_snapshot.py`.
- Напоминание пришло, Mac рядом нет — ответить нельзя (CLI), оценка пропускается по замыслу (состояние момента,
  `--at` нет). Если пропусков много — вопрос в бэклог, не Н1.
- `agenda` в snapshot получит +2–3 строки ежедневно — cap 20 строк (`SNAPSHOT_ROWS`), терпимо; `AGENDA_FIELDS` не
  меняем.
- Дата дневной оценки по `wellbeing_day` (до 04:00 — вчера) — одинаково с `feel`; оценки позже полуночи редки.
- Переименование `active_repeat` → `active_repeats` трогает три модуля; `vanished` уже работает списком — риск
  только в `agenda_rows` (порядок вставки).

## Умолчания (внутреннее)

1. `focus_log`: `id INTEGER PK, date TEXT NOT NULL, logged_at TEXT NOT NULL, focus/fatigue/effort INTEGER NOT NULL
   CHECK 1–5 (при Р3 = 1; при Р3 = 2 — NULL-able), text TEXT`; индекс `focus_log_date`. Имя таблицы и колонок не
   видны Владу.
2. Дата — `wellbeing_day(now)`; `--at` нет; записи только добавляются (как `wellbeing_log`).
3. Команды `focus` и `log_focus` — в `cli/journal.py` (там `weight`, `food`, `log_*`); регистрация в `main.py` как
   `weight`. Вывод `log focus`: `id  logged_at  фокус/усталость/усилие  текст`.
4. `get_focus_log(date_from, date_to)` — как `get_wellbeing`: `period` ≤ 92 дней, `cap(newest=True)`; в snapshot не
   добавляется (при Р7 = 1).
5. `active_repeats(conn) -> list` (`ORDER BY start_at, id`); `agenda_rows` вставляет в начало все с `date < date_from`,
   в том же порядке.
6. Дубль — одинаковый `start_at[11:16]` среди draft/written; cancelled/removed не считаются; сообщение
   «Повторяющийся чек-ин на HH:MM уже есть (черновик или в календаре).»
7. Напоминания — `kind=checkin`: CHECK 0019 разрешает `repeat` только ему; новый kind — перестройка таблицы
   (SQLite не меняет CHECK), в Н1 не берём.
8. Колонки вечера NULL-able, без NOT NULL — старые строки живы (как 0016); `flow` INTEGER CHECK (0, 1).
9. Две миграции — 0021 `focus_log` (партия 1), 0022 вечер (партия 3); при смене порядка партий номера — по порядку
   выполнения.
10. `evening_done` (mood или stress), `main_wellbeing`, `find_deviations`, `find_overload`, `weekly_review` — без
    правок (при Р7 = 1).
11. Лимит `coach-evening/SKILL.md` 3072 → 4096 Б в `tests/test_skills_evening.py:15`.
12. `check_scores(pairs: Iterable[tuple[str, int | None]])` — в `cli/journal.py` рядом с `fail` и `check_date`
    (их `main.py` уже импортирует оттуда — без циклического импорта); им пользуются `feel` (партия 3) и `focus`
    (партия 1 — там он и появляется).
13. Коммит после каждой партии; `docs/pipeline.md` — строка на партию (AGENTS.md), пишет оркестратор.

## Правки по ревью

- 2026-10-31, партия 1 (кабан): `MIN_SCORE`/`MAX_SCORE` продублированы в `cli/journal.py` рядом с `check_scores`,
  в `main.py:75-76` оставлены для `feel`. Папа: в границе партии; дубль временный — снимается в партии 3 (пункт
  `cli/main.py: feel` выше). Направление импорта `main → journal` цикла не даёт (так уже идут `fail`, `now`,
  `check_date`), так что переезд констант возможен и сейчас, но не нужен: `main.py` и так держит свои копии `fail`
  (:80) и `now` (:85) до партии 3.
- 2026-10-31, партия 1 (мама №1): docstring `cli/journal.py` и help `log_app` дополнены дневными оценками.
  Повтор мамы: пропала подсказка «(id для правки)» — кабан вернул её по варианту мамы: «(id веса и еды — для
  edit/delete)», у оценок правки нет. Решение мамы, не Влада; пунктов BACKLOG нет.
- 2026-10-31, партия 2 (кабан, отступления от плана). (а) `README.md:68` — ошибка плана: на HEAD плана 03ca02c
  в README нет текста про «один повторяющийся» (`grep -n -i 'повторя\|один на' README.md` пуст и на 03ca02c, и
  сейчас); строка в п. «Тексты» снимается, правка README не нужна. (б) `docs/architecture.md` — в границе партии 2
  (план: `agenda_rows` в «Модули» партии 2, `architecture.md:202` в «Текстах»), правит кабан партии 2 до коммита:
  `:201` `active_repeat` → `active_repeats` (функция переименована, старого имени в коде нет), `:202` в описании
  `agenda_rows` «активный повторяющийся» → «активные повторяющиеся» (как docstring `agenda/service.py:206-207`).
  Тестов на architecture.md нет — проверка глазами на ревью.
- 2026-10-31, партия 1 (аудит после коммита 7cd20dc): во frontmatter `tools:` `.claude/agents/coach.md:5` нет
  `mcp__ai-coach__get_focus_log` — пробел плана (план назвал `coach.md:10`, список команд Bash, и не назвал :5),
  не следствие Р7. Р7 = «не реагирует» — про поведение (нет в итоге чек-ина и в snapshot), а не про доступ: в Р7(1)
  записано «дневные оценки видны `coach log focus` и `get_focus_log`», и без строки во frontmatter инструмент
  тренеру недоступен вовсе. Прецедент проекта: новый MCP-инструмент и строка в `tools:` — одним коммитом
  (`get_agenda` — f8abc13, `get_habit_log` — 70809e8). Сверка: инструментов в `server.py` 41, в `coach.md` 40,
  разница ровно `get_focus_log`. Правка — в партию 2 (текущую, до коммита; если уже закрыта — отдельным коммитом
  «Н1 партия 1, правка по аудиту», не в партию 3): (1) `coach.md:5` — `, mcp__ai-coach__get_focus_log` после
  `get_wellbeing`; размер 14573 Б (`wc -c`) + 30 Б — в лимите 15360; (2) регресс в текущую партию (правило 9):
  тест в `tests/test_skills_text.py` рядом с `test_skill_tools_mentioned_in_files_are_in_allowed_tools` —
  `tool_names(conn)` (`tests/mcp_fakes.py:18`) ⊆ имена `mcp__ai-coach__*` из `agent_tools()`; на HEAD красный
  (`get_focus_log`), после правки зелёный — проверено скриптом сравнения множеств. Поведение тренера не меняется:
  инструмент читается только по просьбе Влада, в итог чек-ина и snapshot не входит (Р7 = 1 в силе).
- 2026-10-31, партия 2 (мама, необязательное): `tests/test_skills_agenda.py::test_agenda_file_mentions_focus` —
  `"focus" in text` заменён проверками `"coach focus"` и `"Фокус 1–5?"` (Р1, Р4); правил доеба. Решение мамы,
  не Влада; пунктов BACKLOG нет.

## Открытые вопросы

1. Р3 — форма `coach focus` (`src/ai_coach/cli/journal.py` — новая функция); рекомендую (1); разблокирует партию 1;
   решает Влад. Блокирующий.
2. Р2 — канал ответа; рекомендую (1); разблокирует текст `coach.md:10` и `coach-agenda.md`; решает Влад.
3. Р1 + Р4 — сколько, когда, как выглядит (`agenda/service.py:109-114` — правило); рекомендую 3 × daily, 11/15/18,
   «Фокус 1–5?» 5 мин, alarm 0, заметка с командой; разблокирует партию 2 и запись в календарь; решает Влад.
4. Р5 — состав вопросов вечера (`cli/main.py:265 feel`); рекомендую (1) четыре; разблокирует партию 3; решает Влад.
5. Р6 — ритуал без записи в базу; рекомендую (1); разблокирует текст скилла; решает Влад.
6. Р7 — режим наблюдения (`mcp_server/snapshot.py` не трогаем); рекомендую (1); решает Влад.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план Н1 (3 партии) — постоянные расходы после шага и прогон цепочки. Тариф metrics.py от
2026-10-25 (https://platform.claude.com/docs/en/about-claude/pricing, страницу не сверял); fable — по ценам Opus.
База масштаба — «Итог» docs/plan-26-weight.md (правка ~10 строк, $6,94); Н1 — ~175 строк кода + ~450 строк тестов
и ~700 Б промптов в 3 партиях: kaban/doeba ×5–8, ревью/аудит ×3 захода, оркестратор ×2.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Дневные оценки, Р2 = 1 (CLI `coach focus`) | 0 | локальный SQLite, без LLM | — | — | — |
| Дневные оценки, Р2 = 2 (только через тренера, Opus) | ~45–90 | 3 ответа/день × 30 × $0,5–1 за сессию с `coach sync` (допущение) | Р2 = 1 | весь | ничего по данным; ответ — только с Mac |
| Вечер +4 вопроса | ~0,5–1 | +1 экран AskUserQuestion, +2–3K токенов × 30 вечеров | Р5 = 2 (три вопроса) | копейки | признак «погружения» |
| Календарь iCloud, напоминания | 0 | существующий поток v2.6 | — | — | — |
| Snapshot +1–2 КБ | <0,5 | чтение кэша Opus, 1–2 сессии/день | — | — | — |

| Партия | Время |
|---|---|
| 1. День (миграция, CLI, MCP, тексты) | ~35–50 мин (doeba ~10, kaban ~20, ревью+аудит ~8, правки) |
| 2. Напоминания (~25 строк, 8 тестов) | ~25–35 мин |
| 3. Вечер (~30 строк, 12 тестов, скилл) | ~25–40 мин |
| Декарт (3 + 1 сводный) + тесть р.3 | ~15–25 мин |
| Влад: Р1–Р7, «да» на календарь, проверки | не считаю (простой) |

| Роль | Модель | Токены (оценка, cache read) | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| papa-kaban — уже прошло (a0d9be3b1f6e3607a) | fable | 1,23M | 1,91 |
| orchestrator | opus | ~12M | 6–8 |
| kaban ×3 | sonnet | ~2–3M | 1,7–2,7 |
| kaban-doeba ×3 | sonnet | ~2–3M | 1,6–2,6 |
| mama-kaban ×3 | opus | ~0,5–0,8M | 1,1–1,8 |
| kaban-svekrov ×3 | opus | ~1,3–1,8M | 1,8–2,4 |
| kaban-dekart ×4 | fable | ~6–7M | 4–6,6 ($1,66/вызов — факт Ш8 семьи, верх) |
| kaban-test р.3 (свой р.1 не включён) | opus | ~0,1M | 0,4 |
| svinopas, kaban-shurin | opus | не в плане | 0 |
| **итого** | | | **~19–28** (нижняя граница ≥ уже прошло 1,91) |

Модели (`grep -H '^model:'`): kaban, kaban-doeba — sonnet; mama-kaban, kaban-svekrov, kaban-test, svinopas,
kaban-shurin — opus; kaban-dekart, papa-kaban — fable. Свой запуск — opus-5-5, совпадает.

**Дешевле в прогоне:** Декарт один сводный вызов вместо 4 — −$3–5, теряем разбор по партиям; оркестратор —
`/compact` между партиями (−$1–2, без потерь). Ревью и аудит не трогаю.
**Вердикт:** ок по бабкам при Р2 = 1 (постоянных расходов ~0). Р2 = 2 — +$45–90/мес, дорого: рекомендация папы
(1) совпадает и с деньгами.

## Итог

Заполняется при закрытии шага (закрытые пункты беклога, стоимость — тесть, проблемы).
