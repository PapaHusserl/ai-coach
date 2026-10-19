# Шаг 23. Силовые упражнения на время (планка)

Закрывает BACKLOG 7. План — папа-кабан, 2026-10-19. Берётся, пока v2.7 досчитывает ±1 ч: в коде
пересечений с v2.7 нет (спайк живёт в `spikes/screen/*` и docs).

## Суть

У силового упражнения вместо повторов может быть длительность (планка, вис, статика). Тренер в
`create_draft_workout` задаёт `seconds` вместо `reps`; на часы уходит шаг с окончанием по времени,
на телефоне — таймер вместо «N повт.», в `describe_workout` — «60 с».

**Правило:** было `work = _step(order + 1, "interval", END_REPS, item["reps"])`
(`src/ai_coach/workouts/garmin_json.py`, `build_strength`) → станет: в упражнении задано `seconds` →
`_step(order + 1, "interval", END_TIME, item["seconds"])`, иначе `END_REPS, item["reps"]`; задано и то и
другое или ни одного → `ValueError` (в `create_draft_workout` превращается в `ToolError` «spec не подходит»,
как любая ошибка сборки — `mcp_server/tools.py`, `create_draft_workout`).
**Поведение:** меняется только для упражнений с `seconds`; spec с `reps` собирается байт в байт как раньше
(фикстура `tests/fixtures/workouts/strength.json` не меняется).
**Вне репо:** Garmin Connect — принимает ли шаг `END_TIME` с `exerciseName` / `weightValue` внутри
`RepeatGroupDTO` силовой (сейчас `END_TIME` там только у `rest`). Проверка — `coach push` тестовой
тренировки на часы, Влад.

## Решения

1. 2026-10-19, Влад: берём планку сейчас, параллельно — подготовка «Микронутриентов» (BACKLOG 6:
   ТЗ свинопаса и ресёрч дяди-кабана, без кода).
2. 2026-10-19, Влад, по рекомендации: имя поля — `seconds` (как у шагов mobility и run/bike/swim в том же
   spec), не `duration_seconds` из формулировки беклога. Беклог поправлен.
3. 2026-10-19, Влад: правки ROADMAP (строка v2.7, впереди v2.8 и v2.9, блок «Тренировки: доработки»)
   и нумерация BACKLOG (`## N.`, планка = 7) — приняты.

## Модули и функции

- `src/ai_coach/workouts/garmin_json.py: build_strength` — ветка `seconds` / `reps`, проверка «ровно одно».
- `src/ai_coach/workouts/garmin_json.py: _step_line` — уже печатает `time` → «с»; правок нет, закрыть тестом.
- `src/ai_coach/workouts/phone.py: _strength_blocks` — для `seconds` блок `{"k": "work", "sec": …, "kg": …}`
  вместо `reps`; `_clean` уже выкидывает пустые ключи (вес 0 у планки исчезнет сам).
- `player/ui.js: stepAmount`, `stepBody` — work-шаг с `sec` уже рисуется таймером (путь mobility:
  `stepBody` показывает часы, `kg` — отдельной строкой). Правок в JS нет; проверить тестом в
  `tests/player/expand.test.mjs` и руками на странице.
- `src/ai_coach/mcp_server/server.py` — описание `create_draft_workout`: у упражнения `reps` или `seconds`
  (статика: планка, вис), ровно одно.
- `.claude/skills/coach-plan/spec-formats.md` — то же в разделе strength.
- Не трогать: `sync/garmin_sync.py`, `sync/fit_import.py` (`reps` там — факт подходов из Garmin);
  план/факт повторы не сравнивает.
- `weight_kg` остаётся обязательным (как сейчас, `KeyError` → «spec не подходит»); для планки тренер
  передаёт 0. Делать необязательным — отдельное решение, не в этом шаге.

## Партии

1. `garmin_json.py: build_strength` — ветка по `seconds`/`reps`, `ValueError` при обоих/ни одном;
   docstring. На выходе: `build_workout("strength", spec)` с `seconds` даёт work-шаг
   `endCondition == END_TIME`, `endConditionValue == float(seconds)`, `exerciseName`/`weightValue` на месте;
   старая фикстура проходит без изменений.
2. `phone.py: _strength_blocks` — `sec` вместо `reps` при `seconds`. На выходе: `player_payload`
   даёт блок `{"r": sets, "t": title, "s": [{"k": "work", "sec": 60}, {"k": "rest", "sec": …}]}`;
   ссылка `get_workout_link` укладывается в `MAX_FRAGMENT`.
3. Описание инструмента в `server.py` и `spec-formats.md` скилла coach-plan; проверить лимит размера
   скилла, если он есть в тестах (`tests/test_coach_link_texts.py` и соседи).
4. Тесты (кабан-доеба, TDD — до партий 1–2): `tests/test_workouts_build.py`, `tests/test_workouts_phone.py`,
   `tests/test_mcp_write.py`, `tests/player/expand.test.mjs`.
5. Влад: черновик планки через `тренер` → `coach approve` → `coach push` → на часах шаг идёт по времени;
   `get_workout_link` → на телефоне таймер и название. Результат — в «Итог».

## Тесты (кабан-доеба)

- strength, упражнение `{"category": "PLANK", "exercise": "PLANK", "sets": 3, "seconds": 60,
  "rest_seconds": 60, "weight_kg": 0}` → work-шаг: `endCondition["conditionTypeKey"] == "time"`,
  `endConditionValue == 60.0`, `exerciseName == "PLANK"`, `weightValue == 0.0`; rest — как раньше.
- Тот же spec с `reps: 8` вместо `seconds` → `endCondition` `reps`, `endConditionValue == 8.0`
  (регресс; фикстура `strength.json` без изменений).
- Упражнение с `reps` и `seconds` сразу → `ValueError`; без обоих → `ValueError`.
- `create_draft_workout` с обоими / без обоих → `ToolError` «spec не подходит», в базе черновика нет;
  с `seconds` → черновик сохранён, `workout_json` содержит `seconds`.
- `describe_workout` для планки → строка вида `interval: 60 с, PLANK/PLANK, 0 кг`.
- Телефон: `player_payload("strength", spec)` → work-шаг `{"k": "work", "sec": 60}` (без `reps`,
  без `kg` при 0; с `kg` при весе > 0, например вис с отягощением); `r == sets`; `t` — title или код.
- Телефон, регресс: spec с `reps` → блок как раньше (`reps`, без `sec`).
- `expand.test.mjs`: блок `{r: 3, s: [{k: "work", sec: 60}, {k: "rest", sec: 60}]}` → `totalSeconds`
  = 360; `expand` даёт 6 шагов, у work `sec == 60`.
- Проверка руками: страница плеера по ссылке — на шаге планки часы 1:00 и обратный отсчёт, нет «повт.»;
  Garmin Connect / часы после `coach push` — шаг «60 с» внутри повтора ×3.

## Риски

- Garmin может не принять `END_TIME` у силового шага с `exerciseName` внутри `RepeatGroupDTO` или
  показать его иначе (например, без названия упражнения). Проверка только живым `coach push` (Влад);
  если отвергнет — вариант: шаг без `exerciseName`/`category`, название в `description`. Решение — Влад
  после прогона.
- Коды каталога для статики (`PLANK`/`PLANK`, `CORE`/…) — тренер берёт из каталога Garmin, как для прочих;
  в коде валидации кодов нет и не добавляем.
- `weight_kg: 0` обязателен в spec — тренер должен знать из описания инструмента; иначе `KeyError` →
  «spec не подходит».
- Player: `stepBody` при `sec` показывает только часы; `note` и `title` остаются — проверить, что для
  work-шага с `sec` не теряется название блока (`t` на уровне блока, как у strength сейчас).

## Итог

- Закрыт BACKLOG 7 → docs/done/007-silovye-uprazhneniya-na-vremya-planka.md. Коммиты 6c79922 (код), 3778a49 (документы).
- Партия 5: Влад прогнал `coach push` 2026-10-19 — Garmin принял END_TIME внутри RepeatGroupDTO, телефон показывает «60 с».
- Проблемы: ревью нашло 2 недостающих теста из плана (describe_workout, expand.test.mjs) — добавлены до коммита.
  Отложено: `seconds: null/0` проходит проверку ключа в `build_strength`.

### Стоимость (кабан-тесть)

**Источник токенов:** `metrics.py` по
`~/.claude/projects/-Users-vladislavahtamov-projects-ai-coach/0a1b7deb-1b1c-4821-9afe-047b886081d2.jsonl`;
**цены:** https://platform.claude.com/docs/en/about-claude/pricing, тариф 2026-10-17 (из `metrics.py`);
fable — по ценам Opus.

Сметы в документе шага нет — только факт.

| Партия | Смета | Факт |
|---|---|---|
| шаг целиком (партии 1–4) | нет | 35 мин шага, ожидание 12,8 мин; партия 5 — ручной push Влада, без агентов |

| Роль | Модель | Токены (in / cache read / cache write / out) | $ |
|---|---|---|---|
| orchestrator | opus-5-5 | 94 / 2 573 732 / 108 441 / 20 140 | 1.46 (на момент подсчёта 10:30 UTC, неполные) |
| papa-kaban | fable-5-1 | 626 / 1 184 442 / 280 224 / 943 | 1.66 |
| kaban-doeba | sonnet-5-5 | 28 / 286 493 / 57 120 / 2 436 | 0.20 |
| kaban-svekrov | opus-5-5 | 8 / 56 942 / 26 334 / 153 | 0.15 |
| mama-kaban | opus-5-5 | 10 / 68 218 / 21 365 / 62 | 0.12 |
| dyadya-kaban | opus-5-5 | 8 / 43 890 / 20 422 / 48 | 0.11 (BACKLOG 6, параллельно) |
| kaban-test | opus-5-5 | 4 / 12 292 / 18 443 / 19 | 0.10 (на момент подсчёта, неполные) |
| kaban | sonnet-5-5 | 14 / 107 891 / 21 936 / 178 | 0.07 |
| **итого** | | 792 / 4 333 900 / 554 285 / 23 979 | **3.86** |

**Итого:** сметы нет → факт ≈ $3.86 (орк. и тесть — неполные). Дороже всех papa-kaban (фоновый,
44,8 мин, 280K записи кэша) и оркестратор (2,6M чтения кэша).
