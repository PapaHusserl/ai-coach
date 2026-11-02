# Н17. Удаление запланированной тренировки (BACKLOG 28)

Архитектор, 2026-11-02. Контур: вне msa; режим: встроить.

## Суть

Влад хочет убирать запланированную тренировку. Сейчас CLI умеет только `approve` / `push` / `link` / `status`
(`cli/main.py:175-272`), MCP — `cancel_draft_workout` только для `draft` (`mcp_server/tools.py:410`); утверждённую
или отправленную тренер просит «снять на часах самому» (`coach.md:27`, `coach-help/training.md:10`,
`coach-help/sleep.md:18`, `skills/coach-plan/recalc.md:6`). Снятие с Garmin уже умеет `plan/service.py:57
remove_old` (повторный `push`): `unschedule_workout(schedule_id)` → `delete_workout(workout_id)`, при сбое сообщение
называет, что осталось в Garmin.

Шаг — новая команда CLI `coach cancel <id>` в стиле `push` (показ → y/N → Garmin → база) и `event cancel`
(статус `cancelled`), MCP не трогается.

**Правило:** новое (при Р1 = 1, Р2 = 1, Р3 = да):
`plan/service.py` — `cancellable`: `if row["status"] == "cancelled": raise PlanError(...)` (все остальные статусы
отменяемы); `cancel`: `update_planned_workout(conn, id, {"status": "cancelled", "garmin_workout_id": None,
"garmin_schedule_id": None})`; CLI: `if row["status"] == "pushed" and has_old(row): remove_old(client, …)` после
y/N, затем `cancel`. Правило MCP не меняется: `tools.py:416` `if row["status"] != "draft": raise ToolError`
остаётся (при Р5 = 1).

**Поведение:** меняется — новая команда `coach cancel`; тексты тренера, где было «сними на часах сам», говорят
`uv run coach cancel <id>` после «да» (список — «Справка»). `cancel_draft_workout`, `approve`, `push`, `status`
не меняются.

**Вне репо:** нет при Р7 = 1 (`cancel` не в allow, как `approve` и `push` — в `.claude/settings.json` их нет,
проверено grep). При Р7 = 2 — Влад добавляет строку `Bash(uv run coach cancel:*)` (AGENTS.md «Местные правила»).

## Развилка папы 2026-11-01 (перенос по handoff)

Р3 списка папы при встраивании Н15–Н18 в ROADMAP (архитектор, 2026-11-01; в репо не записана, текст — из
транскрипта сессии оркестратора `b2d2785d…jsonl`, запись 2026-11-01T17:01Z): «Р3 (Н17): какие статусы можно
удалять (draft, approved, pushed), удалять строку или ставить cancelled, снимать ли тренировку с календаря Garmin у
pushed с подтверждением y/N. Рекомендую: удалять все три статуса, ставить cancelled, у pushed снимать с Garmin после
y/N». Решения Влада по ней на 2026-11-02 в репо нет (handoff: «в документ каждого шага при старте») — ниже она
разложена на Р1–Р4 этого плана с теми же рекомендациями; остальное (Р5–Р8) — новые развилки из разведки кода.

## Решения

Влад, 2026-11-02, окнами по одному — все по рекомендациям папы:
- Р3: pushed снимать с Garmin (`remove_old`) после y/N.
- Р1: отменяются все три статуса (draft, approved, pushed), любой даты.
- Р2: `status = 'cancelled'`, строка остаётся.
- Р4: y/N только у pushed; draft/approved — сразу.
- Р5: только CLI, MCP `cancel_draft_workout` без изменений.
- Р6: `coach cancel <id>`, один id.
- Р7: allow-строку не добавлять («Вне репо: нет»).
- Р8: подсказки о слоте в календаре коуча нет.

## Справка (правило AGENTS.md)

Новая команда CLI → в том же шаге:

- `.claude/agents/coach-help/training.md` (5 369 Б, лимит 8 192): в «Путь тренировки» строка «Отменить —
  `coach cancel <id>`: черновик и утверждённая — сразу, отправленная — после y/N снимается с календаря Garmin и
  удаляется с часов после синхронизации»; `:10` «Утверждённые и отправленные снимай с часов сам» → «отправленные
  отменяются `coach cancel <id>` после вашего «да»». `test_skills_help.py:404 test_every_cli_command_is_in_help`
  требует `coach cancel` в тексте справки — иначе красный.
- `.claude/agents/coach-help.md:13` (3 986 Б, лимит 6 144): в строку «Тренировки» добавить «отмена».
- `.claude/agents/coach-help/sleep.md:18` (4 792 Б): «утверждённое и отправленное снимаете на часах сами» →
  «отправленное — `coach cancel <id>` после «да»».
- `tests/test_skills_help.py:301 test_training_topic` — needle `"coach cancel"`.

Тексты тренера (не справка, то же правило «функция изменилась — текст в том же шаге»):
- `.claude/agents/coach.md:10` (15 469 Б, лимит 16 384, запас 915 Б) — `cancel` в правило «approve и push только
  после явного «да» на список»; `:27` (8б, красные флаги) «утверждённую или отправленную — попроси снять на часах
  самому» → «утверждённую или отправленную — покажи id и после «да» `uv run coach cancel <id>`». Рост — ожидание,
  не проверено (~100–150 Б); кабану — `wc -c` до и после, лимит из `tests/text_limits.py`.
- `.claude/skills/coach-plan/recalc.md:6` (1 897 Б, лимит 3 072): «предложи пользователю самому решить (они на
  часах)» → «предложи пользователю `coach cancel <id>` (отменяет он сам, у отправленных — с часов)».
- Не трогать: `coach-agenda.md:11` (6 112 из 6 144 Б — запас 32 Б; смысл «предложи `event remove` слота» верен и
  после шага), `coach-wellbeing.md:21`, `coach-week.md:11`, `week.md:6` — там речь о том, что MCP пишет только
  черновики; это не меняется.
- README.md:79 и `docs/architecture.md:10,137` — строка про `coach cancel` (документация, не лимитируется).

## Модули, файлы, функции

- `src/ai_coach/plan/service.py` — `cancellable(conn, workout_id) -> row` (новая; аналог `pushable:38`),
  `cancel(conn, workout_id) -> None` (новая; аналог `approve:28`); `remove_old:57`, `has_old:52` — без изменений,
  переиспользуются. `src/ai_coach/plan/__init__.py` — экспорт двух новых имён в `__all__`.
- `src/ai_coach/cli/main.py` — команда `cancel` (новая; между `approve_:175` и `link:189` или после `push:206`),
  docstring модуля `:1-3` — добавить `cancel` в перечень команд; импорт из `ai_coach.plan`.
- `src/ai_coach/store/plans.py` — без изменений (`update_planned_workout:14`, `get_planned_workout:20`).
- `src/ai_coach/mcp_server/tools.py:410 cancel_draft_workout` — без изменений (при Р5 = 1).
- Тесты: новый `tests/test_plan_cancel.py` (импорт `PushClient, workout, row, status_of` из `test_plan_push`, как
  `test_plan_push_failures.py:6`); `tests/test_skills_help.py:301`; `tests/test_mcp_no_push.py` — не меняется,
  служит регресс-защитой (MCP не получает `cancel`, слова `delete/remove/garmin` в именах инструментов запрещены
  `:12`, импорт `ai_coach.plan` в `mcp_server/` запрещён `:16`).
- Тексты — список в «Справке».

## Партии

Одна партия: две функции (~20 строк), одна команда CLI (~30 строк), ~10 тестов, правки 6 текстов по строке.
Дробить незачем: один слой «переход статуса + Garmin», откат одним коммитом; объём как у Н16 (одна партия).

1. `plan/service.py` `cancellable` + `cancel` + экспорт; `cli/main.py` `cancel`; `tests/test_plan_cancel.py`;
   справка и тексты по «Справке»; README, architecture. Проверка: `make check`; руками — `uv run coach status`,
   `uv run coach cancel <id черновика>` → «Тренировка N отменена», в `status` `[cancelled]`; с отправленной —
   показ и y/N, после `y` на часах после синхронизации её нет (живая проверка Влада, Garmin).

Для mutmut (правило проекта — Makefile `mutate`, фоном вне агента; TESTS по `grep -l` после партии):
`ai_coach.plan.service:cancellable` (новая), `ai_coach.plan.service:cancel` (новая), `ai_coach.cli.main:cancel`
(новая) — `tests/test_plan_cancel.py`. По замеру Н15 mutmut по файлам партии ≈ 1–5 мин (handoff).

Команда (при Р4 = 1, Р6 = 1), порядок как в `push:206-235`:
1. `row = cancellable(conn, id)` → нет или уже `cancelled` → `PlanError`, код 1.
2. `echo` дата, вид, название, статус (строка как в `status:271`).
3. `draft`/`approved` (или `pushed` без Garmin-id) → `cancel`, `commit`, «Тренировка N отменена.»
4. `pushed` с id → `echo` «В Garmin: workoutId=…, scheduleId=…; после отмены её снимут с календаря и удалят»;
   `confirm("Отменить и удалить из Garmin?", default=False)`; `n` → «Ничего не отменено.», выход 0, `load_client`
   не вызывается (как `test_load_client_not_called_on_no`); `y` → `load_client()`, `remove_old(client, wid, sid)`,
   затем `cancel`, `commit`, «Тренировка N отменена и удалена из Garmin. Синхронизируй часы.»
5. `GarminError` → `fail(str(e))`, база не тронута (статус остаётся `pushed`); текст `remove_old` уже называет,
   что осталось в Garmin.

## Тесты (кабан-доеба)

Все — «ожидание, не проверено» (кода нет); фикстуры — `test_plan_push.py` (`isolated`, `client`, `workout`).

- `draft` → `coach cancel` → статус `cancelled`, `client.calls == []`, выход 0.
- `approved` → то же, без обращения к Garmin.
- `pushed` с `garmin_workout_id`/`garmin_schedule_id`, ввод `n` → статус `pushed`, `load_client` не вызван,
  `calls == []`, вывод «Ничего не отменено.».
- `pushed`, ввод `y` → `calls == [("unschedule_workout", sid), ("delete_workout", wid)]` (в этом порядке), статус
  `cancelled`, `garmin_workout_id` и `garmin_schedule_id` — `None`, `pushed_at` сохранён.
- `pushed`, `unschedule_workout` бросает (как `test_old_removal_failure_reports_old_ids`) → выход ≠ 0, статус
  `pushed`, id на месте, в stderr `workoutId=`/`scheduleId=`; `delete_workout` не вызывался.
- `pushed`, `delete_workout` бросает → статус `pushed`, сообщение «снята с календаря, но шаблон … не удалён».
- `cancelled` → `PlanError`, выход ≠ 0, статус не меняется, `calls == []`.
- id 999 → «Тренировки 999 нет.», выход ≠ 0.
- Показ перед y/N содержит дату и название тренировки (`result.output`).
- `cancel_draft_workout` для `approved`/`pushed` по-прежнему `ToolError` (`test_mcp_write.py:167` — уже есть,
  не трогать); `test_mcp_no_push.py` зелёный без правок.
- `test_skills_help.py` зелёный: `coach cancel` в `training.md`; размеры `coach.md`, `recalc.md`, `coach-help.md`,
  `sleep.md` в лимитах `text_limits.py`.
- Проверка руками (Влад): `uv run coach cancel <id отправленной>` → после `y` и синхронизации часов тренировки нет
  в календаре Garmin; `uv run coach status` показывает `[cancelled, отправлена <дата>]`.

## Развилки и риски

**Р1. Какие статусы отменяются** (видимое: что принимает команда). (1) `draft`, `approved`, `pushed` — любой даты,
в т. ч. прошедшей; (2) только `draft` и `approved` (не на часах); (3) только `draft` — тогда шаг сводится к CLI-
обёртке над тем, что уже есть в MCP. Рекомендую (1) (= папа 2026-11-01): Влад просил именно «запланированную», т. е.
утверждённую/отправленную; прошедшая дата — тоже отменяемо, иначе нельзя убрать вчерашний черновик. Следствие для
прошедшей `pushed`: при пересчёте план/факт (`load/plan_actual.py:89` берёт только `pushed`) она перестаёт быть
`skipped` — честно, раз отменена.

**Р2. Строка или статус `cancelled`** (видимое: остаётся ли в `coach status`). (1) `status = 'cancelled'`;
(2) `DELETE FROM planned_workouts`. Рекомендую (1): статус уже в CHECK (`0001_init.sql:94`) и во всех потребителях
(`sport_nutrition.py:36,81`, `agenda/day_plan.py:238`, `agenda/service.py:77`, `workouts/phone.py:140` — все уже
пропускают `cancelled`); на строку ссылаются `plan_actual.planned_id` (FK) и `coach_events.workout_id` — DELETE
оставит висячие ссылки и сломает историю; так же сделаны `delete weight`/`delete food` (пометка, строка остаётся)
и `event cancel`. В `coach status` отменённая видна как `[cancelled]` — как сейчас отменённые черновики, не меняем.

**Р3. Снимать ли с Garmin у `pushed`** (видимое: исчезает ли с часов). (да) `remove_old` — снять с календаря и
удалить шаблон; (нет) только статус, «сними с часов сам» как сейчас. Рекомендую «да» (= папа): код есть и проверен
повторным `push` (`test_plan_push.py:207-243`), иначе база говорит «отменена», а часы — «тренировка стоит».

**Р4. Подтверждение y/N** (видимое: диалог). (1) только у `pushed`, перед походом в Garmin — как `push` спрашивает
только перед отправкой; `draft`/`approved` отменяются сразу, как `event cancel` и `delete food`; (2) y/N у всех
статусов. Рекомендую (1): необратимое снаружи — только Garmin; черновик без y/N — в стиле проекта. Показ перед y/N:
дата, вид, название, статус, `workoutId`/`scheduleId` (как `push:219-223`).

**Р5. MCP** (видимое: может ли тренер отменить сам). (1) только CLI, `cancel_draft_workout` без изменений, тренер
после «да» запускает `uv run coach cancel <id>` (как `approve`/`push`, `coach.md:10`); (2) расширить
`cancel_draft_workout` на `approved` (не на часах), `pushed` — только CLI; (3) MCP отменяет всё без Garmin — нет:
база разойдётся с часами, `test_mcp_no_push.py:16` запрещает `ai_coach.plan` в MCP. Рекомендую (1): правило «MCP
пишет только черновики» записано в README:79, architecture:137, описании сервера `server.py:30` и 5 текстах
тренера — (2) потребует их все переписать ради одного статуса.

**Р6. Имя и форма команды** (видимое: что набирать). (1) `coach cancel <id>` — один id, как `approve`/`push`;
(2) `coach delete workout <id>` — в группу `delete` (`journal.py:31`, «Удаление записей веса и еды»); (3) `coach
cancel <id...>` — несколько id с коммитом после каждого, как `event cancel` (`agenda.py:41 each`). Рекомендую (1):
статус называется `cancelled`, парно с `event cancel` и `cancel_draft_workout`; y/N с показом удобнее на одном id;
(2) смешает тренировку с журналом веса/еды.

**Р7. Allow-строка** (видимое: спросит ли Claude Code ещё раз). (1) не добавлять — как `approve`, `push`, `edit`,
`delete` (их в `settings.json` нет): «да» в чате + запрос Claude Code, по образцу `event write`/`remove`
(architecture:199); (2) добавить `Bash(uv run coach cancel:*)` — Влад руками. Рекомендую (1): команда ходит в
Garmin.

**Р8. Слот тренировки в календаре коуча** (видимое: подсказка после отмены). (1) команда ничего не говорит; тренер по
`coach-agenda.md:11` предлагает `event remove` слота; (2) команда печатает «у тренировки есть событие N — `coach
event remove N`» — нужна новая выборка событий по `workout_id` в `store/agenda.py` (сейчас нет, grep). Рекомендую
(1) — минимум под задачу; (2) — кандидат в беклог.

Риски:
- Частичный сбой Garmin: `unschedule_workout` прошёл, `delete_workout` упал → статус остаётся `pushed`, id на месте;
  повторный `coach cancel` снова вызовет `unschedule_workout` по уже снятому расписанию — ответ Garmin не известен
  (ожидание, не проверено). Та же дыра есть у повторного `push` сегодня (architecture:117 «при сбое — дубль»).
  В Н17 не лечим; если всплывёт — беклог.
- y/N через `typer.confirm` при запуске тренером из Bash без tty — как сегодня у `push`; не проверено, что Влад
  запускает `push` через тренера, а не руками. Поведение не ухудшается.
- `coach.md` запас 915 Б — две правки по строке; превышение лимита покажет `test_skills_*` по `text_limits.py`.
- `pushed` без Garmin-id в базе — по коду `send:77-96` невозможно (id пишутся вместе со статусом); умолчание 3 на
  всякий случай.
- Garmin-методы `unschedule_workout`/`delete_workout` есть в установленном garminconnect (`.venv …/garminconnect/
  __init__.py:3928,3554`); новых зависимостей нет.

## Умолчания (внутреннее)

1. Имена: `cancellable`, `cancel` в `plan/service.py`, экспорт через `plan/__init__.py`; команда `cancel` в
   `cli/main.py` (имя функции `cancel`, typer-имя `cancel` — попадёт в `cli_commands` теста справки).
2. После успешного снятия с Garmin — `garmin_workout_id` и `garmin_schedule_id` → `NULL` (в Garmin их больше нет;
   `has_old` → False), `pushed_at` остаётся как история. При Р3 = нет — id не трогаем.
3. `pushed` без Garmin-id (`has_old` False) — отменяется как `approved`, без Garmin и без y/N (при Р4 = 1), с
   строкой «id Garmin не записаны — проверь часы».
4. Порядок «Garmin → база» (при Р3 = да): сбой Garmin не меняет базу — как `write_event` (architecture:202) и
   `send` (база после успешного schedule).
5. Тесты — новый `tests/test_plan_cancel.py`, фикстуры из `test_plan_push.py` импортом (прецедент
   `test_plan_push_failures.py:6`). Тексты ошибок — в стиле `PlanError` «Тренировка N уже отменена.».
6. Сообщения команды (при Р4 = 1, Р6 = 1) — как в разделе «Партии», п. 3–4; кабан держит стиль `push`.

## Открытые вопросы

1. Р3: снимать ли отправленную тренировку с Garmin (`plan/service.py:57 remove_old`, `cli/main.py` новая `cancel`)
   варианты: (да) снимать после y/N (нет) только статус; рекомендую «да» — иначе база и часы расходятся;
   разблокирует: партию (определяет форму команды и тесты); решает: Влад. Блокирующий.
2. Р1: статусы — все три / draft+approved / только draft; рекомендую все три; решает: Влад.
3. Р2: `cancelled` или DELETE (`store/plans.py`); рекомендую `cancelled`; решает: Влад.
4. Р4: y/N только у `pushed` или у всех; рекомендую только у `pushed`; решает: Влад.
5. Р5: только CLI или расширить MCP на `approved` (`mcp_server/tools.py:410`); рекомендую только CLI; решает: Влад.
6. Р6: `coach cancel <id>` / `coach delete workout <id>` / несколько id; рекомендую `coach cancel <id>`; решает: Влад.
7. Р7: allow-строка — не добавлять / добавить (Влад руками); рекомендую не добавлять; решает: Влад.
8. Р8: подсказка о слоте в календаре коуча — нет / да (новая выборка по `workout_id`); рекомендую нет; решает: Влад.

## Правки по ревью

Отступления кабана, принятые папой 2026-11-02:
- Умолчание 3 сужено: pushed без Garmin-id отменяется как approved, без строки «id Garmin не записаны — проверь
  часы». Состояние недостижимо (send:77-96, «Риски»), а ветка поднимала smells cli/main.py выше порога 0. Видимых
  изменений для обычных сценариев нет.
- Хвост сообщения отмены выбирается словарём SYNC_TAIL[has_old(row)] в cli/main.py, а не веткой if: так держится
  порог smells 0. Тексты сообщений — как в Партии, пп. 3–4.

Ревью круг 1 (мама, свекровь), 2026-11-02:
- Свекровь: лишняя проверка статуса в `cancellable` (недостижима по CHECK 0001_init.sql:94) — убрать; решение папы.
- Р9 (Влад, окно, по рекомендации папы): в `remove_old` «Старая копия» → «Копия» — верно и для cancel, и для push.
- Мама: assert в test_cancel_unschedule_failure_keeps_row проверяет id, что печатаются до y/N, — проверять текст
  ошибки; правит доеба.
- Мама: SYNC_TAIL → if — не правим, принятая правка выше (папа).
- Мама: повторный `coach cancel` после сбоя delete_workout снова зовёт unschedule уже снятого scheduleId — риск
  (как у push, не регресс); ответ Garmin не проверен — ручная проверка ниже; ошибка → пункт BACKLOG «remove_old:
  идемпотентный повтор (cancel и push)» (папа).

Полный прогон 2026-11-02: tests/test_skills_text.py:166 ждал «на часах» в coach.md п.8б — устарел по плану (теперь
`uv run coach cancel <id>`); доеба заменил assert на `uv run coach cancel`.

mutmut 2026-11-02: `cancellable` 11/11 убиты, `cancel` 12/15; 3 выживших — регистр ключей `values` (STATUS и
garmin-id): эквивалентны (SQLite не различает регистр колонок, параметр берётся из того же ключа, db.py:94-97),
разбор доебы; тестов не добавлено. `cli.main.cancel_` mutmut не мутирует (мутантов 0).

## Открыто: стенд / аналитик

- Влад руками: `coach cancel <id>` на тренировке, отправленной на часы — y/N, снятие с календаря Garmin и шаблона,
  синхронизация часов; на черновике — отмена сразу.
- Влад руками: повторный unschedule уже снятого scheduleId — что отвечает Garmin.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план Н17 (суть, партии, тесты, риски); база сметы — «Итог» Н16 (`docs/plan-n16.md`, одна
партия похожего объёма: ~50 строк кода + ~10 тестов + правки текстов); масштаб ≈ 1,0–1,2 (у Н17 6 текстов и
ветка Garmin против 4 текстов у Н16).

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Новых платных статей нет | 0 | Garmin API уже используется, новых зависимостей нет (план, «Риски») | — | — | — |
| LLM-цепочка шага (разово) | 4,8–7,8 $ за шаг | таблица ролей ниже | см. ниже | — | — |

| Партия | Время |
|---|---|
| План (папа) | уже прошло 6,5 мин (af75973fe36f243d8) |
| 1. `cancellable`/`cancel`, `coach cancel`, тесты, 6 текстов, README/architecture | 30–50 мин (Н16: 13 мин работы + make check 5–10 мин; круги правок мамы по текстам `coach.md` у лимита) |
| Декарт (1 партия + 1 сводный = 2 вызова) + тесть р.3 | 8–12 мин |
| Ожидание окон Р1–Р8 и живой проверки Garmin | не считается в работу (у Н16 — 31 мин простоя) |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| papa-kaban (план — уже прошло; закрытие) | fable (цена Opus) | 0,6–0,8M | 1,25 уже прошло + 0,3–0,5 |
| kaban | sonnet | 0,5–0,8M | 0,3–0,5 |
| kaban-doeba | sonnet | 0,3–0,5M | 0,15–0,3 |
| mama-kaban | opus | 0,5–0,8M | 0,45–0,7 |
| kaban-svekrov | opus | 0,5–0,7M | 0,45–0,6 |
| kaban-test (р.1 + р.3) | opus | 0,3–0,4M | 0,3–0,5 |
| kaban-dekart (2 вызова) | fable (цена Opus) | 2–4M | 1,7–3,5 (факт Ш9 семьи 3,47 $ за шаг; за вызов ≈ 1,7 $ — допущение) |
| orchestrator | opus | не включён (как в итогах Н15/Н16 считается отдельно, ~3 $) | — |
| **итого (без оркестратора)** | | 4,7–8,2M | **4,8–7,8** (нижняя граница ≥ уже прошло 1,25) |

Дешевле: Декарт — самая дорогая позиция при малой партии; можно звать один сводный вызов вместо двух
(−~1,7 $), теряем разбор партии отдельно. Папа на fable для закрытия ROADMAP — по правилу не трогаем
(оркестраторные роли). Ревью/аудит не сокращаем. Вердикт: ок по бабкам.

## Итог

**Источник токенов:** `metrics.py ~/.claude/projects/-Users-vladislavahtamov-projects-ai-coach/b2d2785d-d8ab-475d-9ff9-c8c8aa9b80ee.jsonl --from 2026-11-02T04:25` (09:25 +05); **цены:** тариф metrics.py 2026-10-25, https://platform.claude.com/docs/en/about-claude/pricing; fable — по Opus.

| Партия | Смета | Факт |
|---|---|---|
| План (папа) | уже прошло 6,5 мин | 6,5 мин (af75973fe36f243d8) |
| 1. `coach cancel`, тесты, тексты (коммит f5e8fdc) | 30–50 мин | ~10 мин работы по сегментам: kaban 3,4 + doeba 3,3 + mama ‖ svekrov ~1,6 + папа (отступления, ревью) ~1,1; интервал 09:37–10:14, в т. ч. простой — окно Р9 Влада, make check и mutmut фоном |
| Декарт (2 вызова) + тесть р.3 | 8–12 мин | Декарта к моменту подсчёта не звали; тесть р.1 0,8 мин, р.3 идёт |
| Весь шаг | — | 102 мин интервал (09:25–11:07), работы оркестратора 23,2 мин; остальное — окна Р1–Р9 и фоновые прогоны |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| orchestrator (на момент подсчёта 11:07) | opus | 8,70M | 3,62 |
| papa-kaban (план fable + 3 вызова opus) | fable / opus | 1,13M | 1,69 |
| kaban | sonnet | 0,78M | 0,42 |
| kaban-doeba | sonnet | 0,74M | 0,47 |
| mama-kaban | opus | 0,34M | 0,55 |
| kaban-svekrov | opus | 0,37M | 0,60 |
| kaban-test (р.1 + р.3, на момент подсчёта 11:07) | opus | 0,28M | 0,47 |
| kaban-dekart | fable (по Opus) | — (не звали на момент подсчёта) | 0 |
| **итого** | | 12,35M | **7,82** (без оркестратора 4,20) |

**Итого:** смета 4,8–7,8 $ без оркестратора → факт 4,20 $ (ниже: Декарт 1,7–3,5 $ ещё не потрачен; папа дороже сметы на ~0,1 $ — три лишних вызова на отступления и Р9); время партии 30–50 → ~10 мин работы.
Churn после ревью: код +3/−5, тесты +4/−5 (6 % от строк до T0)
Разбор — кабан Декарта.
