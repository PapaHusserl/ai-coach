# Шаг v2.8. Экранное время как источник нагрузки

Закрывает BACKLOG 5. План — папа-кабан, 2026-10-27, по итогам спайка v2.7 ([research-screen.md](research-screen.md)
«Досчёт и финальный вердикт», [plan-v2.md](plan-v2.md) «Шаг v2.7») и решениям Влада по развилкам Р1–Р4. В код —
после шага 24. v2.9 (BACKLOG 3) — после этого шага, калибровка уже с экраном в данных.

## Суть

Экран (ActivityWatch на Mac) становится вторым источником часов работы и хобби. `coach sync` (и новая команда
`coach screen` для вечера) читают из aw-server только агрегаты по категориям за дни окна и кладут их в
`day_counters` (`source='screen'`, kind `screen_*`); `hours()` берёт ручные > экран > календарь; вечерний чек-ин
показывает подсказку «экран насчитал …». Заголовки окон и названия приложений в базу, ответы MCP и репо не идут
(решения v2.7 (2), (17)); правила разметки живут в конфиге вне репо.

**Правило:** было `manual if manual is not None else (day.get(key) or 0)` (`load/overload.py:50-53`, `hours`) →
станет `manual if manual is not None else (screen if screen is not None else (day.get(key) or 0))`, где
`screen = day.get(f"screen_{key}")` (`screen_work_hours`, `screen_hobby_hours`); 0 экрана — значение, как 0 ручных.
Второе: было `int(c["value"])` для всех счётчиков (`workload/service.py:93`, `_rows`) → станет `int` только для
целых kind (`todo_*`, `grooming_*`), часы экрана — `float`.
**Поведение:** меняется — в дни без `coach feel --work/--hobby` `total_load`, `weekend_work` (`find_overload`),
`workload_ahead[].overloaded` и недельный обзор (`review/service.py:124,126` — `work_hours`, `weekend_work_hours`)
берут часы экрана вместо календарных; `get_workload` и snapshot `workload` получают поля `screen_*`;
`coach sync` — новый источник (ошибка AW не прерывает остальное); вечерний чек-ин — подсказка по экрану.
Календарные часы остаются по дню 00–24, ручные и экранные — 04:00→04:00 (v2.7 решение 7, v2.3а).
**Вне репо:** ActivityWatch (стоит с 2026-10-12, Login Items) — секция `[screen]` в
`~/.config/ai-coach/workload.toml` с переносом правил из `spikes/out/screen_rules.toml` — Влад (партия 3);
правила партии 1 (`[meeting].apps`, Obsidian) — Влад в `screen_rules.toml`.

## Решения (Влад, 2026-10-27, по развилкам research-screen.md «Развилки Владу»)

1. **Р1** = (1): экран — второй источник часов; в `hours()` приоритет manual > screen > calendar для work и hobby;
   счётчики экрана в `get_workload`; в вечернем чек-ине подсказка «экран насчитал N ч, записать?».
2. **Р2** = (1): окна приложений созвонов считаются за экраном и во время afk (секция `[meeting].apps`,
   объединение с not-afk отрезками в запросе AW).
3. **Р3**: Obsidian → work (16-е правило при мягком лимите ~15); `~/projects/…` (в том числе семья кабанов) в
   рабочие часы — hobby, как сейчас (правило 19.10, решения v2.7 (14), (22), остаётся).
4. **Р4** = (1): браузер — отдельным счётчиком, в work не входит; пересмотр после партии 1 по колонке «+брауз».
5. 18.10 (вс), ручные 4,0 ч при экране 0,3 ч — не ошибка записи: работа была за другим компьютером. Вывод для
   плана: работа вне этого Mac бывает, её покрывают ручные часы (manual > screen); отдельной логики не нужно.
6. Умолчания (внутреннее) — приняты целиком (Влад, 2026-10-27).
7. **Р5–Р8** — приняты рекомендации папы (Влад, 2026-10-27): Р5 = (1), Р6 = (1), Р7 = (2), Р8 = (3).
8. **Р4 после партии 1** — браузер остаётся отдельным счётчиком, как принято (Влад, 2026-10-27; цифры — research-screen.md «Партия 1 v2.8»).

## Модули, файлы, функции

Существующие (найдены grep-ом):
- `load/overload.py` — `hours` (:50): правило выше; `day_entries`, `total_load`, `find_overload` — без правок
  (экран приходит в строке `workload_series`); `overload_report` (:163) — поля `days` по Р5.
- `workload/service.py` — `COUNTERS` (:17) + kind экрана; `_rows` (:89) — `float` для часов экрана.
- `store/workload.py` — `COUNTER_KINDS` (:10) + kind экрана (`upsert_counter` :73 их пропускает).
- `workload/config.py` — `WorkloadConfig` (:21) + поле `screen: ScreenConfig | None`; `load_config` (:102) —
  разбор `[screen]`; новые `ScreenConfig`, `_screen`.
- `workload/__init__.py` — экспорт `ScreenError`, `ScreenReader`, `AwReader`, `read_screen`.
- `sync/workload_sync.py` — `sync_workload` (:120): четвёртый источник после груминга; параметр `screen:
  ScreenReader | None = None` для подмены в тестах (как `reader`).
- `cli/main.py` — `sync` (:111) без правок; новая команда `screen`.
- `mcp_server/tools.py` — `AHEAD_SKIP` (:93) + kind экрана; `mcp_server/server.py` — описания `get_workload`
  (:66), `get_overload` (:76), `INSTRUCTIONS` (:26); `mcp_server/workload.py` — докстринг.
- `review/service.py` — `_has_data` (:71): день только с экраном — день с данными (`days_with_data`).
- `.claude/settings.json` — allow `Bash(uv run coach screen:*)`; `.claude/skills/coach-evening/SKILL.md`
  (3066 Б из 3072, `wc -c` 2026-10-27 — запас 6 Б, текст придётся ужимать); `.claude/agents/coach-wellbeing.md`
  (6017 Б из 6144 — запас 127 Б); `coach.md` (14152 Б из 15360) — по возможности не трогать.
  Лимит `coach-wellbeing.md` — **7168 Б** (решение папы 2026-10-27 по решению Влада «поднять лимит и вернуть
  фразы»). Откуда прежний: 6144 = 6 КиБ, задан в v2.1 (коммит 0acfd58, `test_coach_wellbeing_exists_and_is_short`)
  как круглая планка «короткого» файла, который `coach.md` читает `cat` по триггеру — цена одного триггера в
  контексте, не измерение. Почему 7168: с возвращёнными фразами файл — 6380 Б (измерено: 6123 + 257 Б семи фраз
  из аудита), 7 КиБ оставляет 788 Б — на один шаг v2.9 (пороги после калибровки); 8 КиБ удвоил бы запас и
  приглашал бы расти. Остальные четыре файла роли — по-прежнему ≤ 6144 (все ≤ 6033 Б, `wc -c` 2026-10-27).
  Правка лимита: `tests/test_skills_workload.py:10`, `tests/test_skills_agenda.py:72`,
  `tests/test_skills_practices.py:12,29`; `docs/architecture.md:196` («каждый ≤ 6144» → wellbeing 7168).
- Спайк (партия 1): `spikes/screen/common.py` — `load_rules` (:156), `screen_query` (:77), `classify` (:188),
  `QUERY_HEAD` (:51); `aw_compare.py` — без правок.

Новые:
- `workload/screen.py` — `ScreenError`; `ScreenReader` (Protocol, `fetch(periods) -> list[dict[tuple[str, str],
  float]]`, как `EventReader`); `AwReader(config)` — `screen_query(config)` (перенос из спайка: окна ∩ (not-afk ∪
  окна `[meeting]`), `[screen.title.<app>]` размечает сервер `categorize`, слияние по `(app, $category)`),
  `_query_literal`, POST `/api/0/query/` с таймаутом, читает из ответа только `app` и `$category`;
  `read_screen(reader, config, first, last) -> tuple[list[dict], list[str]]` — строки для `upsert_counter` и
  замечания (неразмеченное > 15 %) по дню 04:00→04:00 и
  вечеру 19:00→04:00, `source='screen'`, `raw_json` None; `by_category` (work/hobby/browser/unmarked; app из
  `[meeting]` без другой разметки → work).
- Тесты: `tests/test_workload_screen.py`, `tests/test_cli_screen.py`; `FakeAw` в `tests/workload_fakes.py`.

## Партии

1. **Спайк, те же данные AW** (`spikes/screen/common.py`, правила Влада, без продакшен-кода).
   `load_rules` — секция `[meeting] apps = [...]` (в нижний регистр, как остальные; вне лимита ~15, как
   браузер); `screen_query` — `QUERY_HEAD` становится `notafk = filter_keyvals(afk, "status", ["not-afk"]);
   meet = filter_keyvals(window, "app", [...]); active = period_union(notafk, meet); events =
   filter_period_intersect(window, active);` — `period_union` в query2 aw-server v0.14.1 есть, запрос проходит
   (проверено 2026-10-27 на живом AW, 6 ч, в ответе только сумма секунд); без `[meeting]` запрос прежний.
   `classify`: app из `[meeting]` без другой разметки → work. Влад: `aw_day --date D --apps` (только tty) →
   приложения созвонов в `[meeting].apps`, Obsidian в `[work].apps`. Прогон `aw_compare --days N` так, чтобы
   окно покрыло 13–26.10 (на 2026-10-28 — `--days 15`); итог — новый раздел research-screen.md «Партия 1 v2.8»:
   та же таблица, средний |Δ|, > 1 ч, > 2 ч без браузера и с ним, без названий. Критерий из вердикта: средний
   |Δ| ≤ 1 ч и > 2 ч — 0 → экран может подменять ручные часы в будни без `feel`; не достигнут — Р1 остаётся
   (решение Влада), цифра идёт в v2.9. По колонке «+брауз» — вопрос Владу о пересмотре Р4 до партии 2.
   Проверка: без `[meeting]` вывод `aw_day` идентичен прежнему; с `[meeting]` итог дня ≥ прежнего.
2. **Код и тесты (TDD).** `workload/config.py` (`[screen]`: `url` по умолчанию `http://127.0.0.1:5600`,
   `work/hobby/browser/meeting = [app]`, `[screen.title.<app>] work/hobby = [regex]`; ошибки regex, кавычка,
   чужой ключ → `WorkloadConfigError`, как в `load_rules`, но исключением) → `workload/screen.py` →
   `store/workload.py`, `workload/service.py` → `load/overload.py:hours` → `sync/workload_sync.py` →
   `cli/main.py:screen` (`coach screen [--days N]`, по умолчанию 1: только экран → `day_counters`, печатает часы
   по категориям за день самочувствия; `sync_log` не пишет; нет `[screen]` или AW не отвечает → одна строка,
   exit 1) → MCP (`AHEAD_SKIP`, описания) → `review/service.py:_has_data`. На выходе: `make check` зелёный;
   `uv run coach sync` с `[screen]` печатает прежний итог плюс замечания экрана; `uv run coach screen` пишет
   счётчики за сегодня.
3. **Тексты, документы, ручная проверка.** `coach-evening/SKILL.md` — шаг 0 `uv run coach screen`, подсказка по
   Р6 (ужать текст, лимит 3072 Б); `coach-wellbeing.md` — поля `screen_*`, источник часов manual > screen >
   calendar, строка «экран не настроен / не отвечает» в итоге sync; `settings.json` allow; README «Нагрузка вне
   тренировок» (AW, `[screen]`, `coach screen`, приватность); `architecture.md` раздел «v2: экранное время
   (шаг v2.8)» с формулой `hours`; `pipeline.md`; BACKLOG 5 → started в начале шага, done при закрытии.
   Влад: `[screen]` в `workload.toml` (перенос из `screen_rules.toml`), `coach sync`, вечером `тренер вечер`.

## Тестовые сценарии (кабану-доебе, TDD)

- `hours`: manual None, screen 3.0, календарь 7 → 3.0; manual 2, screen 3 → 2; screen 0, календарь 7 → 0;
  screen None → календарь; hobby так же; `total_load({"screen_work_hours": 5})` ==
  `total_load({"work_hours": 5})`; `find_overload` — `weekend_work` по экрану в сб/вс. «Ожидание, не проверено».
- `upsert_counter`: четыре kind экрана принимаются, `screen_foo` → ValueError.
- `workload_series`: `screen_work_hours` 2.25 остаётся 2.25 (не 2); `todo_open` остаётся int; нет счётчика →
  поля `screen_*` None.
- config: нет `[screen]` → `screen` None; app в нижний регистр; `url` по умолчанию; плохая regex, кавычка в
  regex, чужой ключ в `[screen.title.*]`, не-список → `WorkloadConfigError`; битый toml — как раньше.
- `screen_query`: без title и meeting — ровно `QUERY_HEAD` + merge по app; с `[meeting]` — строка
  `period_union`; с title — `categorize` c `(?i)(?:a|b)`, `\\w` в toml доходит как `\w` (однократное снятие
  экранирования), app с title исключены из `rest`. Проверено: `period_union` на живом AW 2026-10-27.
- `read_screen` с `FakeAw`: периоды — на каждый день `[04:00, +1д 04:00)` и `[19:00, +1д 04:00)` по местному
  времени, в этом порядке; секунды по категориям → часы с округлением до 0.01; app из `[meeting]` → work;
  unmarked не хранится; browser отдельно; сумма > длины периода → `ScreenError`; день без событий окон →
  счётчиков нет (Р8); в ответе есть ключ `title` → в строках для базы его нет, `raw_json` None.
- `sync_workload`: `[screen]` + `FakeAw` → строки `source='screen'` за окно `first..today`; `ScreenError` →
  `errors` «экран: …», `status='error'`, туду/груминг/календарь записаны; нет `[screen]` → «экран не настроен»;
  `todo.json` и hb-watch неизменны (есть тест — расширить); один `sync_log` kind `workload`.
- `coach screen`: пишет счётчики за день самочувствия (в 01:00 — вчера, как `coach feel`), печатает часы;
  повторный запуск заменяет значения; AW не отвечает → exit 1 одной строкой; нет `[screen]` → exit 1;
  `sync_log` не меняется (`first_run_today` и `last_sync` прежние).
- MCP: `get_workload` строка содержит `screen_*`; snapshot `workload` — тоже, `workload_ahead` — нет; в JSON
  snapshot и `get_workload` нет подстроки заголовка из `FakeAw`; `get_overload.days` — по Р5; snapshot с 7 днями
  экрана ≤ `MAX_CHARS` («ожидание, не проверено» — рост ~7 строк × 4 поля); `mcp_server` не упоминает
  `AwReader`/`read_screen` (по образцу `test_mcp_no_push`).
- Тексты: `SKILL.md` ≤ 3072 Б, содержит `coach screen` и `screen_work_hours`; allow содержит
  `Bash(uv run coach screen:*)`; `coach-wellbeing.md` ≤ 7168; `coach.md` ≤ 15360.
- Руками (Влад): `uv run coach sync` → в итоге «счётчиков N» больше на 4×дни, замечаний экрана нет;
  `sqlite3 coach.db "SELECT DISTINCT kind, source, raw_json IS NULL FROM day_counters"` — только kind из
  белого списка, `raw_json` NULL; AW выключен → `coach sync` печатает «экран: …», Garmin и календарь записаны;
  `тренер вечер` — подсказка с часами экрана; «да» → `coach feel --work … --hobby …`.

## Развилки и риски

Развилки — раздел «Открытые вопросы» ниже (Р5–Р8). Риски:
- Р2(1) ловит только созвоны, где окно созвона на переднем плане: aw-watcher-window пишет активное окно; если во
  время планёрки в фокусе терминал — минус останется. Проверяется партией 1 по Δ; запасной путь — Р2(2)
  (таймаут afk 10–15 мин), решает Влад по цифре.
- Хобби с экрана — 4–7 ч/день в будни (research-screen.md, таблица 12–18.10) × `W_HOBBY` 0.5 → +2–3.5 к
  `total`; `total_streak` (`TOTAL_HIGH` 10) будет срабатывать чаще — это задача v2.9, в v2.8 веса не трогаем.
- Экран и календарь в `hours()` смешаны по разным дням (04→04 и 00–24) — как уже с ручными; в `architecture.md`.
- Лимиты текстов: `SKILL.md` — 6 Б запаса, без ужимания не пройдёт; `coach-wellbeing.md` — 127 Б.
- Рост snapshot: `MAX_CHARS` 20000 режет самые старые ряды `DATE_SERIES` — не ломается, но проверить тестом.
- AW не отвечает (выключен, обновление macOS) — один источник из четырёх, остальное пишется; `coach screen`
  вечером — exit 1 с подсказкой, скилл спрашивает часы как раньше.
- Несколько хостов в AW — `find_bucket` берёт первый бакет (как в спайке); второй Mac — не в этом шаге.
- `period_union` — функция query2; в aw-server v0.14.1 есть (проверено), при обновлении AW — регресс-риск,
  ловится ошибкой HTTP 400 в sync.

## Умолчания (внутреннее)

- Kind экрана в `COUNTER_KINDS`: при Р5 = (1) — `screen_work_hours`, `screen_hobby_hours`,
  `screen_browser_hours`, `screen_evening_hours`; `source='screen'`; `raw_json` NULL; значение — часы, 2 знака.
- День экрана — 04:00→04:00 местного времени (`EVENING_CUTOFF` из `store/journal.py`), вечер — 19:00→04:00
  (`EVENING_FROM` из `workload/service.py`); один POST на все периоды окна (2 × дней).
- `read_screen` окно в `sync_workload` — `first..today` (то же `days`, что у туду); `coach screen` — `--days 1`.
- `ScreenReader` — Protocol с `fetch(periods)`, подмена через параметр `screen=` (как `reader=`); `FakeAw`
  отдаёт события с `title`, чтобы тесты ловили утечку.
- Секция `[screen]` зеркалит `screen_rules.toml`: `work/hobby/browser/meeting = [app]`, `[screen.title.<app>]`
  с `work`/`hobby` списками regex; порядок классов `("work", "hobby")` — hobby побеждает (решение 18).
  Имена `meeting` и ключи `title` уходят в запрос как в toml (регистр важен); `classify` — через `lower()`.
- `coach screen` не пишет `sync_log` (не синк; `first_run_today` и `last_sync` не трогает).
- `_has_data` в недельном обзоре считает день с `screen_work_hours` днём с данными.
- Замечание sync «неразмеченное N %» — только если > 15 % (критерий спайка); названий в итоге нет.
- Тесты: `tests/test_workload_screen.py`, `tests/test_cli_screen.py`, `FakeAw` в `workload_fakes.py`; mutmut —
  `workload.screen:*`, `workload.config:load_config`, `workload.config:_screen` (новая), `load.overload:hours`,
  `workload.service:_rows`, `store.workload:upsert_counter`, `sync.workload_sync:sync_workload`,
  `cli.main:screen` (новая).

## Уточнения по партии 2 (папа-кабан, 2026-10-27, вопросы кабана)

1. `AwReader(config: ScreenConfig)`, а не `url`: запросу нужны правила — принято.
2. `read_screen` замечание «неразмеченное N %» (> 15 %) — возвращать `(rows, notes)`, как `stored_events` и
   `read_calendar` в `sync/workload_sync.py`; изменяемый параметр `notes=None` — не в стиле модуля.
3. `screen_evening_hours` = всё экранное 19:00→04:00, с браузером и неразмеченным — принято (Р5 = (1)).
4. `coach screen --days N` печатает только день самочувствия, остальные дни пишет молча — принято.
5. Чужие ключи прямо в `[screen]` не отклоняются — принято: так же ведут себя `[calendar]` и `[paths]`
   (`config.py` читает только известные ключи); в `[screen.title.*]` чужой ключ — ошибка, как в спайке.
6. `[meeting]`: в запрос (`filter_keyvals`, точное совпадение на сервере) — имена как в toml, регистр важен
   (как ключи `[title.<app>]` в спайке); `classify` — через `lower()`, как остальные секции — принято.

## Открытые вопросы

1. **Р5. Состав счётчиков экрана** (видно в `get_workload`, snapshot, `get_overload.days`;
   `store/workload.py:10`, `load/overload.py:163`). Варианты: (1) `screen_work_hours`, `screen_hobby_hours`,
   `screen_browser_hours`, `screen_evening_hours` (всё за экраном 19:00→04:00, с браузером) и в
   `get_overload.days` рядом с `manual_*` — `screen_work_hours`, `screen_hobby_hours`; (2) то же плюс
   `screen_work_evening_hours` и `screen_unmarked_hours`; (3) только work и hobby. Рекомендую (1): work/hobby
   нужны `hours()`, браузер — для пересмотра Р4, вечер — сигнал из BACKLOG 5; тренеру в `days` нужно видеть,
   откуда `total`. Разблокирует: партию 2 (белый список kind, тесты). Решает: Влад. Блокирующий.
2. **Р6. Подсказка в вечернем чек-ине** (`coach-evening/SKILL.md`, `cli/main.py`). (1) Скилл перед snapshot
   запускает `uv run coach screen` (новая команда, в allow), затем в вопросе про часы: «экран: работа N ч, хобби
   M ч, браузер K ч — записать так?»; «да» → `coach feel --work N --hobby M`; AW не ответил — вопрос как сейчас;
   (2) без свежего чтения — цифры утреннего sync (за сегодня почти ноль, подсказка бесполезна). Рекомендую (1).
   Разблокирует: партию 3 и команду `screen` в партии 2. Решает: Влад.
3. **Р7. Экран в вечерний сигнал** (`load/overload.py:65,127` — `W_EVENING`, `evening_streak`). (1)
   `screen_work_evening_hours` — второй источник `work_evening_hours` (экран > календарь); порог `> 0` сработает
   от 15 мин работы вечером — по данным спайка почти каждый день; (2) в v2.8 экран в вечерний сигнал не входит,
   порог и вес — v2.9. Рекомендую (2). Разблокирует: состав Р5 (нужен ли `screen_work_evening_hours`). Решает: Влад.
4. **Р8. День без событий окон** (AW не работал, Mac выключен; `workload/screen.py`, новая). (1) писать 0 →
   `hours()` даст 0 вместо календаря; (2) писать 0, но в `hours()` 0 экрана = нет данных → календарь; (3)
   счётчики за день не пишутся вовсе → None → календарь, а 0,3 ч экрана при работе за другим компьютером (18.10)
   перекрывают ручные часы. Рекомендую (3): «нет данных» и «0 часов» различимы, работу вне Mac покрывают ручные
   часы (решение 5). Решает: Влад.
5. **Р4, пересмотр** — после партии 1, по колонке «+брауз»: оставить браузер отдельно или считать work в
   рабочие часы будней. Не блокирует партию 1; до партии 2 — ответ Влада.

## Правки по ревью

Партия 1 (ревью мамы-кабана, исправил кабан): имена `[meeting].apps` в `filter_keyvals` — как в toml (`meeting_names`),
`classify` — без регистра; `title_seconds` через `query_head(rules)`; `rules` обязателен. `aw_compare --days 14` после
правок — те же цифры. Для партии 2: тест `[meeting]` с именем в смешанном регистре. Р4 — решение 8.

Партия 2 (вопросы кабана — папа, 2026-10-27): ответы на 6 вопросов — раздел «Уточнения по партии 2» и «Умолчания»;
1, 3–6 приняты, 2 переделан: `read_screen` возвращает `(rows, notes)` вместо out-параметра (исправил кабан); Р5 —
evening = экран 19:00–04:00. Доеба багов в коде не нашла.
Ревью мамы партии 2: `screen_query` — `json.dumps(..., ensure_ascii=False)` (не-ASCII имена приложений), `coach screen
--days` — `min=1` (исправил кабан, тесты — доеба); дубль сверки числа ответов в `AwReader.fetch` оставлен — на неё
опираются тесты (замечание «можно убрать», не блокирует). Аудит свекрови — чисто.

Партия 3 (аудит свекрови, решение Влада 2026-10-27 «вернуть фразы»): в `coach-wellbeing.md` возвращены фразы не про
экран, вырезанные ради лимита («календарь MCP не читает сам», «в новые черновики», «сигнал внимания», «скажи
пользователю», «часть роли тренера»); ужато в других местах, файл 6123 Б из 6144 (исправил кабан). Ревью мамы: строка
«экран: …» — «не отвечает или ошибка» (кабан); тест allow `coach screen` (доеба; тесты лимитов уже были); отступ строки
allow в `settings.json` поправил Влад сам. Сокращения SKILL.md — по плану («текст придётся ужимать»).
Второй круг (аудит свекрови и ревью мамы): новые сокращения меняют смысл — «работа в выходные = …», «веса - в
`load/overload.py`», «или облегчишь», «(если есть)» у сигналов, «включая сегодня». Решение Влада 2026-10-27: поднять
лимит `coach-wellbeing.md` и вернуть фразы; новый лимит — за папой.
Третий круг: папа — лимит `coach-wellbeing.md` 7168 Б («Модули»); кабан вернул все сокращения прошлой правки (файл
6414 Б) и поправил `architecture.md`; доеба — лимит 7168 в тестах только для `coach-wellbeing.md`.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план v2.8 (партии 1–3, решения 1–7). Эталон — «Итог» шага 23 (`docs/plan-23-plank.md`,
4 партии, 35 мин, $3.86); v2.8 по коду крупнее (~10 модулей, 2 новых тестовых файла, mutmut по 8 функциям) —
масштаб ×2 для kaban/kaban-doeba/ревью, допущение. Цены — тариф metrics.py от 2026-10-25
(https://platform.claude.com/docs/en/about-claude/pricing), не сверял со страницей.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| ActivityWatch (aw-server, локально) | 0 | open-source, стоит с 2026-10-12 | — | — | — |
| `coach sync` / `coach screen` (POST в localhost) | 0 | без API и облака | — | — | — |
| Вечерний чек-ин (+1 вызов `coach screen` в скилле) | ~0 | +~0,5K токенов на чек-ин в сессии Влада по подписке | — | — | — |
| Цепочка кабанов на шаг (разово) | ~$7 | см. таблицы ниже | папа уже отработал; остальное — модели по агентам | ~$0,5 при kaban на haiku | качество кода партии 2 (TDD, mutmut) — не советую |

| Партия | Время |
|---|---|
| 1. Спайк (правила Влада, `aw_compare`) | ~15 мин агентов + ручная работа Влада (`aw_day`, разметка) |
| 2. Код и тесты (TDD) | ~40 мин (шаг 23 целиком — 35 мин, здесь кода больше) |
| 3. Тексты, документы, ручная проверка | ~15 мин агентов + проверка Влада |
| ревью/аудит/итог | ~15 мин |

| Роль | Модель | Токены (оценка, cache read / write / out) | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| papa-kaban (уже прошло) | fable | интервал: 1,2–2,5M / 0,3–0,5M / 1–3K, id в agents.md не сверял | 1,7–3,0 |
| kaban | sonnet | ~0,3M / 50K / 1K | ~0,15 |
| kaban-doeba | sonnet | ~0,6M / 0,12M / 5K | ~0,40 |
| mama-kaban | opus | ~0,15M / 45K / 0,2K | ~0,26 |
| kaban-svekrov | opus | ~0,12M / 50K / 0,3K | ~0,28 |
| kaban-dekart (2 вызова: 1 партия + сводный, выжимки ≤ 400 KB) | fable | ~0,2M / 0,2M / 5K | ~1,2 |
| orchestrator | opus | ~5M / 0,2M / 40K | ~2,8 |
| **итого** | | | **~6,8–8,1** |

Варианты дешевле: kaban-doeba/kaban на haiku — экономия ~$0,5, теряем надёжность TDD на парсинге toml/regex —
не советую; оркестратор — `/compact` между партиями (−~$1 на чтении кэша). Ревью, аудит, маму, свекровь не трогаю.
Модели (`grep -H '^model:' ~/.claude/agents/*.md`): kaban sonnet, kaban-doeba sonnet, mama-kaban opus,
kaban-svekrov opus, kaban-test opus, kaban-dekart fable.
Вердикт: ок по бабкам — постоянных расходов нет, шаг разово ~$7.
