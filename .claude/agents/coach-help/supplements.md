# Спортивное питание, добавки и витамины

Зачем: тренер напоминает, что и когда принять в день тренировки, и ведёт журнал приёмов. Не медицинский совет.

## Протоколы питания к тренировке - `coach protocol`

- Что это: правило «что съесть и выпить» до, во время или после тренировки: углеводы, белки, жидкость, натрий. Фаза: `before`, `during` (углеводы в час), `after`. Вид спорта: `strength`, `mobility`, `run`, `bike`, `swim`; без вида - любой.
- Как запустить: «заведи протокол: перед бегом от 60 минут 30 г углеводов» или `coach protocol add "<название>" --phase before|during|after [--sport ...] [--min-duration <мин>] [--offset <мин>] [--carbs <г>] [--protein <г>] [--fluid <мл>] [--sodium <мг>] [--note ...]`. Остальное: `coach protocol list`, `coach protocol show <id или название>`, `coach protocol edit <id> ...` (`--clear-sport`, `--clear-note`), `coach protocol delete <id>`.
- Что получу: нужен хотя бы один из углеводов, белков, жидкости, натрия, иначе протокол пустой. В день тренировки тренер сам после сводки предложит питание до/во время/после (протоколы подбираются по виду спорта и длительности; короче 75 минут - во время только вода), а в рационе `/coach-meal` приёмы встанут ко времени тренировки. Тренер читает протоколы через `get_sport_nutrition` и `get_sport_nutrition_for`.

## Добавки - `coach supplement`

- Что это: добавка с дозой за приём и графиком: `daily` (каждый день), `training_day` (в день тренировки), `before` или `after` (до или после тренировки). Единица: `g`, `mg`, `ml`, `pcs`.
- Как запустить: «заведи креатин 5 г каждый день» или `coach supplement add "<название>" --dose <число> --unit g|mg|ml|pcs --schedule daily|training_day|before|after [--time-note ...] [--note ...]`. Остальное: `coach supplement list`, `coach supplement show <id или название>`, `coach supplement edit <id> ...` (`--clear-time-note`, `--clear-note`), `coach supplement delete <id>`.
- Что получу: в утренней сводке - добавки на сегодня; без пометки «(принято)» тренер назовёт их непринятыми.

## Журнал приёма - `coach supplement take`, `log`, `untake`

- Что это: отметка «принял». Несколько раз в день можно. Время записи - время приёма, если отмечено в тот же день.
- Как запустить: фраза «принял креатин» или `coach supplement take <id или название> [--date YYYY-MM-DD] [--dose <число>] [--note ...]` (без дозы - по норме; в будущее нельзя); `coach supplement log [--date YYYY-MM-DD] [--from ... --to ...]` - приёмы с id; `coach supplement untake <id приёма>` - удалить отметку (пометка, строка остаётся). Читает тренер через `get_supplement_log`.

## Курсы витаминов и безрецептурных средств - `coach med`

- Что это: курс с датами: что, доза за приём, график, начало и конец (без конца - бессрочно). Вид: `vitamin`, `mineral`, `electrolyte`, `otc`; единица: `mg`, `mcg`, `iu`, `g`, `ml`, `pcs`.
- Как запустить: «заведи витамин D 2000 МЕ с 1 ноября на два месяца» или `coach med add "<название>" --kind ... --dose <число> --unit ... --schedule ... --start YYYY-MM-DD [--end YYYY-MM-DD] [--time-note ...] [--note ...]` (`--start` обязателен). Остальное: `coach med list [--date YYYY-MM-DD | --all]` (курсы на дату, по умолчанию сегодня), `coach med show <id или название>`, `coach med edit <id> ...` (`--no-end` - сделать бессрочным, `--clear-time-note`, `--clear-note`), `coach med delete <id>`.
- Что получу: курсы на сегодня в утренней сводке одной строкой: что, доза, когда. Читает тренер через `get_meds`. Нормы нутриентов - `get_nutrient_norms`. Дозы назначает врач, не тренер.
