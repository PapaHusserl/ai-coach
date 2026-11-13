# Шаг Г1. Гигиена: `make check` в зелёный (`make dead`, `make smells`)

Закрывает BACKLOG 80 и 58. План — папа-кабан, 2026-11-13. Режим «встроить»: только рефакторинг, поведение не
меняется. Разведка на HEAD ac61604. Образец — docs/plan-25-smells.md. Состояние: развилки Р1–Р7 ждут Влада.

## Суть

`make check` красный двумя целями: `dead` (vulture, 2 находки) и `smells` (qlty, 6 при `SMELLS_MAX ?= 0`,
`Makefile:3`). Остальные цели на HEAD (прогон 2026-11-13): `lint` — «All checks passed», 473 файла; `types` —
pyright 0 ошибок; `player-test` — 308 JS-тестов, 0 падений. `cov` я не гонял: тяжёлый прогон субагенту закрыт
(testy.md), его делает оркестратор на гейте — ожидание: зелёный, не проверено.

Инструменты: vulture 2.16 (`pyproject.toml:65–69`, `min_confidence = 60`); qlty 0.651.0, пороги — умолчания
(`file_complexity 50`, `function_complexity 18`, проверка `count >= threshold`, то есть цель: файл ≤ 49,
функция ≤ 17), свой порог только у `function_parameters = 15` (`.qlty/qlty.toml`).

**Правило:** при рекомендациях архитектора меняется одна строка конфига (Р1 = 1) — первым пунктом аппрува:
было `ignore_names = ["model_config", "row_factory", "__signature__", "do_*", "log_message"]` (`pyproject.toml:68`)
→ станет `ignore_names = ["model_config", "row_factory", "__signature__", "do_*", "log_message", "side_effect"]`.
При Р1 = 2 конфиг не меняется вовсе. Пороги не меняются ни в одном варианте: `SMELLS_MAX ?= 0`,
`file_complexity 50`, `function_complexity 18`, `min_confidence = 60` (решение Влада 2026-11-13, Р2 = 1,
docs/plan-roadmap-r3.md «Решения»). `.qlty/qlty.toml` меняется только при Р2 = 2.
**Поведение:** не меняется — вывод и порядок команд `coach --help`, вывод `coach status`, строка итога
`coach sync` и порядок замечаний в ней, ответы пульта (`GET/POST /api/*`, статика, статусы, заголовки, тексты
ошибок), поведение вкладок и автообновления пульта — байт в байт.
**Вне репо:** нет (строки allow в `.claude/settings.json` не нужны: новых команд нет).

## Решения

Влад, 2026-11-13 (docs/plan-roadmap-r3.md «Решения», п. 2; кто решил: Влад): Р2 = (1) — 80 и 58 одним шагом,
рефакторинг, пороги как есть, как шаг 25 (решение Влада 2026-10-27, docs/plan-25-smells.md «Решения»).

Окна 2026-11-13 по развилкам плана; кто решил — Влад, все по рекомендации папы:

- Р1 = (1) — `side_effect` в `ignore_names` (`pyproject.toml:68`).
- Р2 = (1) — убрать реэкспорт `validate_draft` из `agenda/__init__.py`.
- Р3 = (1) — `cli/status.py`.
- Р4 = (1) — `sync/coach_calendar.py`.
- Р5 = (Б) — `Handler` на уровень модуля.
- Р6 = (1) — `web/static/tabs.js`.
- Р7 = (1) — `cli/journal.py` в шаг не брать, пункт беклога «файлы у порога сложности».

## Находки и как разводить

Цифры «сейчас» — `qlty smells --all` и `qlty metrics --functions` на HEAD ac61604. Цифры «после» с пометкой
«песочница» измерены qlty 0.651.0 на копии `src/` вне репо с черновой правкой (копия удалена); итог проверяется
только `make smells` и `make dead`.

История роста smells после шага 25 (коммит 8437967, smells 0) — прогон `qlty smells` по коммитам во временном
worktree (убран):

| Коммит | Дата | Что появилось | Итого |
|---|---|---|---|
| 7e34602, Н23 партия 1 | 11-07 | файл `sync/workload_sync.py` (перенос события из Календаря: `own_events`, `coach_part`) | 1 |
| 4b54aa7, Н23 партия 2 | 11-07 | файл `cli/main.py` (`coach sync --calendar`) | 2 |
| d018d59, Н23 партия 4 | 11-07 | дубль `agenda/__init__.py` ↔ `plan/__init__.py` (две находки) | 4 |
| 68c1a9d, П4 партия 3 | 11-10 | функция `make_server` | 5 |
| d90f82a, П4 партия 5 | 11-10 | `make_server` ушла (таблица `GET_VIEWS`), пришёл файл `web/static/pult.js` | 5 |
| 8fd651f, П5 партия 3 | 11-12 | `make_server` вернулась: 16 → 23 (`api`: ветка `meeting_view` и `MarkError`) | 6 |

«4» из BACKLOG 58 (HEAD 6a69bcc, 11-07) — состояние после Н23; рост 4 → 6 — это `pult.js` (П4 партия 5) и
возврат `make_server` (П5 партия 3). В BACKLOG 58 назван `plan/service` — фактически находка в `plan/__init__.py`.

### 1. vulture: `tests/test_agenda_calendar_edit.py:285, :292` — `unused attribute 'side_effect'` (60 %)

Причина: коммит 07d1c33 (закрытие П5, тесты по выжившим мутантам) добавил два теста
(`test_unexpected_save_exception_…`, `test_unexpected_remove_exception_…`) с присваиванием
`store.<метод>.side_effect = RuntimeError(...)`. Это единственные `side_effect` в репо (`grep -rn side_effect src
tests` — 2 строки): атрибут присвоен и нигде не прочитан кодом, его читает `unittest.mock`. `return_value` не
ловится, потому что читается в том же файле (`:46`, `:255`). У vulture есть белый список
(`vulture/whitelists/unittest_whitelist.py:16, :19` — `Mock.side_effect`, `MagicMock.side_effect`), но он
подключается по имени импорта (`vulture/core.py:299–301`): нужен `import unittest`, а в тестах
`from unittest.mock import MagicMock` — имя `MagicMock`, список не подключается. Ложная находка.

- Вариант 1 (рекомендую): `"side_effect"` в `ignore_names` (`pyproject.toml:68`). Там уже лежат имена, которые
  читает библиотека, а не наш код: `row_factory`, `model_config`, `__signature__`, `log_message`, `do_*`.
  Проверено: `vulture --ignore-names '…,side_effect'` — пусто. Тесты не трогаются; следующие тесты с
  `side_effect` не падают в ту же яму.
- Вариант 2: конфиг не трогать, переписать две строки теста —
  `store_of(kit).saveEvent_span_commit_error_ = MagicMock(side_effect=RuntimeError("секрет"))` (и для `remove…`).
  Проверено на копии файла: находок в файле нет. Минус: ловушка остаётся для каждого следующего теста.

### 2. Дубль `src/ai_coach/agenda/__init__.py` ↔ `src/ai_coach/plan/__init__.py` (mass = 69, две находки)

Причина: оба файла — «импорт N имён из `.service` + `__all__` из N строк». До d018d59 у agenda было 7 имён, у plan
9; Н23 добавил `move_draft` и `move_event` — стало 9 и 9, структура совпала один в один. Порог массы лежит между 8
и 9 именами: пара `garmin/__init__.py` ↔ `pantry/__init__.py` (по 8 имён, та же форма) не ловится. Смысла в
находке нет — это списки реэкспорта.

- Вариант 1 (рекомендую): убрать из `agenda/__init__.py` реэкспорт `validate_draft` (строки `:15`, `:27`). Из
  пакета его никто не берёт: внутри `agenda/service.py` он зовётся напрямую (`:157`, `:237`), тесты импортируют из
  `ai_coach.agenda.service` (`tests/test_agenda_service.py:8`). Песочница: дубль исчез. Минус: хрупко — любая
  пара пакетов с 9+ именами одной формы даст находку снова.
- Вариант 2: фильтр импортов в `.qlty/qlty.toml`:
  `[language.python.smells.duplication] filter_patterns = ["(import_from_statement)", "(import_statement)"]`.
  Песочница: дубль исчез, новых находок нет (два шаблона проверены вместе, по отдельности — нет). Надёжно, но
  это правка конфига qlty для всего Python: импорты перестают участвовать в поиске дублей. Глоб
  `filter_patterns = ["**/__init__.py"]` в `[smells.duplication]` не работает (песочница: находка осталась).
- Вариант 3: оба.

### 3. `src/ai_coach/cli/main.py` — сложность файла 50 (нужно ≤ 49)

Вклад функций (`cognitive`): `status` 12, `push` 7, `import_` 6, `login` 5, `cancel_` 5, `screen` 5, `claude` 4,
`sync` 3, `parse_hours` 2, `feel` 2, по 1 — `approve_`, `link`. Прецедент — одиночные команды в своих модулях,
регистрация в main.py: `cli/pvt.py`, `cli/web.py` (`app.command()(pvt)`, `app.command("web")(web)`,
`main.py:85, :87`); шаг 25 так же вынес `cli/profile.py`.

- Вариант 1 (рекомендую): новый `src/ai_coach/cli/status.py` — команда `status` (`main.py:291–325`); `fail`,
  `check_date` — из `cli/journal.py` (как `cli/pvt.py`, `cli/profile.py`). Песочница: 50 → 39. Тесты не правятся:
  `status` зовут через `main.app` (`tests/test_cli.py:377–`), `main.<имя>` у этой команды не патчится.
  Обязательно: регистрация `app.command()(status)` стоит в main.py на прежнем месте — между `cancel_` и
  `parse_hours`/`feel`, иначе меняется порядок команд в `coach --help` (сейчас: `…, push, cancel, status, feel,
  screen, claude`).
- Вариант 2: `cli/wellbeing.py` — `feel`, `screen`, `parse_hours`, `MAX_HOURS`, `SCREEN_LABELS` (вариант Б шага 25).
  Ожидание 50 → ≈ 41, не проверено. Минус: `tests/test_cli_screen.py` патчит `main.AwReader` — правка теста; та же
  оговорка о порядке регистрации для двух команд.

### 4. `src/ai_coach/sync/workload_sync.py` — сложность файла 56 (нужно ≤ 49)

Вклад: `own_events` 14, `sync_workload` 11, `coach_part` 7, `read_counters` 7, `stored_events` 6,
`claude_counters` 4, `vanished` 3, `read_calendar` 3, `resolve_config` 2. Выросло в Н23 (перенос события) и Н5
(Claude). Прецедент выноса по порогу — `agenda/day_layout.py` (Н28, docs/architecture.md:278).

- Вариант 1 (рекомендую): новый `src/ai_coach/sync/coach_calendar.py` — «календарь коуча»: `own_events`,
  `vanished`, `coach_part` (`workload_sync.py:58–133`). `read_calendar` остаётся и зовёт `coach_part` из нового
  модуля. Песочница: 56 → 32. Тесты не правятся: эти три функции тесты напрямую не импортируют и не патчат
  (grep по `tests/` пуст); патчи `workload_sync.CalendarReader` (`tests/test_cli_sync_workload.py`,
  `tests/test_web_syncer.py`) и `workload_sync.scan_claude` (`tests/test_workload_sync.py`) остаются валидными —
  `read_calendar` и `claude_counters` не переезжают.
- Вариант 2: новый `sync/workload_counters.py` — `read_counters`, `claude_counters`, `resolve_config`. Ожидание
  56 → ≈ 43, не проверено. Минус: правка импортов в `tests/test_workload_sync.py` (`read_counters`,
  `resolve_config`) и патча `scan_claude`; запас меньше.

### 5. `src/ai_coach/web/server.py:143 make_server` — функция 23 (нужно ≤ 17)

Причина: класс `Handler` объявлен внутри функции — сложность его методов (`do_GET` 4, `api` 6, `static` 2,
`do_POST` 2) плюс штраф за вложенность считаются функции `make_server`. Находка уже возвращалась: П4 партия 3 →
убрана таблицей `GET_VIEWS` (d90f82a) → вернулась в П5 партии 3.

- Вариант А (как уже сделано в файле — `post_reply`, `server.py:99`): новая функция модуля
  `get_reply(db, query, build) -> tuple[int, str]` — тело `api` (`:171–193`): разбор даты, `open_db`, вызов
  `build`, `MarkError` → 404/400; `api` остаётся тремя строками с `self.send(...)`, как `do_POST`. Песочница:
  23 → 14, запас 3. Дифф ≈ 20 строк.
- Вариант Б (рекомендую): `Handler` — класс уровня модуля с атрибутом класса `db`; `make_server` заводит
  наследника с нужным `db` и отдаёт `ThreadingHTTPServer((host, port), <наследник>)`. Песочница: `make_server` 0,
  самый тяжёлый метод — `api` 6; находка этим путём больше не вернётся. Минус: дифф ≈ 70 строк (сдвиг отступа
  `server.py:146–212`), ревью — `git diff -w`.
- Тесты не правятся в обоих вариантах: берут только `make_server`, `lan_address`, `post_reply`, `resources`,
  `socket` (`tests/test_web_server.py`), `Handler` не упоминают.

### 6. `src/ai_coach/web/static/pult.js` — сложность файла 61 (нужно ≤ 49)

Сумма именованных функций — 36 (`rowNode` 16, `load` 6, `openRow` 5, `rowText` 3, …); остальные 25 — код верхнего
уровня в блоке `if (typeof document !== "undefined")`: цикл по вкладкам с обработчиком клика (`pult.js:182–197`)
и таймер. Обработчик клика и `load` (`:164–166`) дублируют одно и то же: «вкладка видна → загрузить её панель».

- Вариант 1 (рекомендую): новый `src/ai_coach/web/static/tabs.js` — `setupTabs()` (цикл по `#tabs button`,
  `pult.js:182–197`) и `refreshPanels(day, today)` (три условия из `load`, `:164–166`) над одной таблицей
  «вкладка → загрузчик» (`train` → `loadWeek`, `food` → `loadPantry`, `state` → `loadState`, порядок тот же).
  Импорты `loadWeek`, `loadPantry`, `loadState` уезжают из pult.js в tabs.js. Песочница: pult.js 61 → 38,
  tabs.js 11. `index.html` не правится (`:116` грузит только `pult.js`, остальное — импортами); сервер отдаёт
  любой файл из `static/` (`server.py:195`).
- Вариант 2: вынести отрисовку строки (`rowText`, `progressNode`, `makeTappable`, `rowClasses`, `rowNode` — 21) в
  `rows-pane.js`. Не проверено. Минус: `rowNode` держится на состоянии модуля (`choice`, `meetChoice`,
  `lastView`, `render`, `reloadDay`) — придётся передавать его параметрами; дублирование вкладок остаётся.

### 7. Попутно: `src/ai_coach/cli/journal.py` — сложность 49, один пункт до порога

Не красный, в BACKLOG 58 не входит. Следующая же команда в journal.py вернёт находку. Замерено тем же прогоном
(порог временно 1): ещё близко — `workload/claude.py` 47, `web/marks.py` 45. См. Р7.

## Файлы

При рекомендациях (Р1 = 1, Р2 = 1, Р3 = 1, Р4 = 1, Р5 = Б, Р6 = 1):

- `pyproject.toml:68` — `"side_effect"` в `ignore_names` (при Р1 = 1).
- `src/ai_coach/agenda/__init__.py:15, :27` — убрать `validate_draft` (при Р2 = 1).
- `src/ai_coach/cli/status.py` — новый: `status` (новая по месту; при Р3 = 1).
- `src/ai_coach/cli/main.py` — убрать `status` (`:291–325`), импорт из `cli/status.py`, `app.command()(status)` на
  месте прежнего определения; лишние импорты убрать (ruff). Docstring модуля не меняется.
- `src/ai_coach/sync/coach_calendar.py` — новый: `own_events`, `vanished`, `coach_part` (новые по месту; при
  Р4 = 1).
- `src/ai_coach/sync/workload_sync.py` — убрать `:58–133`, импорт `coach_part`; `find_by_uid`, `list_events` из
  импортов уходят. `read_calendar` (есть, `:136`), `sync_workload` (есть, `:217`) — без правок тела.
- `src/ai_coach/web/server.py` — `Handler` (есть, `:146`, сейчас вложенный) на уровень модуля, `make_server`
  (есть, `:143`) — три-пять строк (при Р5 = Б); либо `get_reply` — новая, `api` — три строки (при Р5 = А).
- `src/ai_coach/web/static/tabs.js` — новый: `setupTabs`, `refreshPanels` (новые; при Р6 = 1).
- `src/ai_coach/web/static/pult.js` — убрать `:182–197` и `:164–166`, вызовы `setupTabs()`, `refreshPanels(...)`.
- `tests/test_cli.py` (или соседний `tests/test_cli_*.py`) — тест порядка команд; `tests/test_web_server.py` — тест
  кириллицы в GET, если его нет (раздел «Тесты»).
- Не трогать: `Makefile`, `.qlty/qlty.toml` (кроме Р2 = 2), `index.html`, `sync/__init__.py`, тесты
  `test_agenda_calendar_edit.py` (кроме Р1 = 2), `docs/architecture.md` (карта там по пакетам; `:236`
  `stored_events` и `:284` `claude_counters` остаются в workload_sync.py; `:179` — сигнатура `sync_workload` без
  `screen` отстала ещё до шага 25, в объём не входит без «да»).

**Объём** (строки на HEAD, `sed`-диапазоны выше): перенос 35 (`status`) + 76 (календарь коуча) + 19 (вкладки) +
67 (сдвиг `Handler`, при Р5 = Б; ≈ 20 при А); новый код — tabs.js ≈ 25 строк (по черновику песочницы), шапки и
импорты новых модулей, 1–2 теста. Ожидание: ≈ 250 строк диффа, не проверено; в лимит партии 400 укладывается.

## Партии

Одна партия (решение архитектора, как в шаге 25): правки независимы, но гейт общий — `make check` зеленеет
только когда закрыты все восемь находок; две партии дали бы два круга ревью и аудита на красном гейте.

1. Кабан-доеба (до правок): тест порядка команд и, если нет, тест кириллицы в GET — оба зелёные на HEAD.
2. Кабан: п. 1 и п. 2 «Находок» — `make dead` пусто; `make smells` показывает 4.
3. Кабан: п. 3 и п. 4 — `make smells` показывает 2; `uv run pytest tests/test_cli.py tests/test_workload_sync.py
   tests/test_workload_sync_agenda.py tests/test_cli_sync_workload.py tests/test_web_syncer.py
   tests/test_workload_import.py` зелёный.
4. Кабан: п. 5 и п. 6 — `make smells` → `smells: 0 (max 0)`; `make player-test` — 308 тестов, 0 падений;
   `uv run pytest tests/test_web_server.py` зелёный.
5. Гейт партии: `make check` целиком → `check: OK` (cov и мутации гоняет оркестратор — testy.md). Мутации — по
   изменённым модулям (`MOD` в `Makefile:5` берёт их из `git diff`).

## Справка (правило AGENTS.md)

Не требуется: новых и изменённых функций тренера нет (команды CLI, MCP-инструменты, скилы, вопросы чек-ина и шкалы
те же). `.claude/agents/coach-help.md` и `coach-help/` не правятся; `tests/test_skills_help.py` (сверяет имена по
`main.app.registered_commands`, `:485`) остаётся зелёным — `status` регистрируется под тем же именем.

## Тесты (кабан-доеба)

Существующие — страховка «поведение не меняется»:

- `coach status` — `tests/test_cli.py:377–` (без опций, `--date`, `--from`), через `main.app`; проверено: файл
  есть, 34 теста, `main.status` не патчится.
- `sync_workload` и календарь коуча — `tests/test_workload_sync.py` (56 тестов), `tests/test_workload_sync_agenda.py`,
  `tests/test_cli_sync_workload.py`, `tests/test_web_syncer.py`, `tests/test_mcp_snapshot_workload.py` — через
  публичную `sync_workload`; прогонять целиком (риск из docs/plan-roadmap-r3.md: окно данных v2.9).
- Импорт без EventKit — `tests/test_workload_import.py`: новый `sync/coach_calendar.py` не должен тянуть EventKit
  (берёт только `store.agenda` и `WorkloadConfig`).
- Сервер пульта — `tests/test_web_server.py` (99 тестов): статика, типы содержимого, кривая дата
  (`"date: нужна дата YYYY-MM-DD."`, `:480, :882, :936`), `/api/meeting` 400 и 404 (`:1045, :1049`), POST,
  методы; `tests/test_web_*.py` остальные.
- JS — `tests/web/*.test.mjs`, `tests/player/*.test.mjs`: 308 тестов; `tests/web/pult.test.mjs` импортирует
  `pult.js` целиком — цепочка импортов с `tabs.js` должна грузиться в node без `document`.
- vulture — `tests/test_agenda_calendar_edit.py`: оба теста `…_exception_is_calendar_error_with_type_name`
  остаются и проходят.

Чего не хватает (добавить):

- Порядок команд: `[c.name or c.callback.__name__ for c in main.app.registered_commands]` равен `['weight',
  'food', 'focus', 'slip', 'pvt', 'who5', 'web', 'shop', 'login', 'sync', 'import', 'approve', 'link', 'push',
  'cancel', 'status', 'feel', 'screen', 'claude']` — проверено: вывод на HEAD ac61604. Группы
  (`registered_groups`) шаг не трогает.
- `GET /api/day` с кириллицей в названии пункта: в теле ответа буквы как есть, не `\u04…` (`ensure_ascii=False`) —
  ожидание, не проверено: grep такого теста не нашёл; если есть — не дублировать.
- При Р5 = А — прямые тесты `get_reply` (новая): кривая дата → `(400, "date: нужна дата YYYY-MM-DD.")`; `NoEvent`
  → 404; иной `MarkError` → 400; успех → `(200, JSON)`; соединение закрыто во всех ветках.
- При Р5 = Б — два сервера `make_server` с разными `db` в одном процессе отвечают каждый из своей базы (атрибут
  класса не общий) — ожидание, не проверено.
- Проверка руками (Влад, после партии): `make check` → `check: OK`; `coach --help` — список как раньше;
  `coach status`; `coach web` → в браузере пять вкладок: клик по «Тренировки», «Еда», «Состояние» грузит панель,
  «План» и «Туду» открываются, стрелки дня перегружают открытую вкладку, через минуту список обновляется сам.
  У `tabs.js` автотестов нет: тесты `tests/web` идут без `document` (grep `document` — 0 во всех восьми файлах).

Для mutmut (`модуль:функция`): `web.server:make_server` (есть), `web.server:get_reply` (новая, при Р5 = А),
`sync.workload_sync:read_calendar` (есть), `sync.coach_calendar:own_events`, `sync.coach_calendar:vanished`,
`sync.coach_calendar:coach_part` (новые по месту), `cli.status:status` (новая по месту). TESTS:
`tests/test_web_server.py`, `tests/test_workload_sync.py`, `tests/test_workload_sync_agenda.py`,
`tests/test_cli_sync_workload.py`, `tests/test_cli.py`.

## Развилки

Все — выбор Влада; видимого пользователю ни одна не меняет.

- **Р1. vulture, `side_effect`.** (1) имя в `ignore_names` (`pyproject.toml`); (2) переписать две строки теста,
  конфиг как есть. Рекомендую (1): находка ложная (белый список самого vulture её знает, но не подключается),
  в `ignore_names` уже лежат такие же имена; (2) оставляет ловушку. Порогов (1) не трогает, но это правка конфига
  проверки — поэтому развилка.
- **Р2. Дубль `__init__`.** (1) убрать неиспользуемый реэкспорт `validate_draft`; (2) фильтр импортов в
  `.qlty/qlty.toml`; (3) оба. Рекомендую (1) — в рамках «конфиг как есть» (Р2 перебора R3); честно: хрупко,
  вернётся при следующем совпадении числа имён, тогда (2).
- **Р3. Разрез `cli/main.py`.** (1) `cli/status.py`; (2) `cli/wellbeing.py`. Рекомендую (1): 50 → 39 (песочница),
  тесты не правятся.
- **Р4. Разрез `sync/workload_sync.py`.** (1) `sync/coach_calendar.py`; (2) `sync/workload_counters.py`.
  Рекомендую (1): 56 → 32 (песочница), тесты не правятся.
- **Р5. `make_server`.** (А) `get_reply`, как `post_reply`: 23 → 14, дифф ≈ 20 строк, запас 3; (Б) `Handler` на
  уровень модуля: `make_server` 0, дифф ≈ 70 строк. Рекомендую (Б): находка появлялась дважды (2026-11-10 и
  2026-11-12), запас 3 — до первой новой ветки в обработчике.
- **Р6. Разрез `pult.js`.** (1) `tabs.js`; (2) `rows-pane.js`. Рекомендую (1): 61 → 38 (песочница), убирает
  дублирование вкладок, состояние модуля не трогает.
- **Р7. `cli/journal.py` = 49.** (1) в шаг не брать, завести пункт беклога «файлы у порога сложности: journal 49,
  workload/claude 47, web/marks 45»; (2) разрезать journal.py в этом же шаге (объём и разрез не разведаны —
  партия вырастет, нужен дозаход архитектора). Рекомендую (1): находки нет, Р2 перебора R3 — про 80 и 58.

## Умолчания (внутреннее)

- Имена: `cli/status.py`, `sync/coach_calendar.py`, `web/static/tabs.js`, `setupTabs`, `refreshPanels`,
  `get_reply` (при Р5 = А) — при Р3 = 1, Р4 = 1, Р6 = 1.
- `cli/status.py` берёт `fail`, `check_date` из `cli/journal.py`, своих копий не заводит; копии `fail`/`now` в
  main.py остаются (ими пользуются остальные команды; слияние дублей — не этот шаг, как в шаге 25).
- Функции переезжают без правок тела, имён и docstring; переименований нет. Рёбра импорта:
  `workload_sync → coach_calendar`, `main → status → journal`, `pult.js → tabs.js → *-pane.js`; обратных нет.
- При Р5 = Б: `db` — атрибут класса `Handler`, наследник с нужным значением создаётся внутри `make_server`;
  способ (вложенный класс-наследник или `type(...)`) — на выбор кабана под pyright strict; имена методов
  `do_*`, `log_message` vulture уже игнорирует (`pyproject.toml:68`).
- При Р6 = 1: таблица вкладок — без обращения к унаследованным ключам объекта (`Object.hasOwn` или `Map`);
  `loadState` зовётся с одним аргументом, как сейчас (`pult.js:166, :195`).
- Одна партия; коммит после ревью и тестов, аудит по коммиту (память проекта).

## Риски

- Порядок `coach --help` — единственное видимое, что может сдвинуться (Р3): держит новый тест порядка команд.
- Цифры «песочница» сняты с черновых правок, не с кода кабана; критерий — `make smells`, не арифметика. Сумма
  функций ≠ count файла у qlty (main.py: сумма 53 при count 50).
- `tabs.js` без автотестов — только проверка руками; ошибка в таблице вкладок даст пустую панель, не падение.
- При Р5 = Б атрибут класса вместо замыкания: два сервера в одном процессе (тесты поднимают их пачками) не
  должны делить `db` — поэтому наследник на каждый вызов `make_server`, а не запись в общий класс.
- При Р2 = 1 дубль вернётся, когда у двух пакетов снова совпадёт число реэкспортов (≥ 9).
- Г1 рефакторит `sync/workload_sync.py` в окне данных v2.9 (docs/plan-roadmap-r3.md «Риски»): тесты
  `tests/test_workload_sync*` — целиком, порядок замечаний в итоге `coach sync` не меняется (функции переезжают
  без правок тела).
- `cov` на HEAD мной не прогонялся: красный по другой причине вскроется на гейте — отдельный разговор.
- Строка `docs/pipeline.md` о партии — по местному правилу AGENTS.md, пишет оркестратор.

## Открытые вопросы

1. Р1 — `ignore_names` или правка теста (`pyproject.toml:68`, `tests/test_agenda_calendar_edit.py:285, :292`);
   варианты: (1) конфиг, (2) тест; рекомендую (1) — ложная находка, прецедент в той же строке конфига;
   разблокирует: формулировку «Правила» и п. 2 партии; решает: Влад. Блокирующий.
2. Р2 — дубль `__init__` (`agenda/__init__.py:15, :27`, `.qlty/qlty.toml`); варианты: (1) убрать реэкспорт,
   (2) фильтр qlty, (3) оба; рекомендую (1) — конфиг как есть; разблокирует: п. 2 партии; решает: Влад.
3. Р3, Р4, Р6 — варианты разреза (`cli/main.py:292`, `sync/workload_sync.py:58`, `web/static/pult.js:182`);
   рекомендую (1)/(1)/(1) — измерено, тесты не правятся; разблокирует: п. 3–4 партии; решает: Влад.
4. Р5 — `make_server` (`web/server.py:143`); варианты: (А) `get_reply`, (Б) `Handler` на уровень модуля;
   рекомендую (Б) — находка возвращалась дважды; разблокирует: п. 4 партии; решает: Влад.
5. Р7 — `cli/journal.py` = 49; варианты: (1) пункт беклога, (2) в этот шаг; рекомендую (1); разблокирует: объём
   партии; решает: Влад.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план Г1 (разделы «Суть», «Решения», «Файлы», «Партии», «Тесты», «Риски»). Внешних платных
статей нет: qlty, vulture, mutmut — локальные, бесплатные; подписки и хостинг не добавляются.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Токены LLM цепочки (разово за шаг) | — | ниже | Декарта не звать | ≈ 7 $ | разбор шага |

База — «Итог» П4 (`docs/plan-p4.md:1092`, последний «Итог» проекта): 5 партий, churn кода +2092/−527, 113,55 $.
Масштаб: Г1 — 1 партия ≈ 250 строк диффа (раздел «Файлы», «Объём»; перенос без правок тела) против ≈ 420 строк кода
на партию П4 → 0,6–1,0 сегмента партии базы. Круги ревью — как в базе (1–2, до 4 в П4 п. 3).
Уже прошло (`metrics.py --from 2026-11-13T07:04`): **5,37 $** (папа fable 4,24, оркестратор 0,97, тесть 0,16) —
нижняя граница сметы.

| Партия | Время |
|---|---|
| 0. План папы | 15 мин (факт) |
| 1. Доеба (тесты до правок) | 10–15 мин |
| 1. Кабан (находки 1–6) | 30–50 мин |
| 1. Ревью мамы + аудит свекрови | 20–35 мин |
| 1. Гейт `make check`, cov, mutmut (фон) | 30–90 мин |
| Тесть р.3 (+ Декарт по решению) | 10 мин (+ 20–30) |
| **итого** | 115–215 мин, из них фон 30–90 |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-11-10) |
|---|---|---|---|
| papa-kaban | fable 5.2 (факт metrics.py) | 3,4M | 4,24 (прошло) |
| orchestrator | opus 5.5 | 12–19M | 5,0–8,0 (в т. ч. 0,97 прошло) |
| kaban | sonnet | 2,1–3,6M | 0,8–1,4 |
| kaban-doeba | sonnet | 2,6–4,6M | 1,1–1,9 |
| mama-kaban | opus | 1,3–2,7M | 1,2–2,5 (сегмент базы 1,9 × 1 партия × 0,6–1,3) |
| kaban-svekrov | opus | 1,5–2,4M | 1,3–2,1 (сегмент базы 2,1 × 1 × 0,6–1,0) |
| kaban-test | opus | 1,1M | 1,2 (р.1 + р.3, без этого запуска 0,16) |
| kaban-dekart — по решению Влада | fable | 7,8M (2 вызова: 1 партия + 1 сводный, 3,9M — факт Ш9) | 7,0 (3,5 за вызов, `plan-sh47.md:372`) |
| **итого без Декарта** | | 24–37M | 14,8–21,3 |
| **итого с Декартом** | | 32–45M | 21,8–28,3 |

Модели — `grep -H '^model:'`: `kaban-test.md:model: opus`; `kaban.md:model: sonnet`; `kaban-doeba.md:model: sonnet`;
`mama-kaban.md:model: opus`; `kaban-svekrov.md:model: opus`; `kaban-dekart.md:model: fable`.
Токены — $ / ($ за 1M) по факту ролей в П4.

**Вердикт:** ок по бабкам; партия ≈ 250 строк < 400. Дешевле: только Декарт (≈ 7 $, теряем разбор). Ревью и
аудит не трогаем; кабан и доеба уже на sonnet. Самая дорогая позиция — оркестратор: держать контекст коротким
(ссылки на файлы, без повторных полных pytest — гейт один раз).

## Правки по ревью

- Партия 1, круг 1 (2026-11-13): pyright на тесте доебы `tests/test_cli.py:456` (`c.callback.__name__`) — доеба
  заменил на `assert command.callback is not None`; ревью мамы — можно мержить; аудит свекрови по 7ef3556 — чисто.
- mutmut (2026-11-13, коммит 7ef3556): 41 выживший, 1 suspicious, 4 timeout. Доеба (sonnet) — 12 тестов в
  `tests/test_cli.py`, `tests/test_workload_sync.py`, `tests/test_workload_sync_agenda.py`; повтор mutmut: убиты
  все заявленные, кроме `status` 7/22 (подстрочные проверки → точные, круг 3 мамы) — после правки killed.
  Остались 19 эквивалентных (обоснования сверены мамой по `mutmut show`): `_refusal` 4, 5, 12, 13, 14, 26, 27;
  `post_reply` 11, 12, 13, 32; `Handler.api` 25, 26, 49; `Handler.do_POST` 26, 27; `make_server` 11–13; `status` 19.
  `read_calendar` 6 — suspicious: мутант при переданном reader зовёт настоящий EventKit; тест
  `test_sync_with_reader_does_not_create_calendar_reader` его ловит, статус mutmut не меняется.
- Нарушение процесса: доеба один раз правил `tests/test_cli.py` через `sed -i` (sent → pushed); целостность
  проверена мамой (круг 2), аудит свекрови (круг 2) — на содержание не повлияло.

## Итог

Закрыты: BACKLOG 58, 80 (партия 1 — 7ef3556; коммит закрытия на момент подсчёта ещё не сделан).

**Источник токенов:** `metrics.py v2.8 ~/.claude/projects/-Users-vladislavahtamov-projects-ai-coach/5b257a3f-9f66-4278-937a-36d17f4b232d.jsonl --from 2026-11-13T07:04`;
**цены:** тариф metrics.py 2026-11-10 (https://platform.claude.com/docs/en/about-claude/pricing), сам pricing не перепроверял.

| Партия | Смета | Факт |
|---|---|---|
| 0. План папы | 15 мин | 12,0 мин (+ 0,3 дозаход в конце) |
| 1. Доеба (тесты до правок) | 10–15 мин | 2,3 мин (2 сегмента) |
| 1. Кабан (находки 1–6) | 30–50 мин | 3,7 мин |
| 1. Ревью мамы + аудит свекрови | 20–35 мин | 3,4 мин (сумма сегментов, 2 круга + круг по mutmut) |
| 1. Гейт, cov, mutmut + доеба по выжившим | 30–90 мин | интервал 07:52–09:33, в т. ч. простой; доеба 3,6 мин работы |
| Тесть р.3 | 10 мин | идёт |
| **итого** | 115–215 мин | интервал 170 мин (07:04–09:54), из них ожидание 125,5 мин (вопросы текстом 119,6) |

Расхождение по времени: работа ролей в 5–10 раз быстрее сметы (перенос без правок тела); весь интервал съело
ожидание пользователя (12 AskUserQuestion, окна по Р1–Р7) и фон mutmut — не длина сегментов.

| Роль | Модель | Токены | $ |
|---|---|---|---|
| papa-kaban | claude-fable-5-2 | 3,45M | 4,54 |
| orchestrator | claude-opus-5-5 | 14,44M | 4,39 (на момент подсчёта 09:54 UTC) |
| kaban | claude-sonnet-5-5 | 0,60M | 0,35 |
| kaban-doeba | claude-sonnet-5-5 | 1,49M | 0,66 |
| mama-kaban | claude-opus-5-5 | 0,39M | 0,66 |
| kaban-svekrov | claude-opus-5-5 | 0,35M | 0,62 |
| kaban-test | claude-opus-5-5 | 0,25M | 0,45 (на момент подсчёта 09:54 UTC) |
| kaban-dekart | — | 0 | не звали |
| **итого** | | 20,97M | 11,67 |

**Итого:** смета 14,8–21,3 $ (без Декарта) → факт 11,67 $ (ниже нижней границы: роли кабана, доебы, мамы и
свекрови ≈ вдвое дешевле сметы, оркестратор 4,39 против 5,0–8,0); 115–215 мин → 170 мин интервала, из них
44,5 мин работы оркестратора.
Churn после ревью: код +0/−0, тесты +117/−6 (22 % от строк до T0)
Разбор — кабан Декарта.
