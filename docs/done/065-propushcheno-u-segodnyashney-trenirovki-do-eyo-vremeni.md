# 65. «Пропущено» у сегодняшней тренировки до её времени
status: done
priority: medium
updated: 2026-11-25

`rebuild_plan_actual` при синке пишет `skipped` плану текущего дня, хотя тренировка ещё впереди
(`load/plan_actual.py:79`, `garmin_sync.py:271`): окно и вкладка «Тренировки» показывают «пропущено»
до вечера (docs/plan-p3.md, Р31).

## Закрыто

Шаг Н35, 2026-11-25 — docs/plan-n35.md.
