# Шаг 26. Вес профиля: свежее ручное взвешивание

Закрывает BACKLOG 9. План — папа-кабан, 2026-10-28. Режим «встроить». Разведка на HEAD cb340d3, данные — живая
база `~/.local/share/ai-coach/coach.db` (только чтение: `sqlite3 ?mode=ro`, `PRAGMA query_only`).

## Суть

Наблюдение Влада (ручная проверка v2.8, 2026-10-28, записано только в BACKLOG 9): тренер считает КБЖУ от 80,6 кг
(Garmin), хотя ручное взвешивание 24.10 — 78,7 кг.

Разведка показала: **КБЖУ уже считается от 78,7**, а 80,6 — это Garmin-вес профиля, который уходит наружу как
«вес» рядом с настоящим или вместо него.

Что в базе (измерено):

- `weight_log` — 6 строк, все с `coach weight` (единственный писатель `add_weight` в `src/` —
  `cli/journal.py:93`); последняя `id 6, 2026-10-24 10:49:04, 78.7`, `deleted_at` пусто. Записей после 24.10
  нет, будущих дат нет.
- `profile_log key=weight` — две строки Garmin: `79.5 @ 2026-10-07`, `80.599 @ 2026-10-11 09:54:42`. С 11.10 Garmin
  отдаёт то же — `set_value` идемпотентен и не пишет повтор (`profile/service.py:152–155`).

Что отдаёт код на `2026-10-28` (прогон `current_profile` + `profile_nutrition` на живой базе):

- `current_profile(...)["weight_kg"] == 78.7` — верно: `_weight_kg` (`profile/service.py:181`) берёт последний
  `weight_log` до `day` включительно и только при пустом — Garmin.
- `nutrition`: `bmr 1774, tdee_rest 2129, kcal_target 1774, protein_g 157, fat_g 71, carbs_g 127` —
  `157 = round(2.0 × 78.7)`; от 80,6 было бы 161. Разница в BMR — 19 ккал.
- `current_profile(...)["values"]["weight"] == {"value": 80.599, "source": "garmin", "logged_at": "2026-10-11 09:54:42"}`
  — вот источник «80,6».

Куда это «80,6» утекает (grep по `src/` и `.claude/`):

| Выход | Что видно сейчас | Где |
|---|---|---|
| `get_morning_snapshot` → `profile.values.weight` | `80.599`, без источника; `weight_kg` в snapshot **не отдаётся** | `mcp_server/snapshot.py:120` — отдаёт только `values`, `missing`, `nutrition`, … |
| `get_profile` → `values.weight` и `weight_kg` | `80.599 (garmin, 11.10)` и `78.7` рядом — два «веса» | `mcp_server/tools.py:210–216` (`**current`) |
| `coach profile show` | `weight: 80.599 (garmin)`; `weight_kg` не печатается | `cli/profile.py:25–26` |
| `nutrition` | от какого веса посчитано — не видно | `profile/nutrition.py:113–123` |

Агент тренера (`.claude/agents/coach.md:16`) строит сводку из snapshot; `weight-food.md:5` велит «вес → цель» без
указания поля — в snapshot единственный «вес профиля» это `values.weight` = Garmin. Отсюда «КБЖУ от 80,6»:
ожидание (диалога в репо нет), не проверено, но другого 80,6 в данных нет.

Кандидаты из хэнд-бэка — проверены и сняты:

- zip/FIT-импорт в `weight_log` — нет: `add_weight` зовёт только `cli/journal.py:93`; `sync/fit_import.py:91`
  `weight` — поле подхода силовой (`strength_sets`), `sync/user_profile.py:39` пишет в `profile_log`.
- КБЖУ мимо `current_profile` — нет: `profile_nutrition` зовут только `snapshot.py:113` и `tools.py:209`, оба после
  `current_profile(conn, day)`.
- `day` — нет: snapshot и `get_profile` берут `date` = сегодня, `list_weights(conn, "0000-01-01", day)` включает 24.10.

Исходное решение шага 11 (`docs/plan-11.md:11`, 2026-10-07): «weight_kg (последний weight_log, иначе Garmin)»;
`service.py:3`: «Ручное значение главнее Garmin». Расчёт этому следует, показ — нет.

**Правило:** было — `_weight_kg`: `weights[-1]["weight_kg"] if weights else values["weight"]["value"]`, а наружу
отдельно уходит `values["weight"]` = Garmin → станет (при Р1 = 1): `values["weight"]` = выбранный вес
`{"value": <кг>, "source": "manual" | "garmin", "logged_at": <measured_at | logged_at>}`, `weight_kg` ему равен;
при Р2 = 2 выбор — по дате: `weight_log.measured_at` против `profile_log.logged_at` ключа `weight`, свежее побеждает.
**Поведение:** меняется — snapshot `profile.values.weight`, `get_profile.values.weight`, `coach profile show`
показывают один и тот же вес, что идёт в КБЖУ (сейчас на живой базе: 78,7 вместо 80,599). Числа КБЖУ не меняются.
**Вне репо:** нет (Garmin не трогаем, MCP-схема не меняется — перезапуск сервера не нужен).

## Решения

Влад, 2026-10-28 (окна):

- Р1 = (1): `values["weight"]` = выбранный вес с источником и датой, один вес во всех выходах.
- Р2 = (2): свежее по дате из `weight_log.measured_at` и `profile_log.logged_at`; ничья → ручной. Меняет решение
  шага 11 (`docs/plan-11.md:11`).
- Умолчания 1–5 приняты как есть.
- Предложение «`weight_kg` в `nutrition`» не берётся (при Р1 = 1 не нужно).

## Модули и функции

- `src/ai_coach/profile/service.py: _weight_kg` (181) — вернуть не число, а запись `{value, source, logged_at}`
  или `None`; `current_profile` (189) — положить её в `values["weight"]` (перекрыв Garmin) и оставить
  `weight_kg` = `value` (его читают `profile_nutrition`, `tools.profile`, тесты). При Р2 = 2 — сравнение дат внутри
  `_weight_kg`.
- `src/ai_coach/mcp_server/snapshot.py: _snapshot_profile` (109) — без правок при Р1 = 1 (берёт `values`); при
  Р1 = 2 — добавить ключ `weight_kg`.
- `src/ai_coach/mcp_server/tools.py: profile` (198) — без правок.
- `src/ai_coach/cli/profile.py: profile_show` (18) — без правок при Р1 = 1; при Р1 = 2 — печатать `weight_kg`.
- `.claude/skills/coach-morning/weight-food.md:5`, `.claude/agents/coach.md:16` — без правок при Р1 = 1; при
  Р1 = 2 — указать поле `profile.weight_kg`.
- `docs/architecture.md` — не правится (вес профиля там не описан).
- Тесты: `tests/test_profile_service.py:170–188` (4 теста веса), `tests/test_mcp_profile.py` (snapshot/get_profile),
  `tests/test_cli_profile.py` (новый тест `show`), `tests/test_profile_sync.py:90` (`weight_kg == 80.0` — остаётся).

## Партии

Одна партия: правка ≈ 10 строк в `service.py`, 6–8 тестов. Делить нечего.

1. Кабан-доеба (TDD): тесты из раздела ниже — красные на HEAD (воспроизводят `values.weight` = Garmin при более
   свежем `weight_log`).
2. Кабан: `_weight_kg` / `current_profile` по Р1/Р2; `make check` → `check: OK`.
3. Влад: проверка руками (ниже). Коммит после ревью и тестов, аудит по коммиту.

## Тесты (кабан-доеба)

Воспроизведение (сейчас красные — ожидание, не проверено на тестовой базе; на живой базе `values.weight`
80.599 при `weight_kg` 78.7 — проверено):

- `weight_log` 78.7 @ 2026-10-24 + Garmin `weight` 80.599 @ 2026-10-11, `day` 2026-10-28 →
  `values["weight"]["value"] == 78.7`, `source == "manual"`, `logged_at == "2026-10-24 10:49:04"`, `weight_kg == 78.7`.
- Инвариант: `values["weight"]["value"] == weight_kg` всегда, когда вес есть.
- Только Garmin → `values["weight"]` = Garmin-запись, `weight_kg` = её значение (есть: `test_garmin_weight_is_fallback`,
  дополнить проверкой `values`).
- Нет данных → `"weight" not in values`, `weight_kg is None`, `"weight" in missing` (есть: `test_weight_is_none_without_data`).
- Граница дня: тот же набор, `day` = 2026-10-23 → 79.2 (запись 18.10; 24.10 не попадает) — семантика
  `list_weights` до `day` включительно сохранена.
- `deleted_at` у последней ручной → берётся предыдущая (есть `test_delete_weight_hides_it_from_list`; через
  `current_profile` — добавить).
- При Р2 = 2: Garmin `logged_at` 2026-10-27 новее `weight_log` 2026-10-24 → Garmin; одинаковая дата → ручной
  (умолчание); при Р2 = 1 — существующий `test_weight_log_beats_garmin_weight` без изменений.
- snapshot: фикстура с обоими весами → `profile["values"]["weight"] == 78.7`; `test_snapshot_profile_skips_empty_keys`
  (`list(values) == ["sex"]`) и `test_snapshot_profile_has_no_history_or_sources` — остаются зелёными (без веса
  ключа нет; в snapshot уходит только `value`).
- `get_profile` → `values["weight"]["value"] == profile["weight_kg"]`.
- CLI `coach profile show` после `coach weight 78.7` при Garmin-записи 80.599 в `profile_log` → в выводе
  `weight: 78.7 (manual)`, строки `80.599` нет.
- Проверка руками (Влад): `coach profile show` → `weight: 78.7 (manual)`; `тренер` → в сводке вес 78,7; MCP
  `get_profile` (date = сегодня) → `values.weight.value` 78.7 и `weight_kg` 78.7; `get_morning_snapshot` →
  `profile.values.weight` 78.7.

Для mutmut (`модуль:функция`): `profile.service:_weight_kg`, `profile.service:current_profile`.

## Развилки

- **Р1. Что показывать как вес профиля** (snapshot `profile.values.weight`, `get_profile.values.weight`,
  `coach profile show`). (1) `values["weight"]` = выбранный вес с источником и датой (`manual` из `weight_log` /
  `garmin` из `profile_log`); Garmin-вес, если он проиграл, наружу не идёт — он есть в `get_profile(history=true)`.
  (2) `values.weight` оставить Garmin-ом, добавить `weight_kg` в snapshot и в вывод `show`, поправить
  `weight-food.md` и `coach.md` на поле `weight_kg`. Рекомендую (1): одна правда о весе во всех трёх выходах,
  без правок промптов и MCP-ответов по форме; (2) оставляет два «веса» рядом — та же путаница для тренера.
  Разблокирует партию; решает Влад.
- **Р2. Приоритет: ручной всегда или свежий.** (1) как сейчас и как решено в шаге 11 (`docs/plan-11.md:11`,
  2026-10-07): `weight_log` главнее Garmin независимо от дат. (2) по дате — свежее из `weight_log.measured_at` и
  `profile_log.logged_at` ключа `weight` (формулировка BACKLOG 9 «если он свежее»). Рекомендую (2): Garmin-вес
  обновляется, только если Влад поменял его в Garmin Connect или появятся весы Garmin — тогда это и есть
  свежее измерение; `logged_at` Garmin-записи — время первого sync с новым значением, при ежедневном sync —
  с точностью до дня. Цена: `test_weight_log_beats_garmin_weight` получает явные даты, +1 тест. Минус (2):
  логика на двух часах (измерение против sync); при редком sync Garmin-вес «молодеет». Решает Влад.
- Не развилка, а предложение: в `nutrition` добавить `weight_kg` (от какого веса посчитано) — при Р1 = 1 не нужно,
  вес и так один; делать только по «да».

## Умолчания (внутреннее)

- `_weight_kg` возвращает `dict | None` (имя не менять — его зовёт только `current_profile`; mutmut-цель та же).
- `logged_at` ручного веса = `measured_at` из `weight_log` (формат `YYYY-MM-DD HH:MM:SS`, как в `profile_log`).
- При Р2 = 2 сравнение строк ISO-дат целиком (`measured_at` против `logged_at`), ничья → ручной.
- `weight_kg` в `current_profile` остаётся (совместимость: `profile_nutrition`, `tools.profile`, 6 тестов).
- Одна партия; коммит после ревью и тестов, аудит по коммиту (память проекта).

## Правки по ревью

- Партия 1, аудит свекрови: перед сравнением дат `T` заменяется на пробел — отклонение от умолчания 3; Влад
  2026-10-28: оставить (защита от смешанного формата), записать здесь.
- Партия 1, ревью мамы (необязательные, взяты): кабан убирает особый случай `have_weight` в подсчёте `missing`
  (`key not in values`); доеба в `test_weight_log_beats_garmin_weight` задаёт дату Garmin явно (`at=`) и
  переименовывает в `test_newer_weight_log_beats_garmin_weight`.

## Риски

- `values["weight"]` сейчас с `source == "garmin"` используется онбордингом как «пришло из Garmin — спроси
  „верно?“» (`coach-onboarding.md:7`); после Р1 = 1 при ручном весе источник станет `manual` — это и есть
  правильное поведение (ручной уже подтверждён), но стоит глазом проверить сценарий первого запуска на пустой базе
  (там веса нет — `missing`, как и сейчас).
- `test_snapshot_profile_has_no_history_or_sources` проверяет отсутствие `source`/`logged_at` в тексте snapshot —
  `_snapshot_profile` отдаёт только `value`, запись с источником туда не протечёт; проверить после правки.
- Р2 = 2 меняет семантику старого теста шага 11 — фиксировать в «Решениях» со ссылкой на plan-11.
- Строка pipeline.md про партию — по местному правилу AGENTS.md, пишет оркестратор.

## Открытые вопросы

1. Р1 — где и какой вес показывать (блокирующий); рекомендую (1); решает Влад.
2. Р2 — ручной всегда или свежий по дате; рекомендую (2); решает Влад.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план шага 26 (одна партия, ≈10 строк в `service.py` + 6–8 тестов). Платного вне цепочки нет:
API, хостинг, БД, подписки не добавляются (SQLite локально, Garmin не трогаем). Постоянных расходов $0/мес.
База сметы — «Итог» шага 25 (`docs/plan-25-smells.md:298`, факт $12,49): масштаб шага 26 меньше (≈10 строк
против рефакторинга нескольких модулей), поэтому цифры ниже — ×0,6–0,8 от факта Ш25.
Цены — тариф metrics.py от 2026-10-25 (opus-5-5/fable: $4 вход, $0,20 чтение кэша, $5 запись, $20 выход;
sonnet-5-5 вдвое дешевле); страницу pricing не сверял.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Подписки/API/хостинг шага | 0 | нового платного нет | — | — | — |
| Прогон цепочки (разово) | ~$7–10 за шаг | масштаб ×0,6–0,8 от Ш25 | папа уже отработал; оркестратору — короче контекст (/compact после решения Р1/Р2) | ~$1 | ничего, если состояние в документе |
| Декарт | ~$0,6–1 | 1 партия → 2 вызова (1 + сводный), выжимки ≪ 400 KB | не трогаем (разбор) | — | — |

| Партия | Время |
|---|---|
| 1. Тесты (doeba, TDD) | ~5–8 мин (Ш25: 5,0) |
| 2. Правка `_weight_kg` + `make check` (kaban) | ~8–15 мин (меньше Ш25 26 мин: 10 строк) |
| Ревью + аудит | ~5–8 мин |
| Влад: решения Р1/Р2 + проверка руками | ~5–10 мин + простой |

Модели (`grep -H '^model:'`):
```
kaban-dekart.md:model: fable
kaban-svekrov.md:model: opus
papa-kaban.md:model: fable
kaban-doeba.md:model: sonnet
mama-kaban.md:model: opus
kaban-test.md:model: opus
kaban.md:model: sonnet
```
Мой запуск — opus-5-5, совпадает с `kaban-test.md`.

| Роль | Модель | Токены (cache read / write / out) | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| orchestrator | opus-5-5 | ~5–7M / 0,3M / 25K | 2,5–3,5 |
| papa-kaban (уже прошло) | fable | id в agents.md не сверял — интервал по Ш25 ×0,5–0,8: ~1,5–2,5M / 0,25–0,4M / 25–40K | 2–3,3 |
| svinopas | opus | не запускался | 0 |
| kaban-doeba | sonnet-5-5 | ~0,6M / 80K / 7K | 0,3–0,5 |
| kaban | sonnet-5-5 | ~1,2–1,8M / 0,2M / 15K | 0,8–1,1 |
| mama-kaban | opus-5-5 | ~0,4M / 50K / 6K | 0,4–0,6 |
| kaban-svekrov | opus-5-5 | ~0,6M / 50K / 10K | 0,5–0,7 |
| kaban-dekart | fable | 2 вызова, ~0,3M / 0,1M / 10K | 0,6–1 |
| **итого** | | | **~$7–10,7** |

Вердикт: ок по бабкам. Дешевле ролей не предлагаю: ревью/аудит не трогаем, маме, свекрови и оркестратору слабую
модель нельзя, kaban и doeba уже на sonnet. Единственный рычаг — оркестратору /compact после ответа Влада по Р1/Р2.

## Итог

- Закрыт BACKLOG 9 → docs/done/009-ves-profilya-svezhee-ruchnoe-vzveshivanie.md; коммит кода 0c925b5; ✅ в ROADMAP.

**Источник токенов:** `metrics.py` по
`~/.claude/projects/-Users-vladislavahtamov-projects-ai-coach/46fe38dc-0d3a-4372-b516-1c0a221e80c4.jsonl`;
**цены:** https://platform.claude.com/docs/en/about-claude/pricing, тариф metrics.py 2026-10-25 (страницу не
сверял — не проверено); fable — по ценам Opus.

| Партия | Смета | Факт |
|---|---|---|
| 1. Тесты (doeba) | ~5–8 мин | 7,3 мин (1,3 + 6,0); второй сегмент — правка по ревью мамы |
| 2. Правка + `make check` (kaban) | ~8–15 мин | 14,6 мин (7,9 + 6,7); в пределах, второй заход — правки по ревью |
| Ревью + аудит | ~5–8 мин | мама 0,8 + свекровь 2,0 ≈ 3 мин (параллельно); короче сметы |
| Влад: Р1/Р2 + проверка | ~5–10 мин + простой | ожидание 146 мин (вопросы 143,5, /compact 1,2), в т. ч. простой; время Влада не выделить |

| Роль | Модель | Токены (cache read / write / out) | $ |
|---|---|---|---|
| orchestrator | opus-5-5 | 6,01M / 0,33M / 27K | 3,40 (на момент подсчёта 10:02 UTC; смета 2,5–3,5) |
| papa-kaban | fable | 1,02M / 0,18M / 23K | 1,57 (смета 2–3,3; 3 коротких сегмента) |
| kaban | sonnet-5-5 | 0,38M / 0,10M / 5K | 0,34 (смета 0,8–1,1) |
| kaban-doeba | sonnet-5-5 | 0,36M / 84K / 7K | 0,32 (смета 0,3–0,5) |
| mama-kaban | opus-5-5 | 0,16M / 50K / 4K | 0,36 (смета 0,4–0,6) |
| kaban-svekrov | opus-5-5 | 0,45M / 65K / 9K | 0,60 (смета 0,5–0,7) |
| kaban-test | opus-5-5 | 90K / 57K / 3K | 0,36 (на момент подсчёта 10:02 UTC) |
| svinopas | opus | не запускался | 0 |
| kaban-dekart | fable | пока не запускался | 0 (смета 0,6–1) |
| **итого** | | 8,47M / 0,87M / 78K | **6,94** |

**Итого:** смета ~$7–10,7 → факт $6,94 без Декарта (с ним ≈ $7,5–8) — у нижней границы сметы. Ниже сметы
папа и kaban (смета от Ш25 завышена для правки на 10 строк); оркестратор у верхней границы. Постоянных расходов нет.
Разбор — кабан Декарта.
