# Шаг 12 — детальный план папы-кабана (2026-10-07)

Цитата пользователя и решения — docs/plan.md → «Шаг 12» (главнее этого файла).

## Файлы и шаги
1. Миграция `0008_pantry.sql`: `pantry_log(id, item TEXT NOT NULL, qty REAL NOT NULL, unit TEXT CHECK (unit IN ('g','ml','pcs')), op TEXT CHECK (op IN ('add','use','set')), logged_at TEXT NOT NULL, note TEXT)`, индекс (item, logged_at). Только добавление; остаток = последний `set` + Σadd − Σuse после него. Название — нижний регистр, без лишних пробелов; синонимы не склеиваются (агент берёт существующее название из `get_pantry`).
2. `store/pantry.py`: `add_entry(conn, row)`, `list_entries(conn, item=None)`.
3. `pantry/service.py`: `record(conn, op, item, qty, unit, now)` — qty > 0 (set — можно 0), unit из списка, у продукта одна единица (другая — ошибка); `stock(conn)` — qty > 0, минус → 0 + предупреждение; `missing(conn, need)` — чего нет и сколько докупить; `shopping_list(conn, need)` — текст.
4. `profile/nutrition.py`: чистая `remaining(targets, eaten)` → `{kcal, protein_g, fat_g, carbs_g}` (минус — перебор) + `pending_count` (записи еды без КБЖУ, в сумму не входят); нет nutrition → None.
5. MCP: `get_pantry()` → `{rows: [item, qty, unit, updated_at], truncated}` через `_cap`; `nutrition_remaining` в `get_profile` и `snapshot["profile"]`; `snapshot["pantry"]` — короткий список, ужимается. Пишущих инструментов не добавлять.
6. CLI: `coach pantry add|use|set "<продукт>" <qty> <unit>`, `remove` (= set 0), `list`; `coach shop "<продукт> <qty> <unit>" ...` (или `--from-file`) → `data/shopping/YYYY-MM-DD.md`, печать и путь, база не меняется; `coach shop done <файл>` — оприходовать список (см. решения).
7. Списание при `coach food` — не автоматически: после КБЖУ в /coach-food агент предлагает список списаний, после «да» — `uv run coach pantry use ...`; еда не из дома не списывается.
8. Скилл `.claude/skills/coach-meal/SKILL.md`: вход — `nutrition_remaining`, `diet`, `preferences`, `injuries`, тренировка дня, `get_pantry`; 1–2 блюда (или рацион до конца дня) под остаток ±10% ккал, упор на белок; состав в граммах и КБЖУ — с пометкой «оценка»; сверка с кладовой: «всё есть» или «нет: …», блюдо всё равно рекомендовать; замена из того, что есть; на «закажи» — `coach shop`, показать файл, наружу ничего не отправлять. `diet` — жёсткий фильтр, `preferences` — мягкий. Утром остаток занижен (цель растёт после тренировки) — проговаривать.
9. `coach.md`: после шага еды, до адаптации плана, без вопроса — прочитать coach-meal и предложить блюда, если `nutrition` есть и остаток ≥ 300 ккал, иначе строка «остаток закрыт»; пустые diet/preferences/кладовая — один вопрос в конце; кладовая не обновлялась > 7 дней — «актуально?»; tools + `mcp__ai-coach__get_pantry`.
10. `coach-onboarding.md`: блок «Питание» (diet — ответ «нет» тоже значение, preferences); `diet` в `missing` не добавлять.
11. settings.json: allow `Bash(uv run coach pantry:*)`, `Bash(uv run coach shop:*)`, `Bash(cat .claude/skills/coach-meal/SKILL.md)`.
12. Документы: architecture (pantry_log, get_pantry, nutrition_remaining), pipeline.md, backlog.

## Тесты (TDD)
- 0008 на пустой базе и после 0007; повторное открытие ничего не меняет.
- add курица 500 g → use 200 g → 300 g; set 1000 g → 1000, записи до set не влияют.
- «Курица » и «курица» — один продукт.
- add курица 2 pcs при единице g → ошибка, 0 строк; qty ≤ 0 для add/use, неизвестная единица → ошибка.
- use больше остатка → 0 и предупреждение, без исключения.
- missing: нужно курица 300 g + рис 100 g, есть курица 200 g → [курица 100 g, рис 100 g]; всё есть → пусто.
- remaining: цель 2500/150/70/300, съедено 1800/100/60/200 → 700/50/10/100; перебор → минус; запись без КБЖУ → pending_count 1; нет nutrition → None.
- MCP get_pantry — только qty > 0; пишущего pantry-инструмента в MCP нет.
- snapshot содержит profile.nutrition_remaining и pantry; profile не теряется при ужатии.
- coach shop создаёт файл в data/shopping, печатает, pantry_log не меняет; пустой список → ошибка. shop done оприходует строки.
- coach food не меняет pantry_log (регрессия).
- Ручная: `тренер` без запроса предлагает блюдо с составом и КБЖУ, называет недостающее; на «закажи» — список, ничего не отправляет.

## Риски
Токены (скилл по условию, кладовая ≤ 60 строк — проверить у тестя); кладовая расходится с реальностью (set, вопрос «актуально?»); дубли названий; аллергии — жёстко, «не медицинский совет».
