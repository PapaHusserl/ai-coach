# spec для create_draft_workout

`sport`: strength / mobility / run / bike / swim. `name` подставляется в spec сам. `estimated_duration_secs` - необязательно (секунды), по умолчанию 0. У упражнения или шага необязательно `title` (название по-русски, показывается на телефоне; иначе берётся из кода) и `note` (заметка).

## strength
```json
{"exercises": [{"category": "BENCH_PRESS", "exercise": "BARBELL_BENCH_PRESS",
                "sets": 3, "reps": 8, "rest_seconds": 90, "weight_kg": 40}]}
```
`category` и `exercise` - коды каталога Garmin (BENCH_PRESS / BARBELL_BENCH_PRESS, SQUAT / BARBELL_BACK_SQUAT, ROW / BARBELL_ROW и т.п.). Одно упражнение - sets подходов с отдыхом между ними.

## mobility (растяжка)
```json
{"steps": [{"exercise": "STRETCH_CAT_COW", "seconds": 40,
            "description": "Техника по-русски, коротко"}]}
```
`exercise` - коды `STRETCH_*` / `WARM_UP_*` каталога Garmin (например STRETCH_HAMSTRING, STRETCH_HIP_FLEXOR_AND_QUAD). `description` обязателен: на часах это заметка, анимаций нет.

## run / bike / swim
```json
{"steps": [{"type": "warmup", "seconds": 600},
           {"type": "interval", "meters": 5000, "pace_sec_per_km": [360, 330]},
           {"type": "cooldown", "seconds": 300}]}
```
`type`: warmup / interval / recovery / cooldown / rest. Шаг - `seconds` или `meters`. `pace_sec_per_km` - необязательно: [медленнее, быстрее], сек на км.
