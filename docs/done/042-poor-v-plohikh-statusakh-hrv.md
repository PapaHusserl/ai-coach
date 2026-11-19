# 42. POOR в плохих статусах HRV
status: done
priority: low
updated: 2026-11-20

`BAD_HRV_STATUSES` (`load/deviations.py`) не содержит `POOR` (статус API), а `tests/test_load_deviations.py:63`
закрепляет POOR как «fine» — проверить, решение это или пропуск. Источник — docs/plan-n16.md «Побочные находки» 2.

## Закрыто

Шаг Н33, 2026-11-20 — docs/plan-n33.md (решение: «Решения» п. 8).
